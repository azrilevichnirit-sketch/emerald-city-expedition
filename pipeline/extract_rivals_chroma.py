"""visual_editor: chroma-key all rivals/*.png — same algorithm as tools."""
import os, shutil, sys
from PIL import Image, ImageFilter
import numpy as np
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")

RIVALS_DIR = Path(r"C:\emerald\rivals")
BACKUP_DIR = RIVALS_DIR / "_before_chroma_clean"
BACKUP_DIR.mkdir(exist_ok=True)

cleaned = 0
errors = []

for src in sorted(RIVALS_DIR.glob("*.png")):
    if src.parent != RIVALS_DIR:
        continue
    backup = BACKUP_DIR / src.name
    if not backup.exists():
        shutil.copy2(src, backup)
    try:
        img = Image.open(src).convert("RGBA")
        arr = np.array(img)
        r = arr[:,:,0].astype(np.int16)
        g = arr[:,:,1].astype(np.int16)
        b = arr[:,:,2].astype(np.int16)
        chroma_mask = (g > 100) & (g > r * 14 // 10) & (g > b * 14 // 10)
        halo_mask = (g > 80) & (g > r) & (g > b) & ((g - (r+b)//2) > 25)
        full_mask = chroma_mask | halo_mask
        arr[full_mask, 0] = 0
        arr[full_mask, 1] = 0
        arr[full_mask, 2] = 0
        arr[full_mask, 3] = 0
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
        out.save(src, "PNG", optimize=True)
        cleaned += 1
    except Exception as e:
        errors.append((src.name, str(e)))

print(f"OK: cleaned={cleaned}, errors={len(errors)}")
if errors:
    for n, e in errors[:5]:
        print(f"  ERR {n}: {e}")
