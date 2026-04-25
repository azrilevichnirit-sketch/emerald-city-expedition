"""
Phase 0E final summary.
Reads approved (in assets/tools/) + final_review verdicts + auto_review + retries.
Writes pipeline/phase_0E_summary.json with:
  - approved[]: tools with PNG in assets/tools/
  - needs_manual_review[]: tools that failed >= 2 retries
  - counts
"""
import json
from pathlib import Path

PROJECT = Path(r"C:/Users/azril/OneDrive/Desktop/fincail_game/new")
PROMPTS = PROJECT / "pipeline" / "prompts"
ASSETS = PROJECT / "assets" / "tools"
VERDICTS = PROJECT / "pipeline" / "human_review_verdicts.json"
AUTO = PROJECT / "pipeline" / "auto_review.json"
RETRIES = PROJECT / "pipeline" / "retries_queue.json"


def main():
    slugs = [p.stem for p in sorted(PROMPTS.glob("*.json"))]
    verdicts_raw = json.loads(VERDICTS.read_text(encoding="utf-8")) if VERDICTS.exists() else {}
    verdicts = verdicts_raw.get("verdicts", verdicts_raw)
    auto = json.loads(AUTO.read_text(encoding="utf-8")) if AUTO.exists() else {}
    retries = json.loads(RETRIES.read_text(encoding="utf-8")) if RETRIES.exists() else {"exhausted": []}

    approved = []
    needs_manual = []
    for s in slugs:
        if (ASSETS / f"{s}.png").exists():
            approved.append(s)
        elif s in retries.get("exhausted", []):
            needs_manual.append({"slug": s, "reason": "retry_exhausted"})
        else:
            v = verdicts.get(s, {})
            a = auto.get(s, {})
            if v.get("verdict") == "FAIL":
                needs_manual.append({"slug": s, "reason": v.get("reason", "human_review_fail")})
            elif a.get("status", "").startswith("auto_fail"):
                needs_manual.append({"slug": s, "reason": a["status"]})
            else:
                needs_manual.append({"slug": s, "reason": "unknown_status"})

    summary = {
        "phase": "0E",
        "date": "2026-04-21",
        "total_tools": len(slugs),
        "approved_count": len(approved),
        "needs_manual_review_count": len(needs_manual),
        "engines": {
            "leonardo_phoenix": "rounds 1-2 — 34 approved",
            "google_imagen_4": "rounds 3-4 — 11 approved (fallback for Leonardo failures)",
        },
        "approved": approved,
        "needs_manual_review": needs_manual,
    }
    out_path = PROJECT / "pipeline" / "phase_0E_summary.json"
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"approved: {len(approved)}")
    print(f"needs_manual_review: {len(needs_manual)}")
    print(f"summary: {out_path}")


if __name__ == "__main__":
    main()
