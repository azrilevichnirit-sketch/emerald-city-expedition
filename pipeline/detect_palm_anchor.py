"""
anchor_calibrator — detect palm pixel of Nirit in master_player/nirit_alpha.png
Outputs:
  - master_player/nirit_alpha_palm_debug.png  (red dot overlay)
  - pipeline/palm_anchor_M1.json              (final coords)
"""
import json
import sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

SRC = Path(r"C:\emerald\master_player\nirit_alpha.png")
DEBUG = Path(r"C:\emerald\master_player\nirit_alpha_palm_debug.png")
OUT_JSON = Path(r"C:\emerald\pipeline\palm_anchor_M1.json")

img = Image.open(SRC).convert("RGBA")
W, H = img.size
print(f"image size: {W} x {H}")

arr = np.array(img)
r = arr[:, :, 0].astype(np.int16)
g = arr[:, :, 1].astype(np.int16)
b = arr[:, :, 2].astype(np.int16)
a = arr[:, :, 3]

# Skin-tone mask:
#   warm (R > B + 15), brighter red, alpha solid
skin = (
    (r > 140) & (r > g) & (g > b) &
    (r - b > 15) & (a > 200) &
    (r < 245) & (g < 220)  # exclude pure-white edge artifacts
)
print(f"skin pixels total: {int(skin.sum())}")

# Restrict to LOWER half (y > 50% of H = 672)
lower_half = skin.copy()
lower_half[: H // 2, :] = False
print(f"skin pixels in lower half: {int(lower_half.sum())}")

# Cluster via connected components
labeled, n_clusters = ndimage.label(lower_half)
print(f"clusters in lower half: {n_clusters}")

if n_clusters == 0:
    print("ERROR: no skin clusters in lower half")
    sys.exit(1)

# Cluster sizes
sizes = ndimage.sum(lower_half, labeled, range(1, n_clusters + 1))
order = np.argsort(sizes)[::-1]  # largest first

# List top 5 clusters with their centroids for inspection
print("\nTop clusters (lower half):")
top_info = []
for idx in order[:5]:
    cid = idx + 1
    size = int(sizes[idx])
    ys, xs = np.where(labeled == cid)
    cx = float(xs.mean())
    cy = float(ys.mean())
    top_info.append({"id": cid, "size": size, "cx": cx, "cy": cy})
    print(f"  cluster {cid}: size={size}, centroid=({cx:.0f}, {cy:.0f}), "
          f"pct=({cx / W * 100:.1f}%, {cy / H * 100:.1f}%)")

# Pick the LARGEST in lower half
best = top_info[0]
palm_x = int(round(best["cx"]))
palm_y = int(round(best["cy"]))

# Check second hand on RIGHT side of image (x > W/2): is there a sizeable cluster?
right_half_mask = (lower_half) & (np.indices(lower_half.shape)[1] > W // 2)
labeled_r, nr = ndimage.label(right_half_mask)
print(f"\nclusters on RIGHT half (lower): {nr}")
if nr > 0:
    sizes_r = ndimage.sum(right_half_mask, labeled_r, range(1, nr + 1))
    rmax = int(sizes_r.max())
    rid = int(np.argmax(sizes_r)) + 1
    ys, xs = np.where(labeled_r == rid)
    rcx, rcy = float(xs.mean()), float(ys.mean())
    print(f"  largest right-side cluster: size={rmax}, centroid=({rcx:.0f}, {rcy:.0f}), "
          f"pct=({rcx / W * 100:.1f}%, {rcy / H * 100:.1f}%)")
    # Use right-side hand only if it's at least 60% the size of the left-side pick
    if rmax >= 0.6 * best["size"]:
        print("  -> right-side cluster is competitive; using it instead.")
        palm_x, palm_y = int(round(rcx)), int(round(rcy))

palm_x_pct = palm_x / W * 100
palm_y_pct = palm_y / H * 100

# Draw debug image
debug_img = img.copy()
draw = ImageDraw.Draw(debug_img)
R = 20
draw.ellipse(
    (palm_x - R, palm_y - R, palm_x + R, palm_y + R),
    outline=(255, 0, 0, 255), width=4,
)
# Also crosshair
draw.line((palm_x - R - 10, palm_y, palm_x + R + 10, palm_y), fill=(255, 0, 0, 255), width=2)
draw.line((palm_x, palm_y - R - 10, palm_x, palm_y + R + 10), fill=(255, 0, 0, 255), width=2)
debug_img.save(DEBUG, "PNG")
print(f"\ndebug image saved: {DEBUG}")

prev = {"x": 47, "y": 60}
result = {
    "_agent": "anchor_calibrator",
    "_image": "master_player/nirit_alpha.png",
    "_image_size": [W, H],
    "palm_pixel": {"x": palm_x, "y": palm_y},
    "palm_pct": {"x": round(palm_x_pct, 2), "y": round(palm_y_pct, 2)},
    "detected_method": "skin_tone_lower_half_largest_cluster",
    "previous_value": prev,
    "detected_at": "2026-04-26",
}
OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
OUT_JSON.write_text(json.dumps(result, indent=2), encoding="utf-8")

print("\n=== FINAL ===")
print(f"palm pixel:  ({palm_x}, {palm_y})")
print(f"palm pct:    ({palm_x_pct:.2f}%, {palm_y_pct:.2f}%)")
print(f"prev pct:    ({prev['x']}%, {prev['y']}%)")
print(f"diff:        ({palm_x_pct - prev['x']:+.2f}%, {palm_y_pct - prev['y']:+.2f}%)")
print(f"json:        {OUT_JSON}")
