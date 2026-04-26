"""visual_editor agent (tools branch): chroma-key all 45 tools."""
import os, shutil, sys
from PIL import Image, ImageFilter
import numpy as np
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")

TOOLS_DIR = Path(r"C:\emerald\assets\tools")
BACKUP_DIR = Path(r"C:\emerald\assets\tools\_before_chroma_clean")
BACKUP_DIR.mkdir(exist_ok=True)

cleaned = 0
skipped = 0
errors = []

for src in sorted(TOOLS_DIR.glob("*.png")):
    if "_clean" in src.name or src.parent != TOOLS_DIR:
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
        # Chroma key: dominant green
        chroma_mask = (g > 100) & (g > r * 14 // 10) & (g > b * 14 // 10)
        # Also light-green halos: less aggressive but still greenish
        halo_mask = (g > 80) & (g > r) & (g > b) & ((g - (r+b)//2) > 25)
        full_mask = chroma_mask | halo_mask
        # Set alpha=0 on chroma (and zero out RGB so no green leak through anti-alias)
        arr[full_mask, 0] = 0
        arr[full_mask, 1] = 0
        arr[full_mask, 2] = 0
        arr[full_mask, 3] = 0
        # Decontaminate green spill on edges
        edge_partial = (~full_mask) & (g > r) & (g > b) & (g - max(80, 0) > 20)
        # Subtract green spill: shift green down toward avg of r,b for partial-green pixels
        for idx in np.argwhere(edge_partial):
            y, x = idx[0], idx[1]
            rr, gg, bb = arr[y,x,0], arr[y,x,1], arr[y,x,2]
            avg = (int(rr) + int(bb)) // 2
            if gg > avg + 10:
                arr[y,x,1] = max(avg, gg - 30)
        # Erode alpha
        alpha = arr[:,:,3]
        alpha_img = Image.fromarray(alpha).filter(ImageFilter.MinFilter(3))
        arr[:,:,3] = np.array(alpha_img)
        out = Image.fromarray(arr)
        out.save(src, "PNG", optimize=True)  # overwrite — backup already saved
        cleaned += 1
    except Exception as e:
        errors.append((src.name, str(e)))

import sys
sys.stdout.reconfigure(encoding="utf-8")
print(f"OK: cleaned={cleaned}, errors={len(errors)}")
if errors:
    for n, e in errors[:10]:
        print(f"  ERR {n}: {e}")
print(f"backups: {BACKUP_DIR}")
