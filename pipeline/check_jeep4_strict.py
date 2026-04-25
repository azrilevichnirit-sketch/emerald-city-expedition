"""STRICT full-image audit of the active smoking_jeep.png.

The standard leak check uses (G > R+30 AND G > B+30) which is too permissive.
This script:
  - Scans every pixel
  - Classifies each pixel as: bg_chroma / clean_subject / GREEN_FRINGE / GREEN_HALO
  - GREEN_FRINGE = on the boundary between subject and bg, slight green spill
  - GREEN_HALO   = pixel inside the subject that's clearly green-tinted

Also reports alpha channel state — if there's no alpha, the file CANNOT be
clean-composited over a different bg later, even if chroma is technically right.
"""
import sys
from PIL import Image

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PATH = r"C:\emerald\assets\scenery\smoking_jeep.png"
TARGET = (0, 177, 64)
TOL_BG = 12        # within +/- 12 of target = pure bg
TOL_FRINGE = 40    # within +/- 40 = fringe (anti-aliasing edge zone)


def classify(px):
    r, g, b = px[:3]
    # pure background
    if all(abs(c - t) <= TOL_BG for c, t in zip((r, g, b), TARGET)):
        return "bg"
    # near-bg fringe (anti-alias edge)
    if all(abs(c - t) <= TOL_FRINGE for c, t in zip((r, g, b), TARGET)):
        return "fringe"
    # subject pixel — is it suspiciously green?
    if g > r + 15 and g > b + 15 and g > 70:
        # how far IS it green-tinted?
        dom = min(g - r, g - b)
        if dom > 40:
            return "halo_strong"
        return "halo_weak"
    return "clean"


print("=" * 70)
print(f"STRICT FULL-IMAGE AUDIT: {PATH}")
print("=" * 70)

im = Image.open(PATH)
print(f"  mode={im.mode}  size={im.size}")
has_alpha = im.mode in ("RGBA", "LA") or "A" in im.mode
print(f"  alpha channel: {'YES' if has_alpha else 'NO  <-- !! cannot be composited cleanly'}")

im_rgb = im.convert("RGB")
w, h = im_rgb.size
px = im_rgb.load()

counts = {"bg": 0, "fringe": 0, "halo_weak": 0, "halo_strong": 0, "clean": 0}
total = w * h
for y in range(h):
    for x in range(w):
        counts[classify(px[x, y])] += 1

print("\nPixel breakdown:")
for k in ["bg", "fringe", "clean", "halo_weak", "halo_strong"]:
    pct = counts[k] / total * 100
    label = {
        "bg":          "pure chroma bg #00B140      ",
        "fringe":      "fringe (anti-alias edge)    ",
        "clean":       "clean subject               ",
        "halo_weak":   "halo_weak  (mild green tint)",
        "halo_strong": "halo_strong (BAD spill)     ",
    }[k]
    flag = ""
    if k == "halo_weak" and pct > 0.5:
        flag = " <-- green tint visible at scale"
    if k == "halo_strong" and pct > 0.05:
        flag = " <-- visible green spill on subject"
    if k == "fringe" and pct > 3:
        flag = " <-- thick edge, will look halo'd against any bg"
    print(f"  {label}  {pct:6.2f}%   {counts[k]:>9} px{flag}")

# Edge-pixel sample: what's the color of pixels right next to a bg pixel?
print("\nEdge sample — color of pixels touching the chroma boundary:")
edge_samples = []
for y in range(1, h - 1):
    for x in range(1, w - 1):
        c = classify(px[x, y])
        if c == "bg":
            continue
        # check if any 4-neighbor is bg
        if any(classify(px[x + dx, y + dy]) == "bg"
               for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]):
            edge_samples.append(px[x, y])
            if len(edge_samples) >= 2000:
                break
    if len(edge_samples) >= 2000:
        break

if edge_samples:
    avg = tuple(sum(c[i] for c in edge_samples) // len(edge_samples) for i in range(3))
    print(f"  sampled {len(edge_samples)} edge pixels")
    print(f"  avg edge color = {avg}")
    edge_lean = avg[1] - max(avg[0], avg[2])
    if edge_lean > 8:
        print(f"  green-lean = +{edge_lean}  <-- edges biased green, will halo")
    elif edge_lean > 3:
        print(f"  green-lean = +{edge_lean}  (mild — may be acceptable)")
    else:
        print(f"  green-lean = {edge_lean}  (clean)")

print("=" * 70)
