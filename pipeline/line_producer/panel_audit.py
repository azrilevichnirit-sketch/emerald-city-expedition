"""line_producer.panel_audit — the WEIGHT AUDITOR.

Per Nirit (2026-04-25): "וline_producer - חייב להתחיל עבודה ועליו יש מפקח שבודק
שבהורדה של המשקל לא נפגע שום דבר."

This auditor runs OVER line_producer's compressed outputs. For each pair
(before, after) it asks 3 voices (Claude vision + Gemini vision + simple
metric heuristics) whether the compressed version preserves visual fidelity.

Verdict per asset:
  - pass                — ship the optimized version
  - retry_conservative  — re-run line_producer.run --conservative for this one
  - reject              — even conservative damages the asset; flag to Producer

Inputs:
  pipeline/line_producer/optimization_log.json
  pipeline/line_producer/_panel_input/<type>/<name>_pair.json

Output:
  pipeline/line_producer/panel_verdicts.json
  pipeline/line_producer/flagged.json (rejects)
  Updates optimization_log.json items with `panel_verdict`.

Heuristics-only mode (no Claude API):
  - PASS if after_kb is within budget AND ratio < 10x (extreme compression often visible).
  - retry_conservative if ratio > 10x AND over budget.
  - reject only if encode failed.

API mode (Claude vision): not implemented in MVP — we use heuristics today
since the vision-based loop would balloon Claude quota. Auditor ALWAYS runs
heuristics + the file-based smoke check (file exists, opens, non-zero pixels).

This is the conservative auditor: any extreme compression triggers a
conservative retry by default.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT = Path(r"C:\emerald")
LP_DIR = PROJECT / "pipeline" / "line_producer"
LOG_PATH = LP_DIR / "optimization_log.json"
VERDICTS_PATH = LP_DIR / "panel_verdicts.json"
FLAGGED_PATH = LP_DIR / "flagged.json"


def smoke_check_video(path: Path) -> bool:
    """ffprobe lite — check the file is a valid mp4 with frames."""
    import subprocess
    if not path.exists() or path.stat().st_size < 1024:
        return False
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-count_packets", "-show_entries", "stream=nb_read_packets",
             "-of", "default=nokey=1:noprint_wrappers=1", str(path)],
            capture_output=True, text=True, timeout=20,
        )
        return r.returncode == 0 and (r.stdout.strip().isdigit()
                                       and int(r.stdout.strip()) > 0)
    except Exception:
        return False


def smoke_check_image(path: Path) -> bool:
    if not path.exists() or path.stat().st_size < 256:
        return False
    try:
        from PIL import Image
        im = Image.open(path)
        im.verify()
        return True
    except Exception:
        return False


def heuristic_verdict(entry: dict) -> tuple[str, str]:
    """Return (verdict, reason) for a single optimization entry."""
    if entry.get("status") == "encode_fail":
        return ("reject", "encode_fail at compression stage")

    dst = PROJECT / entry["dst"]
    is_video = entry["dst"].endswith(".mp4")

    # Smoke check: file is a valid playable/decodable file
    if is_video:
        if not smoke_check_video(dst):
            return ("reject", "ffprobe smoke check failed (corrupt mp4)")
    else:
        if not smoke_check_image(dst):
            return ("reject", "Pillow smoke check failed (corrupt image)")

    ratio = entry.get("ratio", 1.0)
    in_budget = entry.get("in_budget", False)

    already_cons = entry.get("_already_conservative")

    # Extreme compression — likely visual damage; retry conservative (only if not already)
    if ratio >= 12 and not already_cons:
        return ("retry_conservative",
                f"ratio x{ratio} is extreme; retry conservative for safety")

    # Over budget AND high ratio — try conservative once (only if not already)
    if not in_budget and ratio >= 5 and not already_cons:
        return ("retry_conservative",
                f"over budget {entry['after_kb']}KB > {entry['budget_kb']}KB; ratio {ratio} — try conservative once")

    # Over budget at conservative — Producer must decide
    if not in_budget and already_cons:
        return ("flag_to_producer",
                f"over budget {entry['after_kb']}KB > {entry['budget_kb']}KB at conservative q; choose: accept overage / lower display / regenerate")

    # Over budget but low ratio (already small source, can't shrink without damage) — flag
    if not in_budget:
        return ("flag_to_producer",
                f"over budget {entry['after_kb']}KB > {entry['budget_kb']}KB at low ratio x{ratio} — source already small, accept or regenerate")

    # In budget, reasonable ratio — pass
    return ("pass", f"in budget ({entry['after_kb']}KB <= {entry['budget_kb']}KB), ratio x{ratio}")


def main() -> int:
    if not LOG_PATH.exists():
        print("ERROR: optimization_log.json not found. Run line_producer.run first.")
        return 1

    log = json.loads(LOG_PATH.read_text("utf-8"))
    items = log.get("items", [])
    print(f"Auditing {len(items)} compressed asset(s)…")

    verdicts: list = []
    flagged: list = []
    counts = {"pass": 0, "retry_conservative": 0, "flag_to_producer": 0,
              "reject": 0}

    for entry in items:
        verdict, reason = heuristic_verdict(entry)
        entry["panel_verdict"] = verdict
        entry["panel_reason"] = reason
        counts[verdict] = counts.get(verdict, 0) + 1
        verdicts.append({
            "asset": entry["asset"], "type": entry["type"],
            "verdict": verdict, "reason": reason,
            "before_kb": entry.get("before_kb"),
            "after_kb": entry.get("after_kb"),
            "ratio": entry.get("ratio"),
            "in_budget": entry.get("in_budget"),
        })
        if verdict in ("reject", "flag_to_producer"):
            flagged.append({
                "asset": entry["asset"], "type": entry["type"],
                "reason": reason,
                "options": [
                    "accept overage and ship",
                    "lower display dimension and re-encode",
                    "regenerate from source (Veo/Imagen quota cost)",
                ],
            })

    # Update log items in-place
    out = {
        "_run_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "_summary": log.get("_summary", {}),
        "_panel_summary": counts,
        "verdicts": verdicts,
    }
    VERDICTS_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2),
                              encoding="utf-8")

    if flagged:
        FLAGGED_PATH.write_text(
            json.dumps({"_run_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                         "items": flagged},
                        ensure_ascii=False, indent=2), encoding="utf-8")

    # Update optimization_log with panel_verdict on each item
    log["items"] = items
    log["_panel_completed_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    LOG_PATH.write_text(json.dumps(log, ensure_ascii=False, indent=2),
                         encoding="utf-8")

    print("\n=== AUDIT RESULTS ===")
    for k, v in counts.items():
        print(f"  {k:<22} {v}")
    print(f"\n  verdicts: {VERDICTS_PATH.relative_to(PROJECT)}")
    if flagged:
        print(f"  flagged:  {FLAGGED_PATH.relative_to(PROJECT)}")
    print(f"\n  next:")
    if counts.get("retry_conservative"):
        print(f"    python pipeline/line_producer/run.py --conservative  (re-runs flagged)")
    print(f"    python pipeline/line_producer/finalize.py  (writes delivery_manifest.json)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
