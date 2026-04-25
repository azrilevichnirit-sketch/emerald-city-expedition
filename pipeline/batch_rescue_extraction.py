"""Batch rescue: try to extract a CLEAN chroma cutout for every prop that
currently fails chroma. Sources tried in order:
  1) old/scenery/<slug>.png
  2) old/assets/...something matching slug
  3) candidate r1..rN from pipeline/review/scenery/_candidates/
  4) _v2_backup/<slug>.png
  5) _orig_backup/<slug>.png

For each prop, pick the first source that yields a CLEAN or MILD_HALO output.

Output:
  - rescued PNGs in pipeline/review/extracted_v2/<slug>.png
  - rescue_log.json  with what was tried + final state per slug
"""
import sys
import json
import time
from pathlib import Path
from PIL import Image

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT = Path(r"C:\emerald")
sys.path.insert(0, str(PROJECT / "pipeline"))

from subject_extractor import (
    extract_rembg,
    composite_on_chroma,
    chroma_check,
    verdict,
)

OUT = PROJECT / "pipeline" / "review" / "extracted_v2"
OUT.mkdir(parents=True, exist_ok=True)
RECOVERY = json.loads((PROJECT / "pipeline" / "review" / "asset_recovery_map.json")
                     .read_text(encoding="utf-8"))

CANDIDATES_DIR = PROJECT / "pipeline" / "review" / "scenery" / "_candidates"
ORIG = PROJECT / "assets" / "scenery" / "_orig_backup"
V2 = PROJECT / "assets" / "scenery" / "_v2_backup"
OLD_SCENERY = Path(r"C:\Users\azril\OneDrive\Desktop\fincail_game\old\scenery")
OLD_TOPRAH = Path(r"C:\Users\azril\OneDrive\Desktop\fincail_game\old\assets\תפאורה\new")


def find_sources(slug: str):
    sources = []
    p1 = OLD_SCENERY / f"{slug}.png"
    if p1.exists():
        sources.append(("old/scenery", p1))
    p2 = OLD_TOPRAH / f"{slug}.png"
    if p2.exists():
        sources.append(("old/assets/תפאורה", p2))
    # candidate rounds
    for r in range(1, 9):
        pc = CANDIDATES_DIR / f"{slug}_r{r}.png"
        if pc.exists():
            sources.append((f"candidate_r{r}", pc))
    # backups
    pv2 = V2 / f"{slug}.png"
    if pv2.exists():
        sources.append(("_v2_backup", pv2))
    porig = ORIG / f"{slug}.png"
    if porig.exists():
        sources.append(("_orig_backup", porig))
    return sources


def try_extract(src_path: Path, dest_path: Path):
    src = Image.open(src_path)
    rgba = extract_rembg(src)
    out = composite_on_chroma(rgba, defringe=True, alpha_threshold=128)
    out.save(dest_path)
    c = chroma_check(out)
    return verdict(c), c


# Slugs to attempt rescue: anything currently FAKE_CLEAN, NO_CHROMA, DIRTY,
# or NO_SUBJECT. Skip already-CLEAN.
target_slugs = []
for slug, info in RECOVERY["items"].items():
    chroma_state = info.get("chroma_state")
    if chroma_state in ("CLEAN", "MILD_HALO"):
        continue
    target_slugs.append(slug)

print("=" * 80)
print(f"BATCH RESCUE — attempting extraction on {len(target_slugs)} props")
print("=" * 80)

log = {
    "_run_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    "_target_count": len(target_slugs),
    "items": {},
}

success_count = 0
for i, slug in enumerate(target_slugs, 1):
    sources = find_sources(slug)
    if not sources:
        print(f"  [{i:>2}/{len(target_slugs)}]  {slug:<35}  NO SOURCES FOUND")
        log["items"][slug] = {"status": "no_sources_found"}
        continue

    best = None
    tried = []
    for src_label, src_path in sources:
        dest = OUT / f"{slug}__{src_label.replace('/', '_').replace('תפאורה', 'tofora')}.png"
        try:
            v, c = try_extract(src_path, dest)
        except Exception as e:
            tried.append({"source": src_label, "error": str(e)[:120]})
            continue
        tried.append({"source": src_label, "verdict": v, "chroma": c})
        if v in ("CLEAN", "MILD_HALO"):
            best = (src_label, v, c, dest)
            break

    if best:
        # also save final to canonical name
        canonical = OUT / f"{slug}.png"
        Image.open(best[3]).save(canonical)
        success_count += 1
        print(f"  [{i:>2}/{len(target_slugs)}]  {slug:<35}  -> {best[1]:<10} (from {best[0]})")
        log["items"][slug] = {
            "status": "rescued",
            "source": best[0],
            "verdict": best[1],
            "chroma": best[2],
            "canonical": str(canonical),
            "all_attempts": tried,
        }
    else:
        print(f"  [{i:>2}/{len(target_slugs)}]  {slug:<35}  FAILED ({len(tried)} attempts)")
        log["items"][slug] = {"status": "failed", "all_attempts": tried}

print()
print("=" * 80)
print(f"RESCUED: {success_count} / {len(target_slugs)}")
print("=" * 80)

LOG_PATH = PROJECT / "pipeline" / "review" / "rescue_log.json"
LOG_PATH.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\nlog -> {LOG_PATH}")
print(f"images -> {OUT}")
