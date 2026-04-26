"""visual_editor agent v2: extract master_player using flood fill + threshold.

The original PNG has a TEXTURED off-white bg (not pure white). Pure threshold
catches the brightest pixels but misses the textured areas. Flood fill from
the 4 corners catches anything CONNECTED to the edges with brightness > 180,
which is the actual character cutout boundary.
"""
import os, shutil
from PIL import Image, ImageFilter, ImageDraw
import numpy as np
from collections import deque

SRC = r"C:\emerald\master_player\niritazr_female_tropical_expedition_researcher_age_30_athleti_d44318aa-1ac0-43df-aa05-4411aaa85c98_0.png"
BACKUP = r"C:\emerald\master_player\nirit_master.before_alpha_extract.png"
OUT_FULL = r"C:\emerald\master_player\nirit_alpha.png"
OUT_540 = r"C:\emerald\master_player\nirit_alpha_540h.png"

if not os.path.exists(BACKUP):
    shutil.copy2(SRC, BACKUP)

img = Image.open(SRC).convert("RGBA")
arr = np.array(img)
h, w = arr.shape[:2]
print(f"src: {w}x{h}")

# Brightness map
gray = (arr[:,:,0].astype(np.int32) + arr[:,:,1].astype(np.int32) + arr[:,:,2].astype(np.int32)) // 3
print(f"brightness range: {gray.min()}..{gray.max()}, mean={gray.mean():.0f}")

# Flood fill from 4 corners. Threshold: pixel is "background" if brightness > 180.
# This finds all bg pixels CONNECTED to a corner.
THRESHOLD = 180
visited = np.zeros((h, w), dtype=bool)
queue = deque()
# Seed from all 4 corners + a strip along each edge
for x in range(w):
    if gray[0, x] > THRESHOLD:
        queue.append((0, x))
        visited[0, x] = True
    if gray[h-1, x] > THRESHOLD:
        queue.append((h-1, x))
        visited[h-1, x] = True
for y in range(h):
    if gray[y, 0] > THRESHOLD:
        queue.append((y, 0))
        visited[y, 0] = True
    if gray[y, w-1] > THRESHOLD:
        queue.append((y, w-1))
        visited[y, w-1] = True

while queue:
    y, x = queue.popleft()
    for dy, dx in [(-1,0),(1,0),(0,-1),(0,1)]:
        ny, nx = y+dy, x+dx
        if 0 <= ny < h and 0 <= nx < w and not visited[ny, nx] and gray[ny, nx] > THRESHOLD:
            visited[ny, nx] = True
            queue.append((ny, nx))

bg_mask = visited
fg_count = (~bg_mask).sum()
bg_count = bg_mask.sum()
print(f"flood fill: {bg_count} bg px, {fg_count} fg px ({100*fg_count/(h*w):.1f}% character)")

# SECOND PASS: catch interior PURE-white pockets (e.g. between legs)
# WITHOUT eating skin highlights. Skin highlight on this image is around
# RGB (200, 165, 140) — warm and color-imbalanced. Pure bg white is (250, 250, 250)
# — neutral. Distinguishing trick: require ALL channels >= 248 AND require the
# pixel to be "neutral" (max-min channel diff <= 8). Skin can never satisfy both.
# Then drop the upper-size filter — the legs gap on a 896x1344 image is large.
from scipy.ndimage import label as cc_label
r_ch = arr[:,:,0].astype(np.int32)
g_ch = arr[:,:,1].astype(np.int32)
b_ch = arr[:,:,2].astype(np.int32)
chan_max = np.maximum(np.maximum(r_ch, g_ch), b_ch)
chan_min = np.minimum(np.minimum(r_ch, g_ch), b_ch)
neutral = (chan_max - chan_min) <= 8
near_pure_white = (r_ch >= 240) & (g_ch >= 240) & (b_ch >= 240) & neutral
interior_candidate = near_pure_white & (~bg_mask)
labeled, n_components = cc_label(interior_candidate)
print(f"interior candidates: {interior_candidate.sum()} px in {n_components} components")
# Print top-10 component sizes for diagnostic
sizes = []
for cid in range(1, n_components+1):
    sz = int((labeled == cid).sum())
    sizes.append((cid, sz))
sizes.sort(key=lambda t: -t[1])
print(f"top component sizes: {[s for _,s in sizes[:10]]}")
interior_white = np.zeros_like(interior_candidate)
for cid, sz in sizes:
    # Accept any component >= 50 px (reject 1-2 px noise). NO upper bound — the
    # neutrality + brightness requirement guarantees we only catch true white bg.
    if sz >= 50:
        interior_white |= (labeled == cid)
print(f"interior white pockets accepted: {interior_white.sum()} px")
bg_mask = bg_mask | interior_white

# Apply: bg pixels → alpha=0, fg pixels → alpha=255
alpha = np.where(bg_mask, 0, 255).astype(np.uint8)

# Soft edge: pixels just inside the boundary that are still bright should be partial alpha
# Find edge pixels (alpha=255 but adjacent to alpha=0)
alpha_img = Image.fromarray(alpha)
# Erode by 1 px to remove halos that survived flood fill (lighter pixels surrounded by fg)
alpha_img = alpha_img.filter(ImageFilter.MinFilter(3))
alpha = np.array(alpha_img)

arr[:,:,3] = alpha

# Decontaminate near-edge bright pixels — scale RGB by alpha so semi-transparent
# pixels don't leak white onto darker bgs
mask_partial = (arr[:,:,3] > 0) & (arr[:,:,3] < 255) & (gray > 200)
factor = (arr[:,:,3] / 255.0).astype(np.float32)
for ch in range(3):
    ch_arr = arr[:,:,ch].astype(np.float32)
    arr[:,:,ch] = np.clip(np.where(mask_partial, ch_arr * factor, ch_arr), 0, 255).astype(np.uint8)

out = Image.fromarray(arr)
out.save(OUT_FULL, "PNG", optimize=True)

oh, ow = out.size[1], out.size[0]
out_540 = out.resize((int(round(ow*540/oh)), 540), Image.LANCZOS)
out_540.save(OUT_540, "PNG", optimize=True)

print(f"OK: {OUT_FULL} ({os.path.getsize(OUT_FULL)//1024}KB)")
print(f"OK: {OUT_540} ({os.path.getsize(OUT_540)//1024}KB)")

# Verify samples
sample = np.array(out)
print(f"hair @({w//2},{h//8}): {tuple(sample[h//8, w//2])}")
print(f"shoulder @({w//2-40},{h//4}): {tuple(sample[h//4, w//2-40])}")
print(f"corner @(5,5): {tuple(sample[5,5])}")
print(f"middle-left edge @({w//4},{h//2}): {tuple(sample[h//2, w//4])}")

# DIAGNOSTIC: scan rows to find visible-pixel runs (detect legs gap + hands)
print("\n--- ROW SCAN (output) ---")
src_rgb = np.array(Image.open(SRC).convert("RGB"))
for y_pct in [0.55, 0.65, 0.72, 0.80, 0.88, 0.94]:
    y = int(h * y_pct)
    alpha_row = sample[y, :, 3]
    visible = alpha_row > 0
    runs = []
    in_run = False; start = 0
    for x in range(w):
        if visible[x] and not in_run:
            start = x; in_run = True
        elif not visible[x] and in_run:
            runs.append((start, x-1)); in_run = False
    if in_run: runs.append((start, w-1))
    # Also scan source for bright bg runs
    src_gray = src_rgb[y].mean(axis=1)
    src_bright = src_gray > 245
    src_runs = []
    in_run = False; start = 0
    for x in range(w):
        if src_bright[x] and not in_run:
            start = x; in_run = True
        elif not src_bright[x] and in_run:
            src_runs.append((start, x-1)); in_run = False
    if in_run: src_runs.append((start, w-1))
    print(f"y={y} ({y_pct:.2f}): out_visible_runs={runs} | src_bright_runs={src_runs}")

# Sample the legs-gap area specifically
print("\n--- SAMPLES at suspected legs-gap ---")
for y_pct in [0.78, 0.85, 0.90]:
    y = int(h*y_pct)
    xc = w//2
    src_px = tuple(src_rgb[y, xc])
    out_px = tuple(sample[y, xc])
    print(f"  y={y} x={xc}: src_RGB={src_px} -> out_RGBA={out_px}")
