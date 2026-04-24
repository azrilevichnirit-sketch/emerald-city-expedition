"""Shutterstock Post-Processor — rembg + composite on #00B140 green screen.

Runs AFTER shutterstock_agent.py has filled pipeline/staging/shutterstock/
with raw licensed JPGs.

For each JPG:
  1. Load.
  2. Run rembg (U2Net) to isolate the subject (alpha channel).
  3. Composite onto flat #00B140 (the Builder's chroma key target).
  4. Save PNG to pipeline/staging/shutterstock/processed/<category>/<slug>.png.

Why rembg for BOTH scenery and tools:
  - Tools: "isolated white background" photos are close to white but rarely
    pure white (anti-alias halos, subtle gradients). Chroma-keying by color
    leaves halos; rembg gives clean alpha.
  - Scenery: real photos have no alpha; rembg is the only realistic way to
    cut them.

Idempotent: skips items already in processed/ with non-zero size.

Usage:
  python pipeline/shutterstock_postprocess.py           # process everything
  python pipeline/shutterstock_postprocess.py scenery   # only scenery
  python pipeline/shutterstock_postprocess.py tools     # only tools
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from PIL import Image  # noqa: E402
from rembg import remove, new_session  # noqa: E402

PROJECT = Path(__file__).resolve().parent.parent
STAGING = PROJECT / "pipeline" / "staging" / "shutterstock"
PROCESSED = STAGING / "processed"
PROCESSED.mkdir(parents=True, exist_ok=True)
(PROCESSED / "scenery").mkdir(exist_ok=True)
(PROCESSED / "tools").mkdir(exist_ok=True)

GREEN = (0, 177, 64)  # #00B140 chroma target

# u2net is the general-purpose model; fine for both photos and studio shots.
_SESSION = None

def session():
    global _SESSION
    if _SESSION is None:
        _SESSION = new_session("u2net")
    return _SESSION


def process_one(src: Path, dst: Path) -> tuple[int, int]:
    """Returns (input_bytes, output_bytes). dst is a .png path."""
    img = Image.open(src).convert("RGBA")
    cut = remove(img, session=session())  # RGBA with alpha
    # Composite onto flat green
    bg = Image.new("RGBA", cut.size, GREEN + (255,))
    bg.alpha_composite(cut)
    # Save as RGB PNG (no alpha — Builder keys against #00B140)
    bg.convert("RGB").save(dst, "PNG", optimize=True)
    return src.stat().st_size, dst.stat().st_size


def process_category(cat: str) -> dict:
    src_dir = STAGING / cat
    dst_dir = PROCESSED / cat
    jpgs = sorted(src_dir.glob("*.jpg"))
    stats = {"category": cat, "total": len(jpgs), "done": 0, "skip": 0,
             "fail": 0, "items": []}
    if not jpgs:
        print(f"[{cat}] no source JPGs in {src_dir}")
        return stats

    print(f"[{cat}] {len(jpgs)} items from {src_dir}")
    for i, src in enumerate(jpgs, 1):
        dst = dst_dir / f"{src.stem}.png"
        if dst.exists() and dst.stat().st_size > 0:
            print(f"  [{i:02}/{len(jpgs)}] {src.name}: skip (already processed)")
            stats["skip"] += 1
            continue
        t0 = time.time()
        try:
            in_b, out_b = process_one(src, dst)
            dt = round(time.time() - t0, 1)
            print(f"  [{i:02}/{len(jpgs)}] {src.name}: -> {dst.name} "
                  f"({in_b//1024}kb->{out_b//1024}kb, {dt}s)")
            stats["done"] += 1
            stats["items"].append({"slug": src.stem, "status": "done",
                                   "elapsed_s": dt})
        except Exception as e:
            print(f"  [{i:02}/{len(jpgs)}] {src.name}: FAIL {type(e).__name__}: {e}")
            stats["fail"] += 1
            stats["items"].append({"slug": src.stem, "status": "fail",
                                   "error": f"{type(e).__name__}: {e}"})
    return stats


def main(argv: list[str]) -> int:
    args = argv[1:]
    cats = ["scenery", "tools"] if not args else [args[0]]
    print("Shutterstock Post-Process: rembg + chroma-composite on #00B140")
    print("=" * 60)
    all_stats = []
    for cat in cats:
        all_stats.append(process_category(cat))
    print("\n" + "=" * 60)
    print("POST-PROCESS COMPLETE")
    for s in all_stats:
        print(f"  {s['category']}: done={s['done']} skip={s['skip']} "
              f"fail={s['fail']} of total={s['total']}")
    print(f"Output root: {PROCESSED}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
