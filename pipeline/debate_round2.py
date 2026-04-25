"""Round 2 audit — re-run calibrated debate on the 23 tools flagged in round 1.

Uses the same prompts infrastructure (debate_runner.py), which was updated to:
  - voice_b approves when tool passes the 6 questions (no gratuitous challenge)
  - moderator treats 'pass' as default when both voices agree

Writes results to pipeline/debates/round2/
At end: compiles round2/_summary.json and highlights any tool STILL flagged.
"""
import json
import time
from pathlib import Path
from debate_runner import run_debate
from debate_audit_45 import build_context

PROJECT = Path(__file__).resolve().parent.parent
CONTENT_LOCK = PROJECT / "content_lock.json"
TOOLS_DIR = PROJECT / "assets" / "tools_final"
ROUND1_DIR = PROJECT / "pipeline" / "debates"
ROUND2_DIR = PROJECT / "pipeline" / "debates" / "round2"

FLAGGED_R1 = [
    "מצנח_מ01", "כנפיים_מ01",
    "ברזנט_מ02", "פטיש_מ02",
    "מפה_מ03", "משקפת_מ03", "מפתח_מ03",
    "רתמה_מ04", "רובה_חבלים_מ04",
    "רשת_מ05", "לפיד_מ05",
    "אופניים_מ06",
    "פריסקופ_מ07", "לום_מ07",
    "סולם_חבלים_מ08", "טפרי_טיפוס_מ08",
    "רב_כלי_מ09",
    "מצלמה_זעירה_מ10",
    "בנגי_מ11",
    "מצפן_מ13", "רחפן_מ13",
    "תיבה_מ14",
    "דגל_סיום_מ15",
]
assert len(FLAGGED_R1) == 23


def main():
    lock = json.loads(CONTENT_LOCK.read_text(encoding="utf-8"))
    ROUND2_DIR.mkdir(parents=True, exist_ok=True)
    t_start = time.time()

    for i, slug in enumerate(FLAGGED_R1, 1):
        out_file = ROUND2_DIR / f"production_designer_{slug}.json"
        if out_file.exists():
            print(f"[{i:02d}/23] skip (exists): {slug}")
            continue

        img = TOOLS_DIR / f"{slug}.png"
        question, context = build_context(slug, lock)
        print(f"[{i:02d}/23] {slug}  (elapsed {time.time()-t_start:.0f}s)")
        try:
            run_debate(
                role="production_designer",
                scene_id=slug,
                question=question,
                context=context,
                image_path=str(img),
                rounds=8,
                output_dir=str(ROUND2_DIR)
            )
        except Exception as e:
            print(f"    ERROR: {type(e).__name__}: {e}")

    # Compile summary comparing round 1 vs round 2
    summary = {
        "round": 2,
        "total": len(FLAGGED_R1),
        "debates": [],
        "still_flagged": [],
        "cleared": [],
        "decision_changes": {}
    }

    for slug in FLAGGED_R1:
        r1_file = ROUND1_DIR / f"production_designer_{slug}.json"
        r2_file = ROUND2_DIR / f"production_designer_{slug}.json"
        if not r2_file.exists():
            continue
        r1 = json.loads(r1_file.read_text(encoding="utf-8"))["final_decision"]
        r2 = json.loads(r2_file.read_text(encoding="utf-8"))["final_decision"]

        entry = {
            "slug": slug,
            "r1": {
                "decision": r1.get("decision"),
                "director_flag": r1.get("director_flag"),
                "flag_reason": r1.get("flag_reason")
            },
            "r2": {
                "decision": r2.get("decision"),
                "director_flag": r2.get("director_flag"),
                "flag_reason": r2.get("flag_reason"),
                "fix_notes": r2.get("fix_notes"),
                "synthesis": (r2.get("synthesis") or "")[:500]
            }
        }
        summary["debates"].append(entry)

        if r2.get("director_flag"):
            summary["still_flagged"].append(slug)
        else:
            summary["cleared"].append(slug)

        summary["decision_changes"][slug] = (
            f"{r1.get('decision')} → {r2.get('decision')}"
        )

    (ROUND2_DIR / "_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print()
    print("=== ROUND 2 SUMMARY ===")
    print(f"elapsed: {time.time()-t_start:.0f}s")
    print(f"total re-debated: {len(summary['debates'])}/23")
    print(f"STILL flagged: {len(summary['still_flagged'])}")
    for s in summary["still_flagged"]:
        print(f"  - {s}")
    print(f"cleared (unflagged now): {len(summary['cleared'])}")
    for s in summary["cleared"]:
        print(f"  - {s}  ({summary['decision_changes'][s]})")
    print()
    print(f"full summary: {ROUND2_DIR / '_summary.json'}")


if __name__ == "__main__":
    main()
