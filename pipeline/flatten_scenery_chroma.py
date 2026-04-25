"""Flatten the green background of every scenery PNG to exact #00B140.

Problem: Nano Banana (v1 and v2) sometimes renders "studio-lit" green —
a lighter green in the center fading to darker green / near-black at the
edges. That vignette breaks chroma-key: the darker-edge pixels won't be
keyed out the same way as center pixels, so a dark halo survives compositing.

Fix: deterministic pixel pass. For every pixel, if it is clearly
green-dominant (G well above R and B), clamp it to exactly (0, 177, 64)
= #00B140. Prop pixels (never green-dominant) are untouched.

Runs AFTER rebackground_scenery_v2.py. Overwrites assets/scenery/*.png.
Originals are already preserved in assets/scenery/_orig_backup/ and the
last Nano Banana output is preserved in assets/scenery/_v2_backup/ (this
script writes there on first touch).
"""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from PIL import Image  # noqa: E402

PROJECT = Path(__file__).resolve().parent.parent
SCENERY = PROJECT / "assets" / "scenery"
V2_BACKUP = SCENERY / "_v2_backup"
V2_BACKUP.mkdir(exist_ok=True)

# Pure green target
TARGET = (0, 177, 64)

# Classification thresholds.
# A pixel is "green-dominant background" if:
#   G - max(R, B) >= GREEN_LEAD   (green clearly leads)
#   AND G >= MIN_G                (not nearly-black)
# Tuned to catch both bright center (#00C04A ish) and dark edges (#002010 ish)
# while NOT catching muddy green-brown jeep paint (where R and B are close to G).
GREEN_LEAD = 15     # G must exceed the stronger of R/B by at least this much
MIN_G = 25          # below this, it's basically black — leave alone (edge case)


def flatten(path: Path) -> tuple[int, int]:
    """Return (changed_px, total_px)."""
    img = Image.open(path).convert("RGBA")
    px = img.load()
    w, h = img.size
    changed = 0
    total = w * h
    tr, tg, tb = TARGET
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a == 0:
                continue
            lead = g - max(r, b)
            if lead >= GREEN_LEAD and g >= MIN_G:
                px[x, y] = (tr, tg, tb, a)
                changed += 1
    img.save(path, "PNG")
    return changed, total


def main():
    files = sorted(SCENERY.glob("*.png"))
    print(f"Flatten chroma: {len(files)} scenery PNGs")
    print(f"Target: rgb{TARGET} = #00B140")
    print(f"Rule: pixel is bg if G - max(R,B) >= {GREEN_LEAD} and G >= {MIN_G}")
    print("-" * 60)

    for i, path in enumerate(files, 1):
        # Back up the Nano Banana output before we overwrite
        backup = V2_BACKUP / path.name
        if not backup.exists():
            backup.write_bytes(path.read_bytes())

        changed, total = flatten(path)
        pct = 100.0 * changed / total
        print(f"[{i:02}/{len(files)}] {path.name}: "
              f"{changed:,}/{total:,} px flattened ({pct:.1f}%)")

    print("\n" + "=" * 60)
    print("CHROMA FLATTEN COMPLETE")
    print(f"Originals:     {SCENERY / '_orig_backup'}")
    print(f"Nano v2 out:   {V2_BACKUP}")
    print(f"Final (flat):  {SCENERY}")


if __name__ == "__main__":
    main()
