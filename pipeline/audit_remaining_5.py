"""Audit remaining 5 props with Nirit's notes:
  - dust_clouds       -> use old/.../flare_smoke or engine_smoke (already exists!)
  - flashing_keypad   -> Nirit thinks current static might be fine; also check old/security_keypad
  - wet_footprints    -> Nirit doubts shutterstock; check current state, propose CSS or accept
  - guard_shadows     -> Nirit asks if current Gemini output is OK
"""
import sys
from pathlib import Path
from PIL import Image

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

TARGET = (0, 177, 64)
TOL_BG = 12

def is_bg(p):
    return all(abs(c - t) <= TOL_BG for c, t in zip(p[:3], TARGET))

def audit(path: Path):
    try:
        im = Image.open(path).convert("RGB")
    except Exception as e:
        return {"error": str(e)[:80]}
    w, h = im.size
    px = im.load()
    cb, ct = 0, 0
    for cx, cy in [(0, 0), (w-12, 0), (0, h-12), (w-12, h-12)]:
        for y in range(cy, cy+12):
            for x in range(cx, cx+12):
                ct += 1
                if is_bg(px[x, y]):
                    cb += 1
    purity = cb / ct
    edge = []
    step = max(1, min(w, h) // 800)
    for y in range(1, h-1, step):
        for x in range(1, w-1, step):
            if is_bg(px[x, y]):
                continue
            if any(is_bg(px[x+dx, y+dy]) for dx, dy in [(-1,0),(1,0),(0,-1),(0,1)]):
                edge.append(px[x, y])
                if len(edge) >= 2000:
                    break
        if len(edge) >= 2000:
            break
    if not edge:
        return {"size": f"{w}x{h}", "purity": purity, "edge": None, "lean": None}
    avg = tuple(sum(c[i] for c in edge) // len(edge) for i in range(3))
    lean = avg[1] - max(avg[0], avg[2])
    return {"size": f"{w}x{h}", "purity": round(purity, 3), "edge": list(avg), "lean": lean}

def verdict(r):
    if "error" in r: return "ERROR"
    p, lean = r.get("purity"), r.get("lean")
    if lean is None: return "NO_SUBJECT_OR_NO_CHROMA"
    if p < 0.5: return "NO_CHROMA"
    if lean <= 3: return "CLEAN"
    if lean <= 8: return "MILD_HALO"
    if lean <= 20: return "FAKE_CLEAN"
    return "DIRTY"

CANDIDATES = [
    # dust_clouds alternatives
    ("dust_clouds (active, FAKE_CLEAN)",
     r"C:\emerald\assets\scenery\dust_clouds.png"),
    ("dust_clouds alt: old/flare_smoke.png",
     r"C:\Users\azril\OneDrive\Desktop\fincail_game\old\bg_extra_assets_video\flare_smoke.png"),
    ("dust_clouds alt: old/engine_smoke.png",
     r"C:\Users\azril\OneDrive\Desktop\fincail_game\old\bg_extra_assets_video\engine_smoke.png"),
    # flashing_keypad alternatives
    ("flashing_keypad (active, FAKE_CLEAN)",
     r"C:\emerald\assets\scenery\flashing_keypad.png"),
    ("keypad alt: old/scenery/security_keypad.png",
     r"C:\Users\azril\OneDrive\Desktop\fincail_game\old\scenery\security_keypad.png"),
    ("keypad alt: old/assets/תפאורה/new/security_keypad.png",
     r"C:\Users\azril\OneDrive\Desktop\fincail_game\old\assets\תפאורה\new\security_keypad.png"),
    # wet_footprints
    ("wet_footprints_trail (active, FAKE_CLEAN)",
     r"C:\emerald\assets\scenery\wet_footprints_trail.png"),
    # guard_shadows
    ("guard_shadows (active, ALL_BG_NO_SUBJECT)",
     r"C:\emerald\assets\scenery\guard_shadows.png"),
]

print("=" * 80)
print("CHROMA AUDIT — remaining 5 props, with Nirit's alternatives")
print("=" * 80)

for label, path in CANDIDATES:
    p = Path(path)
    if not p.exists():
        print(f"\n  MISSING:  {label}\n    {path}")
        continue
    r = audit(p)
    v = verdict(r)
    print(f"\n  [{v}]  {label}")
    if "error" in r:
        print(f"    ERROR: {r['error']}")
    else:
        print(f"    size={r['size']}  bg_purity={r['purity']}  edge={r['edge']}  lean={r['lean']}")

print()
