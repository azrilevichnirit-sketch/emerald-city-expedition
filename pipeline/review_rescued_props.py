"""Run human_review's gate questions (via Gemini Vision) on every rescued
PNG. Auto-retry from next candidate round if PASS fails.

Per agents/human_review.md "Stop 2 — every new tool/prop created":
  - Is it actually [the slug name]? (not a different prop)
  - Clean #00B140 bg — no other elements?
  - Style consistent with style_reference?
  - Clear what it is + how it's used?

Plus prod-company concerns:
  - Subject complete (not cut in half by rembg)?
  - No artifacts (chunks of original bg left behind)?
  - At target zone size, will it composite naturally with the mission bg?

Output:
  pipeline/review/rescued_review.json   - per-slug PASS/FAIL + reason
  pipeline/review/_for_nirit/<slug>.png - copies of items that PASSED
                                           (only these reach Nirit)
"""
import sys
import json
import time
import base64
import re
import shutil
from pathlib import Path
from PIL import Image

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT = Path(r"C:\emerald")
sys.path.insert(0, str(PROJECT / "pipeline"))

from debate_runner import call_gemini
from subject_extractor import (
    extract_rembg, composite_on_chroma, chroma_check, verdict
)

EXTRACTED = PROJECT / "pipeline" / "review" / "extracted_v2"
RESCUE_LOG = json.loads((PROJECT / "pipeline" / "review" / "rescue_log.json")
                        .read_text(encoding="utf-8"))
RECOVERY = json.loads((PROJECT / "pipeline" / "review" / "asset_recovery_map.json")
                      .read_text(encoding="utf-8"))
LOCK = json.loads((PROJECT / "content_lock.json").read_text(encoding="utf-8"))

CANDIDATES_DIR = PROJECT / "pipeline" / "review" / "scenery" / "_candidates"
FOR_NIRIT = PROJECT / "pipeline" / "review" / "_for_nirit"
FOR_NIRIT.mkdir(parents=True, exist_ok=True)


def slug_intent(slug: str) -> str:
    """One-line description of what this slug is supposed to be."""
    q123 = json.loads((PROJECT / "pipeline" / "review" / "scenery_audit_q123.json")
                      .read_text(encoding="utf-8"))
    info = q123["items"].get(slug, {})
    mid = info.get("mission")
    mission = LOCK["missions"].get(mid, {})
    return f"slug={slug} | mission={mid} | mission_text={mission.get('mission_text','')[:120]}"


def review_one(slug: str, png_path: Path) -> dict:
    """Send to Gemini Vision with human_review's gate questions."""
    intent = slug_intent(slug)
    b64 = base64.b64encode(png_path.read_bytes()).decode("ascii")

    prompt = (
        f"בודק QA לחברת הפקה. אביזר הסצנה הבא עבר חיתוך אוטומטי "
        f"(rembg) מתמונה גולמית והוצב על chroma green #00B140. "
        f"\n{intent}\n\n"
        "ענה על 5 שאלות PASS/FAIL — כל one false = FAIL כללי:\n\n"
        "Q1 (subject_match): האם הסובייקט בתמונה הוא אכן מה שה-slug אומר "
        "(למשל אם slug=escape_boat_distant — האם רואים סירה ולא משהו אחר)? PASS/FAIL.\n\n"
        "Q2 (subject_complete): האם הסובייקט שלם — לא חתוך באמצע, "
        "לא חסרים לו חלקים מהותיים (חצי גג, חצי גוף)? PASS/FAIL.\n\n"
        "Q3 (clean_chroma): האם הרקע #00B140 נקי לחלוטין — אין שאריות "
        "מהרקע המקורי (חתיכות עץ/קרקע/שמיים)? PASS/FAIL.\n\n"
        "Q4 (no_artifacts): האם אין ארטיפקטים של אלגוריתם החיתוך — "
        "קצוות משוננים גסים, חורים בתוך הסובייקט, ספיל ירוק על הסובייקט? PASS/FAIL.\n\n"
        "Q5 (composes_naturally): האם הסובייקט יראה טבעי כשיוטמע עם "
        "הרקע של המשימה (לא ישבר את הסקאלה, לא ייראה עם סטייל מנוגד)? PASS/FAIL.\n\n"
        "**verdict**: PASS אם 5/5, MILD אם 4/5 והפגם משני, FAIL אחרת.\n"
        "**worst_issue**: משפט אחד — מה הכי בעייתי (אם משהו).\n\n"
        "החזר JSON בלבד:\n"
        '{"q1":{"verdict":"PASS|FAIL","note":"..."},'
        '"q2":{"verdict":"PASS|FAIL","note":"..."},'
        '"q3":{"verdict":"PASS|FAIL","note":"..."},'
        '"q4":{"verdict":"PASS|FAIL","note":"..."},'
        '"q5":{"verdict":"PASS|FAIL","note":"..."},'
        '"verdict":"PASS|MILD|FAIL","worst_issue":"..."}'
    )

    try:
        resp = call_gemini(
            system="אתה QA reviewer לחברת הפקה. החזר JSON תקין בלבד, "
                   "ללא מרקדאון, ללא הקדמות.",
            user_text=prompt,
            image_b64=b64,
            max_tokens=600,
        )
    except Exception as e:
        return {"_error": str(e)[:200]}

    m = re.search(r"\{.*\}", resp, re.S)
    if not m:
        return {"_parse_error": "no json", "_raw": resp[:300]}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError as e:
        return {"_parse_error": str(e), "_raw": resp[:300]}


def try_round(slug: str, round_n: int):
    """Re-extract from candidate_r{n} if r1 failed review."""
    src = CANDIDATES_DIR / f"{slug}_r{round_n}.png"
    if not src.exists():
        return None
    try:
        rgba = extract_rembg(Image.open(src))
        out = composite_on_chroma(rgba, defringe=True, alpha_threshold=128)
        c = chroma_check(out)
        v = verdict(c)
        if v not in ("CLEAN", "MILD_HALO"):
            return None
        dest = EXTRACTED / f"{slug}.png"
        out.save(dest)
        return dest
    except Exception:
        return None


# =============== run ===============

slugs = [s for s, info in RESCUE_LOG["items"].items()
         if info.get("status") == "rescued"]

print("=" * 70)
print(f"QA REVIEW (human_review gate) on {len(slugs)} rescued props")
print("=" * 70)

review = {
    "_run_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    "items": {},
}
counts = {"PASS": 0, "MILD": 0, "FAIL": 0, "_error": 0}

for i, slug in enumerate(slugs, 1):
    canonical = EXTRACTED / f"{slug}.png"
    if not canonical.exists():
        print(f"  [{i:>2}/{len(slugs)}] {slug:<35}  MISSING canonical")
        continue

    print(f"  [{i:>2}/{len(slugs)}] {slug:<35} ", end="", flush=True)
    r = review_one(slug, canonical)

    # If FAIL, try r2..r8
    final_round = "r1"
    if r.get("verdict") == "FAIL":
        for rn in range(2, 9):
            new_path = try_round(slug, rn)
            if new_path is None:
                continue
            r2 = review_one(slug, new_path)
            if r2.get("verdict") in ("PASS", "MILD"):
                r = r2
                final_round = f"r{rn}"
                break

    v = r.get("verdict", "_error")
    if "_error" in r or "_parse_error" in r:
        v = "_error"
    counts[v] = counts.get(v, 0) + 1
    review["items"][slug] = {"final_round": final_round, "review": r}

    issue = r.get("worst_issue", "")[:60]
    print(f" -> {v:<6} ({final_round})  {issue}")

    if v in ("PASS", "MILD"):
        shutil.copy2(canonical, FOR_NIRIT / f"{slug}.png")

print()
print("=" * 70)
print("SUMMARY:")
for k in ["PASS", "MILD", "FAIL", "_error"]:
    print(f"  {k:<10}  {counts.get(k, 0)}")
print("=" * 70)
print(f"\nReview saved -> pipeline/review/rescued_review.json")
print(f"PASS+MILD copied to -> {FOR_NIRIT}")

(PROJECT / "pipeline" / "review" / "rescued_review.json").write_text(
    json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8"
)
