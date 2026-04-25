"""Assemble the clean final tools folder — 45 PNGs only, nothing else.

Sources:
  - r9/r6 approved: גלשן_מ01 (r9), מצנח_בסיס_מ11 (r6) → from pipeline/review
  - rA fixes (12): from pipeline/review/tools_qa_gemini/{slug}_rA_final.png
  - rB fix (1):   זיקוק_מ15 (rB) → pipeline/review
  - Previously approved (30): from current assets/tools/
Writes into: assets/tools_final/
Excludes: styletest variants, raw/temp files.
"""
import shutil
from pathlib import Path

PROJECT = Path(r"C:/Users/azril/OneDrive/Desktop/fincail_game/new")
ASSETS = PROJECT / "assets" / "tools"
REVIEW = PROJECT / "pipeline" / "review" / "tools_qa_gemini"
FINAL = PROJECT / "assets" / "tools_final"

FINAL.mkdir(parents=True, exist_ok=True)
# Wipe any stale files so the folder contains ONLY the 45 approved tools
for f in FINAL.iterdir():
    if f.is_file():
        f.unlink()

# Map: destination filename (as in assets/tools/) -> source path
FIXED_RA = [
    "דגל_סיום_מ15", "סולם_חבלים_מ08", "מצנח_מ01", "פטיש_מ02",
    "מפתח_מ03", "רובה_חבלים_מ04", "רשת_מ05", "לפיד_מ05",
    "חבל_קשרים_מ08", "רב_כלי_מ09", "שמיכה_מ10", "בנגי_מ11",
]
FIXED_RB = ["זיקוק_מ15"]
R9 = ["גלשן_מ01"]
R6 = ["מצנח_בסיס_מ11"]

# All 45 expected slugs (matching assets/tools/ current names)
ALL_SLUGS = [
    # M1
    "מצנח_מ01", "גלשן_מ01", "כנפיים_מ01",
    # M2
    "ברזנט_מ02", "פטיש_מ02", "אוהל_מ02",
    # M3
    "מפה_מ03", "משקפת_מ03", "מפתח_מ03",
    # M4
    "קרשים_מ04", "רתמה_מ04", "רובה_חבלים_מ04",
    # M5
    "פנס_עוצמתי_מ05", "רשת_מ05", "לפיד_מ05",
    # M6
    "גריקן_מ06", "ערכה_מ06", "אופניים_מ06",
    # M7
    "דגל_מ07", "פריסקופ_מ07", "לום_מ07",
    # M8
    "סולם_חבלים_מ08", "חבל_קשרים_מ08", "טפרי_טיפוס_מ08",
    # M9
    "שמן_מ09", "רב_כלי_מ09", "מבער_מ09",
    # M10
    "מצלמה_זעירה_מ10", "שמיכה_מ10", "קאטר_מ10",
    # M11
    "סנפלינג_מ11", "בנגי_מ11", "מצנח_בסיס_מ11",
    # M12
    "כרטיס_מ12", "מצלמה_פלאש_מ12", "לפיד_יד_מ12",
    # M13
    "סרגל_מ13", "מצפן_מ13", "רחפן_מ13",
    # M14
    "מטבעות_מ14", "תיבה_מ14", "כדור_בדולח_מ14",
    # M15
    "דגל_סיום_מ15", "מגאפון_מ15", "זיקוק_מ15",
]

assert len(ALL_SLUGS) == 45, f"expected 45 slugs, got {len(ALL_SLUGS)}"

report = []
for slug in ALL_SLUGS:
    if slug in FIXED_RA:
        src = REVIEW / f"{slug}_rA_final.png"
    elif slug in FIXED_RB:
        src = REVIEW / f"{slug}_rB_final.png"
    elif slug in R9:
        src = REVIEW / f"{slug}_r9_final.png"
    elif slug in R6:
        src = REVIEW / f"{slug}_r6_final.png"
    else:
        src = ASSETS / f"{slug}.png"

    dst = FINAL / f"{slug}.png"
    if not src.exists():
        report.append(f"MISSING SRC: {slug} -> {src}")
        continue
    shutil.copy2(src, dst)
    report.append(f"{slug:<30} <- {src.parent.name}/{src.name}")

print(f"Final folder: {FINAL}")
print(f"Files written: {len(list(FINAL.glob('*.png')))}/45")
print()
for line in report:
    print(line)
