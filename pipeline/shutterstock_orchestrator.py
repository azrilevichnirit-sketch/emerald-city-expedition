"""Shutterstock ORCHESTRATOR — runs the 5-agent loop for all 96 items.

Pipeline per item, up to 3 rounds:

  round N:
    1. master.plan_item(item, round=N, feedback=prev_round_feedback)
         -> command JSON with primary_query + intent_for_checker + hard_rejects
    2. searcher.search_with_fallbacks(command)
         -> up to 10 result thumbnails
    3. result_checker.check_results(command, search_envelope)
         -> verdict (PASS with chosen_id, or RETRY with feedback)
    4. if RETRY: carry feedback forward, round += 1 (up to 3), goto 1.
    5. downloader.license_and_download(chosen_id, fmt, size, saved_path)
         -> file written to review folder
    6. download_checker.check_download(command, saved_path)
         -> verdict (PASS final, or RETRY with feedback)
    7. if RETRY: delete file, carry feedback forward, round += 1, goto 1.

After 3 rounds without PASS: item marked FAIL_exhausted in ledger.

Output folders:
  pipeline/review/shutterstock/tools/<slug>.<ext>     (45 tools)
  pipeline/review/shutterstock/scenery/<slug>.<ext>   (51 props)
  pipeline/staging/shutterstock/ledger/<slug>.json    (per-item log)
  pipeline/review/shutterstock/_status.json           (running summary)

Items input:
  tools  — read from content_lock.json (missions[M*].tools[].label/file)
  scenery — read from pipeline/debates/scenery/_props_structured.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT = Path(__file__).resolve().parent.parent
PIPELINE = PROJECT / "pipeline"
REVIEW = PROJECT / "pipeline" / "review" / "shutterstock"
LEDGER = PROJECT / "pipeline" / "staging" / "shutterstock" / "ledger"

sys.path.insert(0, str(PIPELINE))

from shutterstock_master import plan_item  # noqa: E402
from shutterstock_searcher import search_with_fallbacks  # noqa: E402
from shutterstock_result_checker import check_results  # noqa: E402
from shutterstock_downloader import license_and_download  # noqa: E402
from shutterstock_download_checker import check_download  # noqa: E402


MAX_ROUNDS = 3


def ensure_dirs():
    (REVIEW / "tools").mkdir(parents=True, exist_ok=True)
    (REVIEW / "scenery").mkdir(parents=True, exist_ok=True)
    LEDGER.mkdir(parents=True, exist_ok=True)


def load_items(categories: list[str] | None = None) -> list[dict]:
    """Build the unified item list.

    Returns records with: slug, category, he_label, en_prompt, mission,
    mission_text.
    """
    categories = categories or ["tools", "scenery"]
    items: list[dict] = []

    if "tools" in categories:
        cl = json.loads((PROJECT / "content_lock.json").read_text("utf-8"))
        for mission_id, m in cl["missions"].items():
            mission_text = m.get("mission_text", "")
            for t in m.get("tools", []):
                label = t.get("label", "")
                # Strip .png/.jpg extension from file to get a slug.
                fpath = t.get("file", "")
                slug_base = Path(fpath).stem if fpath else label
                # Build a romanized slug — we need safe filenames in
                # pipeline/review for downstream builder code.
                items.append({
                    "slug": slug_base,
                    "category": "tools",
                    "he_label": label,
                    "en_prompt": t.get("en_prompt", ""),
                    "mission": mission_id,
                    "mission_text": mission_text,
                    "slot": t.get("slot"),
                    "points": t.get("points"),
                })

    if "scenery" in categories:
        props = json.loads(
            (PROJECT / "pipeline" / "debates" / "scenery" / "_props_structured.json")
            .read_text("utf-8")
        )
        # content_lock missions for mission_text backfill
        cl = json.loads((PROJECT / "content_lock.json").read_text("utf-8"))
        for p in props:
            mid = p.get("mission", "")
            mission_text = cl["missions"].get(mid, {}).get("mission_text", "")
            items.append({
                "slug": p["slug"],
                "category": "scenery",
                "he_label": p.get("he", ""),
                "en_prompt": p.get("en_prompt", ""),
                "mission": mid,
                "mission_text": mission_text,
            })

    return items


def landing_path(item: dict, fmt: str) -> Path:
    ext_map = {"png": "png", "jpg": "jpg", "jpeg": "jpg", "eps": "eps", "svg": "svg"}
    ext = ext_map.get((fmt or "").lower(), "png")
    subdir = REVIEW / ("tools" if item["category"] == "tools" else "scenery")
    # Use the slug as-is; content_lock already uses Hebrew filenames for tools,
    # so the saved path matches what the builder expects.
    return subdir / f"{item['slug']}.{ext}"


def run_one_item(item: dict, force: bool = False) -> dict:
    """Run the 5-agent loop for a single item. Returns the ledger entry."""
    entry: dict[str, Any] = {
        "item": item,
        "rounds": [],
        "final_status": "PENDING",
        "final_path": None,
        "started_ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    # Skip if already delivered (unless --force).
    for ext in ("png", "jpg", "eps", "svg"):
        candidate = landing_path(item, ext)
        if candidate.exists() and not force:
            entry["final_status"] = "ALREADY_DONE"
            entry["final_path"] = str(candidate.relative_to(PROJECT))
            entry["ended_ts"] = entry["started_ts"]
            return entry

    feedback: str | None = None
    for round_num in range(1, MAX_ROUNDS + 1):
        round_log: dict[str, Any] = {"round": round_num}

        # 1. Master.
        try:
            cmd = plan_item(item, round_num=round_num,
                           feedback_from_previous_round=feedback)
            round_log["master_cmd"] = {
                "rationale": cmd.get("rationale"),
                "query": cmd.get("primary_query", {}).get("query"),
                "image_type": cmd.get("primary_query", {}).get("image_type"),
                "license": cmd.get("license"),
                "intent": cmd.get("intent_for_checker"),
                "give_up": cmd.get("give_up", False),
            }
        except Exception as e:
            round_log["master_error"] = f"{type(e).__name__}: {e}"
            entry["rounds"].append(round_log)
            entry["final_status"] = "FAIL_master_error"
            break

        if cmd.get("give_up"):
            entry["rounds"].append(round_log)
            entry["final_status"] = "FAIL_master_gave_up"
            break

        # 2. Searcher.
        search_env = search_with_fallbacks(cmd, per_page=10)
        round_log["search_status"] = search_env.get("status")
        round_log["search_returned"] = search_env.get("returned", 0)
        round_log["search_total"] = search_env.get("total_count", 0)

        if search_env.get("status") != "OK":
            feedback = f"Searcher returned status={search_env.get('status')} (attempts: {search_env.get('attempts')}). Broaden query or swap image_type."
            round_log["result_check"] = None
            round_log["download"] = None
            round_log["download_check"] = None
            entry["rounds"].append(round_log)
            continue

        # 3. Result checker.
        try:
            rc = check_results(cmd, search_env)
            round_log["result_check"] = {
                "verdict": rc.get("verdict"),
                "chosen_id": rc.get("chosen_id"),
                "feedback": rc.get("feedback_to_master"),
                "inspected": rc.get("candidates_inspected"),
            }
        except Exception as e:
            round_log["result_check"] = {"error": f"{type(e).__name__}: {e}"}
            entry["rounds"].append(round_log)
            feedback = f"result_checker raised {type(e).__name__}: {e}"
            continue

        if rc.get("verdict") != "PASS":
            feedback = rc.get("feedback_to_master") or "result_checker returned RETRY without feedback"
            entry["rounds"].append(round_log)
            continue

        chosen_id = rc.get("chosen_id")
        lic = cmd.get("license", {})
        fmt = lic.get("format", "png")
        size = lic.get("size", "huge")
        target = landing_path(item, fmt)

        # 4. Downloader.
        dl = license_and_download(chosen_id, fmt, size, target)
        round_log["download"] = {
            "status": dl.get("status"),
            "license_id": dl.get("license_id"),
            "saved_bytes": dl.get("saved_bytes"),
            "saved_path": dl.get("saved_path"),
            "error": dl.get("error"),
        }
        if dl.get("status") != "OK":
            # Download-level failures: some are retryable via master change.
            if dl.get("status", "").startswith("FAIL_license_http_403"):
                feedback = "Licensing rejected with 403 — scope or subscription issue, not a query issue. Re-issue the same command; the orchestrator will abort if this persists."
            else:
                feedback = f"Download failed: {dl.get('status')} — {dl.get('error','')[:160]}"
            entry["rounds"].append(round_log)
            continue

        # 5. Download checker.
        dc = check_download(cmd, target)
        round_log["download_check"] = {
            "verdict": dc.get("verdict"),
            "deterministic": dc.get("deterministic_checks"),
            "vision": dc.get("vision_check"),
            "feedback": dc.get("feedback_to_master"),
        }

        if dc.get("verdict") == "PASS":
            entry["rounds"].append(round_log)
            entry["final_status"] = "OK"
            entry["final_path"] = str(target.relative_to(PROJECT))
            entry["final_license_id"] = dl.get("license_id")
            entry["final_sha256"] = dl.get("sha256")
            break

        # Download checker said RETRY — delete the rejected file so we don't
        # leave garbage in the review folder.
        try:
            if target.exists():
                target.unlink()
        except Exception:
            pass
        feedback = dc.get("feedback_to_master") or "download_checker RETRY without feedback"
        entry["rounds"].append(round_log)

    if entry["final_status"] == "PENDING":
        entry["final_status"] = "FAIL_exhausted_3_rounds"

    entry["ended_ts"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return entry


def write_status(items_done: list[dict]):
    summary: dict[str, Any] = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total": len(items_done),
        "by_status": {},
        "by_category": {"tools": {"ok": 0, "fail": 0, "pending": 0},
                        "scenery": {"ok": 0, "fail": 0, "pending": 0}},
        "items": [],
    }
    for e in items_done:
        st = e.get("final_status", "UNKNOWN")
        summary["by_status"][st] = summary["by_status"].get(st, 0) + 1
        cat = e["item"].get("category", "unknown")
        if cat in summary["by_category"]:
            if st in ("OK", "ALREADY_DONE"):
                summary["by_category"][cat]["ok"] += 1
            elif st.startswith("FAIL"):
                summary["by_category"][cat]["fail"] += 1
            else:
                summary["by_category"][cat]["pending"] += 1
        summary["items"].append({
            "slug": e["item"]["slug"],
            "category": cat,
            "status": st,
            "path": e.get("final_path"),
            "rounds": len(e.get("rounds", [])),
        })
    (REVIEW / "_status.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--categories", nargs="+", default=["tools", "scenery"],
                    choices=["tools", "scenery"],
                    help="Which categories to run.")
    ap.add_argument("--limit", type=int, default=None,
                    help="Stop after N items (for testing).")
    ap.add_argument("--only", nargs="*", default=None,
                    help="Run only these slugs (space-separated).")
    ap.add_argument("--force", action="store_true",
                    help="Re-run even if landing file already exists.")
    args = ap.parse_args()

    ensure_dirs()
    items = load_items(args.categories)
    if args.only:
        items = [it for it in items if it["slug"] in args.only]
    if args.limit:
        items = items[: args.limit]

    print(f"[orchestrator] dispatching {len(items)} items "
          f"(categories={args.categories}, limit={args.limit}, force={args.force})")

    done: list[dict] = []
    for i, item in enumerate(items, 1):
        print(f"[{i}/{len(items)}] {item['category']:7s} {item['slug']} …")
        entry = run_one_item(item, force=args.force)
        done.append(entry)

        # Per-item ledger.
        ledger_path = LEDGER / f"{item['slug']}.json"
        ledger_path.write_text(
            json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        print(f"         -> {entry['final_status']}  "
              f"rounds={len(entry.get('rounds', []))}  "
              f"path={entry.get('final_path')}")

        # Refresh running status after each item so Nirit can watch progress.
        write_status(done)

    write_status(done)

    ok_count = sum(1 for e in done if e["final_status"] in ("OK", "ALREADY_DONE"))
    fail_count = sum(1 for e in done if e["final_status"].startswith("FAIL"))
    print(f"\n[orchestrator] complete: {ok_count} OK, {fail_count} FAIL, "
          f"of {len(done)} dispatched")
    print(f"[orchestrator] ledger: {LEDGER.relative_to(PROJECT)}")
    print(f"[orchestrator] review folders: "
          f"{(REVIEW/'tools').relative_to(PROJECT)}, "
          f"{(REVIEW/'scenery').relative_to(PROJECT)}")
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
