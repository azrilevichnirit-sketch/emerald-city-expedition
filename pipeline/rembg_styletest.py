"""
Background removal for style test — best-of-batch candidates.
Produces: transparent PNG (rembg) + composite on #00B140 (final).
"""
import sys
from pathlib import Path
from rembg import remove
from PIL import Image

PROJECT = Path(r"C:/Users/azril/OneDrive/Desktop/fincail_game/new")
STYLETEST_DIR = PROJECT / "pipeline" / "review" / "styletest"

CHROMA = (0, 0xB1, 0x40)  # #00B140

# Best-of-batch selection per human_review agent
candidates = [
    ("מצנח_מ01_styletest_v3.png", "מצנח_מ01"),
    ("פנס_עוצמתי_מ05_styletest_v2.png", "פנס_עוצמתי_מ05"),
    ("סולם_חבלים_מ08_styletest_v3.png", "סולם_חבלים_מ08"),
]

results = []

for src_name, asset in candidates:
    src = STYLETEST_DIR / src_name
    if not src.exists():
        print(f"SKIP {src_name} — not found")
        continue

    print(f"\n=== {asset} ===")
    print(f"  input: {src_name}")

    rembg_path = STYLETEST_DIR / f"{asset}_rembg.png"
    composite_path = STYLETEST_DIR / f"{asset}_final.png"

    # 1. rembg → transparent PNG
    print(f"  running rembg...", flush=True)
    img = Image.open(src)
    transparent = remove(img)
    transparent.save(rembg_path)
    print(f"  rembg saved: {rembg_path.name}  ({rembg_path.stat().st_size} bytes)")

    # 2. Composite on #00B140
    rgba = Image.open(rembg_path).convert("RGBA")
    bg = Image.new("RGB", rgba.size, CHROMA)
    bg.paste(rgba, mask=rgba.split()[3])
    bg.save(composite_path)
    print(f"  composite saved: {composite_path.name}  ({composite_path.stat().st_size} bytes)")

    results.append({
        "asset": asset,
        "source": str(src),
        "rembg": str(rembg_path),
        "final": str(composite_path),
    })

print("\n=== DONE ===")
for r in results:
    print(f"  {r['asset']}:")
    print(f"    rembg  : {r['rembg']}")
    print(f"    final  : {r['final']}")
