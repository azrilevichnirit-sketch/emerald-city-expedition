"""visual_editor: chroma-key pose_06_t5 (catching pose) -> alpha PNG."""
import os, shutil, sys
from PIL import Image, ImageFilter
import numpy as np
sys.stdout.reconfigure(encoding="utf-8")

SRC = r"C:\emerald\pipeline\pose_keyframes\pose_06_t5.png"
BACKUP = r"C:\emerald\pipeline\pose_keyframes\pose_06_t5.before_alpha.png"
OUT = r"C:\emerald\master_player\nirit_pose06_alpha.png"

if not os.path.exists(BACKUP):
    shutil.copy2(SRC, BACKUP)

img = Image.open(SRC).convert("RGBA")
arr = np.array(img)
r = arr[:,:,0].astype(np.int16)
g = arr[:,:,1].astype(np.int16)
b = arr[:,:,2].astype(np.int16)

# Standard chroma key for green
chroma_mask = (g > 100) & (g > r * 14 // 10) & (g > b * 14 // 10)
halo_mask = (g > 80) & (g > r) & (g > b) & ((g - (r+b)//2) > 25)
full_mask = chroma_mask | halo_mask

arr[full_mask, 0] = 0
arr[full_mask, 1] = 0
arr[full_mask, 2] = 0
arr[full_mask, 3] = 0

# Decontaminate residual green
edge_partial = (~full_mask) & (g > r) & (g > b) & (g > 90)
for idx in np.argwhere(edge_partial):
    y, x = idx[0], idx[1]
    rr, gg, bb = arr[y,x,0], arr[y,x,1], arr[y,x,2]
    avg = (int(rr) + int(bb)) // 2
    if gg > avg + 10:
        arr[y,x,1] = max(avg, gg - 30)

alpha = arr[:,:,3]
alpha_img = Image.fromarray(alpha).filter(ImageFilter.MinFilter(3))
arr[:,:,3] = np.array(alpha_img)

out = Image.fromarray(arr)
out.save(OUT, "PNG", optimize=True)

print(f"OK: {OUT} ({os.path.getsize(OUT)//1024}KB)")
print(f"size: {out.size}")
