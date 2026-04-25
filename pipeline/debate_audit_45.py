"""Retroactive audit of all 45 tool icons — production_designer role.

For each tool:
  - Loads mission_text + slot + label + points from content_lock.json
  - Loads PNG from assets/tools_final/
  - Runs 8-round debate (Gemini lead / Claude challenge / OpenAI moderator)
  - Saves pipeline/debates/production_designer_{slug}.json

At end: compiles pipeline/debates/_summary.json with counts + flagged list.

Resumes: tools whose debate JSON already exists are skipped.
"""
import json
import time
from pathlib import Path
from debate_runner import run_debate

PROJECT = Path(__file__).resolve().parent.parent
CONTENT_LOCK = PROJECT / "content_lock.json"
TOOLS_DIR = PROJECT / "assets" / "tools_final"
DEBATES_DIR = PROJECT / "pipeline" / "debates"

ALL_SLUGS = [
    "מצנח_מ01", "גלשן_מ01", "כנפיים_מ01",
    "ברזנט_מ02", "פטיש_מ02", "אוהל_מ02",
    "מפה_מ03", "משקפת_מ03", "מפתח_מ03",
    "קרשים_מ04", "רתמה_מ04", "רובה_חבלים_מ04",
    "פנס_עוצמתי_מ05", "רשת_מ05", "לפיד_מ05",
    "גריקן_מ06", "ערכה_מ06", "אופניים_מ06",
    "דגל_מ07", "פריסקופ_מ07", "לום_מ07",
    "סולם_חבלים_מ08", "חבל_קשרים_מ08", "טפרי_טיפוס_מ08",
    "שמן_מ09", "רב_כלי_מ09", "מבער_מ09",
    "מצלמה_זעירה_מ10", "שמיכה_מ10", "קאטר_מ10",
    "סנפלינג_מ11", "בנגי_מ11", "מצנח_בסיס_מ11",
    "כרטיס_מ12", "מצלמה_פלאש_מ12", "לפיד_יד_מ12",
    "סרגל_מ13", "מצפן_מ13", "רחפן_מ13",
    "מטבעות_מ14", "תיבה_מ14", "כדור_בדולח_מ14",
    "דגל_סיום_מ15", "מגאפון_מ15", "זיקוק_מ15",
]
assert len(ALL_SLUGS) == 45

DIMENSIONS = {
    "M1": "סיכון", "M2": "יציבות", "M3": "FOMO", "M4": "סיכון",
    "M5": "אימפולסיביות", "M6": "יציבות", "M7": "FOMO", "M8": "סיכון",
    "M9": "אימפולסיביות", "M10": "יציבות", "M11": "סיכון",
    "M12": "FOMO", "M13": "יציבות", "M14": "אימפולסיביות", "M15": "סיכון"
}


def build_context(slug, lock):
    mnum = slug.split("_")[-1]
    m_key = f"M{int(mnum[1:]):d}"
    mission = lock["missions"][m_key]
    idx = ALL_SLUGS.index(slug) % 3
    tool = mission["tools"][idx]
    triplet = " / ".join(
        f"{t['slot']}={t['label']} ({t['points']}pt)" for t in mission["tools"]
    )
    ctx = (
        f"משימה {m_key} (מדד {DIMENSIONS[m_key]}): \"{mission['mission_text']}\"\n"
        f"שלישייה: {triplet}\n"
        f"הכלי הנבדק: slot {tool['slot']} — {tool['label']} ({tool['points']} נק')"
    )
    question = (
        f"האם אייקון הכלי '{tool['label']}' (slug={slug}, {m_key}, slot {tool['slot']}, "
        f"{tool['points']}pt, מדד {DIMENSIONS[m_key]}) אינטואיטיבי מיד לשחקן? "
        f"האם עומד בלוגיקת המשחק — איך השחקנית משתמשת בו? "
        f"האם ויזואלית ברור ומובחן מ-2 האחרים בשלישייה? "
        f"צפה בתמונה והכרע pass/fix/redo."
    )
    return question, ctx


def main():
    lock = json.loads(CONTENT_LOCK.read_text(encoding="utf-8"))
    missing = []
    t_start = time.time()

    for i, slug in enumerate(ALL_SLUGS, 1):
        out_file = DEBATES_DIR / f"production_designer_{slug}.json"
        if out_file.exists():
            print(f"[{i:02d}/45] skip (exists): {slug}")
            continue

        img = TOOLS_DIR / f"{slug}.png"
        if not img.exists():
            print(f"[{i:02d}/45] MISSING PNG: {slug}")
            missing.append(slug)
            continue

        question, context = build_context(slug, lock)
        print(f"[{i:02d}/45] {slug}  (elapsed {time.time()-t_start:.0f}s)")
        try:
            run_debate(
                role="production_designer",
                scene_id=slug,
                question=question,
                context=context,
                image_path=str(img),
                rounds=8
            )
        except Exception as e:
            print(f"    ERROR: {type(e).__name__}: {e}")

    # Build summary
    summary = {"total": 45, "missing_pngs": missing, "debates": []}
    pass_count = fix_count = redo_count = flagged_count = 0

    for slug in ALL_SLUGS:
        p = DEBATES_DIR / f"production_designer_{slug}.json"
        if not p.exists():
            continue
        data = json.loads(p.read_text(encoding="utf-8"))
        fd = data.get("final_decision", {})
        entry = {
            "slug": slug,
            "decision": fd.get("decision"),
            "director_flag": fd.get("director_flag"),
            "flag_reason": fd.get("flag_reason"),
            "fix_notes": fd.get("fix_notes"),
            "synthesis": (fd.get("synthesis") or "")[:400]
        }
        summary["debates"].append(entry)
        d = fd.get("decision")
        if d == "pass":
            pass_count += 1
        elif d == "fix":
            fix_count += 1
        elif d == "redo":
            redo_count += 1
        if fd.get("director_flag"):
            flagged_count += 1

    summary["counts"] = {
        "pass": pass_count, "fix": fix_count, "redo": redo_count,
        "flagged": flagged_count
    }
    summary["flagged_slugs"] = [
        d["slug"] for d in summary["debates"] if d["director_flag"]
    ]
    summary["needs_fix_or_redo"] = [
        d["slug"] for d in summary["debates"] if d["decision"] in ("fix", "redo")
    ]

    (DEBATES_DIR / "_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print()
    print("=== SUMMARY ===")
    print(f"total elapsed: {time.time()-t_start:.0f}s")
    print(f"pass={pass_count}  fix={fix_count}  redo={redo_count}  flagged={flagged_count}")
    print(f"flagged slugs: {summary['flagged_slugs']}")
    print(f"needs_fix_or_redo: {summary['needs_fix_or_redo']}")
    print(f"missing pngs: {missing}")
    print(f"summary: {DEBATES_DIR / '_summary.json'}")


if __name__ == "__main__":
    main()
