"""
Palm-anchor detector for M1 catch pose (both arms raised).
Input:  master_player/nirit_catch_M1_alpha.png (RGBA, transparent bg)
Output: pipeline/palm_anchor_M1_catch.json  -> {x, y, x_pct, y_pct, w, h}
        pipeline/palm_anchor_M1_catch_debug.png  -> red dot on detected palm

Strategy:
- Skin-tone mask: R>140 & R>G & G>B & alpha>200 & R-B>15
- Restrict search to UPPER half of bounding box of opaque body (where raised arms live)
- Pick TOPMOST skin cluster (highest reaching palm) — that's the catch hand
- Centroid of that top cluster -> palm pixel
"""
from PIL import Image, ImageDraw
import numpy as np
from pathlib import Path
import json
from scipy import ndimage

SRC = Path(r"C:\emerald\master_player\nirit_catch_M1_alpha.png")
OUT_JSON = Path(r"C:\emerald\pipeline\palm_anchor_M1_catch.json")
OUT_DEBUG = Path(r"C:\emerald\pipeline\palm_anchor_M1_catch_debug.png")

img = Image.open(SRC).convert("RGBA")
arr = np.array(img)
h, w = arr.shape[:2]
print(f"loaded {SRC.name} -> {w}x{h}")

r = arr[..., 0].astype(np.int16)
g = arr[..., 1].astype(np.int16)
b = arr[..., 2].astype(np.int16)
a = arr[..., 3]

# 1) overall opaque bbox -> determine "upper half"
opaque = a > 200
ys, xs = np.where(opaque)
if len(ys) == 0:
    raise RuntimeError("no opaque pixels — alpha extraction broken")
y_min, y_max = ys.min(), ys.max()
x_min, x_max = xs.min(), xs.max()
body_h = y_max - y_min
upper_cut = y_min + body_h // 2  # take only top half
print(f"opaque bbox: y={y_min}..{y_max} x={x_min}..{x_max}  upper_cut={upper_cut}")

# 2) skin-tone mask
skin = (
    (r > 140)
    & (r > g)
    & (g > b)
    & (a > 200)
    & (r - b > 15)
)
# limit to upper half
upper_mask = np.zeros_like(skin)
upper_mask[:upper_cut, :] = True
skin_upper = skin & upper_mask
print(f"skin px in upper half: {skin_upper.sum()}")

if skin_upper.sum() < 50:
    # fallback: relax thresholds
    skin = (r > 130) & (r > g - 5) & (g > b - 5) & (a > 200) & (r - b > 8)
    skin_upper = skin & upper_mask
    print(f"relaxed skin px: {skin_upper.sum()}")

# 3) connected components, pick the TOPMOST (smallest mean y) cluster of meaningful size
labeled, n_clusters = ndimage.label(skin_upper)
print(f"clusters found: {n_clusters}")

best = None  # (top_y, size, label, cy, cx)
for lbl in range(1, n_clusters + 1):
    ys_c, xs_c = np.where(labeled == lbl)
    size = len(ys_c)
    if size < 30:
        continue
    top_y = ys_c.min()
    cy = ys_c.mean()
    cx = xs_c.mean()
    if best is None or top_y < best[0]:
        best = (top_y, size, lbl, cy, cx)
        print(f"  cluster {lbl}: size={size} top_y={top_y} centroid=({cx:.0f},{cy:.0f})")

if best is None:
    raise RuntimeError("no skin cluster of size>=30 in upper half")

top_y, size, lbl, cy, cx = best
print(f"chosen cluster: lbl={lbl} size={size} top={top_y}")

# Refine: centroid of just the TOP THIRD of that cluster (the actual palm fingertips zone)
ys_c, xs_c = np.where(labeled == lbl)
y_top = ys_c.min()
y_bot = ys_c.max()
third_cut = y_top + (y_bot - y_top) // 3
top_third_idx = ys_c <= third_cut
palm_y = float(ys_c[top_third_idx].mean())
palm_x = float(xs_c[top_third_idx].mean())
print(f"refined palm pixel: ({palm_x:.1f}, {palm_y:.1f})")

x_pct = palm_x / w * 100
y_pct = palm_y / h * 100
print(f"palm pct: ({x_pct:.2f}%, {y_pct:.2f}%)")

# 4) write JSON
data = {
    "x": round(palm_x, 1),
    "y": round(palm_y, 1),
    "x_pct": round(x_pct, 2),
    "y_pct": round(y_pct, 2),
    "w": w,
    "h": h,
    "source_pose": "anim_climbing.mp4 @ t=1.0",
    "method": "skin-tone topmost cluster, top-third centroid",
}
OUT_JSON.write_text(json.dumps(data, indent=2), encoding="utf-8")
print(f"wrote {OUT_JSON}")

# 5) debug PNG with red dot
dbg = img.copy()
draw = ImageDraw.Draw(dbg)
rad = 14
draw.ellipse(
    [palm_x - rad, palm_y - rad, palm_x + rad, palm_y + rad],
    outline=(255, 0, 0, 255),
    width=4,
)
# crosshair
draw.line([palm_x - rad - 6, palm_y, palm_x + rad + 6, palm_y], fill=(255, 0, 0, 255), width=2)
draw.line([palm_x, palm_y - rad - 6, palm_x, palm_y + rad + 6], fill=(255, 0, 0, 255), width=2)
dbg.save(OUT_DEBUG, "PNG")
print(f"wrote {OUT_DEBUG}")
