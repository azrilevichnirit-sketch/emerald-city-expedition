"""STRICT 2nd-pass QA on the 13 integrated rescued props.

Why: the first QA gate (review_rescued_props.py) had FALSE POSITIVES.
Nirit attached 5 screenshots of integrated images that are visually broken —
thin slivers, isolated rocks, disconnected fragments, cropped waterfalls.

This pass is harder:
  1) PIXEL TEST   — count non-chroma area. <5% = sliver/fragment, auto-FAIL.
                    >85% = barely-cropped image, suspicious.
  2) NAMING TEST  — Gemini Vision: "in 2-5 English words, what is this?
                    If unclear/fragment/blob, say UNCLEAR."
                    No slug hint given. Honest open-ended.
  3) SLUG-MATCH   — Given the slug intent, "would a viewer at-a-glance
                    identify this as [intent]?" PASS only if obvious.

Verdict = PASS only if all 3 pass. STRICT_FAIL otherwise.

Output: pipeline/review/strict_qa_pass2.json
        + recommendation per slug: KEEP / REVERT_TO_V3_BACKUP
"""
import sys
import json
import time
import base64
import re
from pathlib import Path
from PIL import Image

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT = Path(r"C:\emerald")
sys.path.insert(0, str(PROJECT / "pipeline"))

from debate_runner import call_gemini

SCENERY = PROJECT / "assets" / "scenery"
INTEG_LOG = json.loads((PROJECT / "pipeline" / "review" / "integration_log.json")
                       .read_text(encoding="utf-8"))
LOCK = json.loads((PROJECT / "content_lock.json").read_text(encoding="utf-8"))
Q123 = json.loads((PROJECT / "pipeline" / "review" / "scenery_audit_q123.json")
                  .read_text(encoding="utf-8"))

CHROMA = (0, 177, 64)


def subject_area_pct(path: Path) -> float:
    im = Image.open(path).convert("RGB")
    w, h = im.size
    px = im.load()
    non_bg = 0
    total = 0
    step = max(1, min(w, h) // 400)  # sample grid for speed
    for y in range(0, h, step):
        for x in range(0, w, step):
            total += 1
            r, g, b = px[x, y]
            if not all(abs(c - t) <= 18 for c, t in zip((r, g, b), CHROMA)):
                non_bg += 1
    return round(100.0 * non_bg / max(1, total), 2)


def slug_intent(slug: str) -> str:
    info = Q123["items"].get(slug, {})
    mid = info.get("mission")
    mission = LOCK["missions"].get(mid, {})
    return f"mission={mid}: {mission.get('mission_text', '')[:140]}"


def naming_test(png_path: Path) -> dict:
    """No slug hint. Open-ended naming."""
    b64 = base64.b64encode(png_path.read_bytes()).decode("ascii")
    prompt = (
        "Look at this image. The background is solid green chroma (#00B140) "
        "and the subject is in the center.\n\n"
        "Answer two questions HONESTLY in JSON:\n"
        "1. 'name': In 2-5 English words, what is the subject? "
        "If it is just a fragment, a sliver, a small blob, disconnected pieces, "
        "or anything you cannot identify with certainty, answer exactly: UNCLEAR.\n"
        "2. 'confidence': How confident are you? high / medium / low.\n\n"
        "Be very critical. If a child looking at this would not know what it is, "
        "say UNCLEAR.\n\n"
        'Return JSON only: {"name":"...","confidence":"high|medium|low"}'
    )
    try:
        resp = call_gemini(
            system="You are a strict QA reviewer. Honest, blunt, no hedging.",
            user_text=prompt,
            image_b64=b64,
            max_tokens=200,
        )
    except Exception as e:
        return {"_error": str(e)[:200]}
    m = re.search(r"\{.*\}", resp, re.S)
    if not m:
        return {"_parse_error": resp[:200]}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError as e:
        return {"_parse_error": str(e), "_raw": resp[:200]}


def slug_match_test(png_path: Path, slug: str, intent: str) -> dict:
    """Now reveal the slug, ask if image matches."""
    b64 = base64.b64encode(png_path.read_bytes()).decode("ascii")
    prompt = (
        f"This image is supposed to be a scenery prop named '{slug}'. "
        f"Context: {intent}\n\n"
        "Question: would a casual viewer (not a designer, just a normal player) "
        f"at-a-glance recognize this image as '{slug}'?\n\n"
        "Be STRICT. PASS only if the answer is obvious. "
        "If the image shows just a fragment, sliver, isolated piece, or something "
        "ambiguous, answer FAIL.\n\n"
        'Return JSON only: {"verdict":"PASS|FAIL","reason":"one short sentence"}'
    )
    try:
        resp = call_gemini(
            system="You are a strict QA reviewer for a production company. "
                   "False positives ruin the demo. When in doubt, FAIL.",
            user_text=prompt,
            image_b64=b64,
            max_tokens=200,
        )
    except Exception as e:
        return {"_error": str(e)[:200]}
    m = re.search(r"\{.*\}", resp, re.S)
    if not m:
        return {"_parse_error": resp[:200]}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError as e:
        return {"_parse_error": str(e), "_raw": resp[:200]}


# ============== run ==============

slugs = list(INTEG_LOG["items"].keys())
print("=" * 78)
print(f"STRICT 2nd-pass QA on {len(slugs)} integrated rescued props")
print("=" * 78)

results = {"_run_at": time.strftime("%Y-%m-%d %H:%M:%S"), "items": {}}
keep, revert = [], []

for i, slug in enumerate(slugs, 1):
    path = SCENERY / f"{slug}.png"
    print(f"\n[{i:>2}/{len(slugs)}] {slug}")
    if not path.exists():
        print("    MISSING file")
        continue

    area = subject_area_pct(path)
    print(f"    subject_area: {area}%")

    intent = slug_intent(slug)
    name_r = naming_test(path)
    print(f"    naming:       {name_r}")

    match_r = slug_match_test(path, slug, intent)
    print(f"    slug_match:   {match_r}")

    # final verdict
    fail_reasons = []
    if area < 5.0:
        fail_reasons.append(f"sliver (area={area}%)")
    if area > 92.0:
        fail_reasons.append(f"almost-full-frame (area={area}%) — likely uncropped")
    nm = name_r.get("name", "")
    if nm == "UNCLEAR" or name_r.get("confidence") == "low":
        fail_reasons.append(f"naming={nm}/{name_r.get('confidence')}")
    if match_r.get("verdict") == "FAIL":
        fail_reasons.append(f"slug_match=FAIL: {match_r.get('reason', '')[:60]}")
    if "_error" in name_r or "_parse_error" in name_r:
        fail_reasons.append("naming_test errored")
    if "_error" in match_r or "_parse_error" in match_r:
        fail_reasons.append("slug_match errored")

    if fail_reasons:
        decision = "REVERT_TO_V3_BACKUP"
        revert.append(slug)
    else:
        decision = "KEEP"
        keep.append(slug)

    print(f"    -> {decision}  {('; '.join(fail_reasons)) if fail_reasons else 'all checks passed'}")

    results["items"][slug] = {
        "area_pct": area,
        "naming": name_r,
        "slug_match": match_r,
        "fail_reasons": fail_reasons,
        "decision": decision,
    }

print()
print("=" * 78)
print(f"KEEP   ({len(keep)}): {', '.join(keep) if keep else '(none)'}")
print(f"REVERT ({len(revert)}): {', '.join(revert) if revert else '(none)'}")
print("=" * 78)

results["_keep"] = keep
results["_revert"] = revert
(PROJECT / "pipeline" / "review" / "strict_qa_pass2.json").write_text(
    json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(f"\nsaved -> pipeline/review/strict_qa_pass2.json")
