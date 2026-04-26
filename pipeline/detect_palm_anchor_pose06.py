"""
anchor_calibrator — pose06 (catching, right hand raised)
Detect raised palm in upper-left quadrant.
"""
import json
import sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

SRC = Path(r"C:\emerald\master_player\nirit_pose06_alpha.png")
DEBUG = Path(r"C:\emerald\master_player\nirit_pose06_palm_debug.png")
OUT_JSON = Path(r"C:\emerald\pipeline\palm_anchor_pose06.json")

img = Image.open(SRC).convert("RGBA")
W, H = img.size
print(f"image size: {W} x {H}")

arr = np.array(img)
r = arr[:, :, 0].astype(np.int16)
g = arr[:, :, 1].astype(np.int16)
b = arr[:, :, 2].astype(np.int16)
a = arr[:, :, 3]

# Skin-tone mask (same as base detector)
skin = (
    (r > 140) & (r > g) & (g > b) &
    (r - b > 15) & (a > 200) &
    (r < 245) & (g < 220)
)
print(f"skin pixels total: {int(skin.sum())}")

# Restrict to UPPER-LEFT quadrant (x < W/2, y < H/2)
quad = skin.copy()
quad[H // 2 :, :] = False  # zero out lower half
quad[:, W // 2 :] = False  # zero out right half
print(f"skin pixels in upper-left quadrant: {int(quad.sum())}")

labeled, n_clusters = ndimage.label(quad)
print(f"clusters in upper-left: {n_clusters}")

if n_clusters == 0:
    print("ERROR: no skin clusters in upper-left quadrant")
    sys.exit(1)

sizes = ndimage.sum(quad, labeled, range(1, n_clusters + 1))
order = np.argsort(sizes)[::-1]

print("\nTop clusters (upper-left):")
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

# The face is also a skin cluster — but the palm should be FURTHER LEFT
# than the face. Strategy: largest cluster is usually the face/forearm
# combined; we need the LEFTMOST significant cluster, OR if the largest
# cluster is wide, take its leftmost portion.
# First try: pick the cluster whose centroid is furthest to the LEFT
# among clusters that are at least 25% the size of the largest.
largest_size = top_info[0]["size"]
candidates = [c for c in top_info if c["size"] >= 0.25 * largest_size]
candidates.sort(key=lambda c: c["cx"])  # leftmost first
best = candidates[0]
print(f"\nselected (leftmost among major clusters): cluster {best['id']}, "
      f"size={best['size']}, centroid=({best['cx']:.0f}, {best['cy']:.0f})")

palm_x = int(round(best["cx"]))
palm_y = int(round(best["cy"]))

# Use cluster centroid as the palm anchor (palm center, not fingertip).
# The cluster is the raised hand+wrist; centroid lands on palm/wrist area.
# Refine: take the LEFTMOST 35% of cluster (the hand portion, excluding
# any forearm pixels that bleed in) and use that centroid.
ys, xs = np.where(labeled == best["id"])
x_threshold = np.percentile(xs, 35)
mask_tip = xs <= x_threshold
tip_x = float(xs[mask_tip].mean())
tip_y = float(ys[mask_tip].mean())
print(f"palm refinement (leftmost 35%): ({tip_x:.0f}, {tip_y:.0f})")
palm_x = int(round(tip_x))
palm_y = int(round(tip_y))

palm_x_pct = palm_x / W * 100
palm_y_pct = palm_y / H * 100

# Debug image with red dot
debug_img = img.copy()
draw = ImageDraw.Draw(debug_img)
R = 20
draw.ellipse(
    (palm_x - R, palm_y - R, palm_x + R, palm_y + R),
    fill=(255, 0, 0, 255), outline=(255, 255, 255, 255), width=3,
)
draw.line((palm_x - R - 10, palm_y, palm_x + R + 10, palm_y), fill=(255, 0, 0, 255), width=2)
draw.line((palm_x, palm_y - R - 10, palm_x, palm_y + R + 10), fill=(255, 0, 0, 255), width=2)
debug_img.save(DEBUG, "PNG")
print(f"\ndebug image saved: {DEBUG}")

result = {
    "_agent": "anchor_calibrator",
    "_image": "master_player/nirit_pose06_alpha.png",
    "_image_size": [W, H],
    "palm_pixel": {"x": palm_x, "y": palm_y},
    "palm_pct": {"x": round(palm_x_pct, 2), "y": round(palm_y_pct, 2)},
    "detected_method": "skin_tone_upper_left_largest_cluster",
    "pose": "catching_hand_raised",
    "detected_at": "2026-04-26",
}
OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
OUT_JSON.write_text(json.dumps(result, indent=2), encoding="utf-8")

print("\n=== FINAL ===")
print(f"palm pixel:  ({palm_x}, {palm_y})")
print(f"palm pct:    ({palm_x_pct:.2f}%, {palm_y_pct:.2f}%)")
print(f"json:        {OUT_JSON}")
