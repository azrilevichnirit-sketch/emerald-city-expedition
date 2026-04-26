"""
M1 catch-pose alpha extraction.
Input:  pipeline/extracted_frames/M1_catch_raw.png  (climbing.mp4 @ t=1.0s)
Output: master_player/nirit_catch_M1_alpha.png

Steps:
1. Load RGB + create alpha
2. Chroma key: g>100 & g>r*1.4 & g>b*1.4  -> alpha=0
3. Decontaminate green spill on edges (any pixel where g > max(r,b) and alpha>0)
4. MinFilter(3) erode on alpha to kill 1-px green halos
5. Mask Veo watermark area (bottom-right ~50px) by sampling neighborhood
6. Save RGBA PNG
"""
from PIL import Image, ImageFilter
import numpy as np
from pathlib import Path

SRC = Path(r"C:\emerald\pipeline\extracted_frames\M1_catch_raw.png")
DST = Path(r"C:\emerald\master_player\nirit_catch_M1_alpha.png")
DST.parent.mkdir(parents=True, exist_ok=True)

img = Image.open(SRC).convert("RGBA")
arr = np.array(img)
h, w = arr.shape[:2]
print(f"loaded {SRC.name} -> {w}x{h}")

r = arr[..., 0].astype(np.int16)
g = arr[..., 1].astype(np.int16)
b = arr[..., 2].astype(np.int16)
a = arr[..., 3]

# 1) chroma key
green_mask = (g > 100) & (g > r * 1.4) & (g > b * 1.4)
a[green_mask] = 0
print(f"chroma keyed: {green_mask.sum()} px transparent ({green_mask.mean()*100:.1f}%)")

# 2) decontaminate green spill on remaining (edges) — pull g toward avg(r,b)
spill = (a > 0) & (g > r) & (g > b) & (g - np.maximum(r, b) > 8)
target = ((r + b) // 2).astype(np.int16)
new_g = np.where(spill, np.minimum(g, target + 6), g)
arr[..., 1] = np.clip(new_g, 0, 255).astype(np.uint8)
print(f"decontaminated: {spill.sum()} edge px")

# write back alpha
arr[..., 3] = a

# 3) MinFilter(3) erode on alpha
img2 = Image.fromarray(arr, "RGBA")
alpha_ch = img2.split()[3]
eroded = alpha_ch.filter(ImageFilter.MinFilter(3))
img2.putalpha(eroded)
arr = np.array(img2)
a = arr[..., 3]
print(f"eroded alpha (MinFilter 3)")

# 4) Veo watermark mask (bottom-right ~60px tall × 80px wide)
# Sample neighborhood color above the watermark and overpaint where text is darker
wm_y0, wm_y1 = h - 60, h - 5
wm_x0, wm_x1 = w - 90, w - 5
# locate dark/text pixels in that region (non-green watermark text on green bg)
region_a = a[wm_y0:wm_y1, wm_x0:wm_x1]
# pixels still opaque in watermark area = leftover text glyphs not killed by chroma
leftover = region_a > 0
arr[wm_y0:wm_y1, wm_x0:wm_x1, 3] = np.where(leftover, 0, region_a)
print(f"veo watermark cleared: {leftover.sum()} leftover px in BR corner")

# save
out = Image.fromarray(arr, "RGBA")
out.save(DST, "PNG")
print(f"saved -> {DST}")
print(f"final size: {DST.stat().st_size:,} bytes")
