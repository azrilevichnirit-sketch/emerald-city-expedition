"""Chroma audit for the 8 jeep visuals.

Question: which jeep visuals are on clean #00B140 chroma green
with NO green leak on the subject?

Per Camera Bible:
  scenery_bg_target = (0, 177, 64)   # #00B140
  tolerance        = +/- 8 per channel for "clean" background pixel
  leak threshold   = green-dominant pixel (G > R+30 AND G > B+30) inside
                     subject mask = bad
"""
import sys
from pathlib import Path
from PIL import Image

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

TARGET = (0, 177, 64)
TOL = 12          # how close to #00B140 a pixel must be to count as "background"
LEAK_DR = 30      # how green-dominant a pixel must be inside subject to count as leak

CANDIDATES = [
    ("1  smoking_jeep_r1   (Gemini round 1)",
     r"C:\emerald\pipeline\review\scenery\_candidates\smoking_jeep_r1.png"),
    ("2  smoking_jeep_r2   (Gemini round 2)",
     r"C:\emerald\pipeline\review\scenery\_candidates\smoking_jeep_r2.png"),
    ("3  smoking_jeep_r3   (Gemini round 3)",
     r"C:\emerald\pipeline\review\scenery\_candidates\smoking_jeep_r3.png"),
    ("4  smoking_jeep      (ACTIVE  in assets/scenery/)",
     r"C:\emerald\assets\scenery\smoking_jeep.png"),
    ("5  smoking_jeep      (_orig_backup)",
     r"C:\emerald\assets\scenery\_orig_backup\smoking_jeep.png"),
    ("6  smoking_jeep      (_v2_backup)",
     r"C:\emerald\assets\scenery\_v2_backup\smoking_jeep.png"),
    ("7  jeep_hood_open    (Nirit / old/scenery/)",
     r"C:\Users\azril\OneDrive\Desktop\fincail_game\old\scenery\jeep_hood_open.png"),
    ("8  jeep_hood_open    (Nirit / old/assets/תפאורה/new/)",
     r"C:\Users\azril\OneDrive\Desktop\fincail_game\old\assets\תפאורה\new\jeep_hood_open.png"),
]


def is_target_green(px):
    r, g, b = px[:3]
    return (abs(r - TARGET[0]) <= TOL
            and abs(g - TARGET[1]) <= TOL
            and abs(b - TARGET[2]) <= TOL)


def is_green_dominant(px):
    """Pixel that is suspiciously green for a non-background pixel."""
    r, g, b = px[:3]
    return (g > r + LEAK_DR) and (g > b + LEAK_DR) and g > 80


def audit(path: Path):
    im = Image.open(path).convert("RGB")
    w, h = im.size
    px = im.load()

    # 1) corner sample (12x12 from each corner) — should all be #00B140
    corners = []
    for cx, cy in [(0, 0), (w - 12, 0), (0, h - 12), (w - 12, h - 12)]:
        bg_hits, total = 0, 0
        for y in range(cy, cy + 12):
            for x in range(cx, cx + 12):
                total += 1
                if is_target_green(px[x, y]):
                    bg_hits += 1
        corners.append(bg_hits / total)
    bg_purity = sum(corners) / len(corners)  # 1.0 = perfect

    # 2) average corner color (what the bg actually is)
    rs, gs, bs, n = 0, 0, 0, 0
    for cx, cy in [(0, 0), (w - 12, 0), (0, h - 12), (w - 12, h - 12)]:
        for y in range(cy, cy + 12):
            for x in range(cx, cx + 12):
                r, g, b = px[x, y]
                rs += r; gs += g; bs += b; n += 1
    avg_bg = (rs // n, gs // n, bs // n)

    # 3) green-leak inside subject = pixels that are NOT background-green
    #    but ARE green-dominant. This is the smoking gun.
    leak, subject = 0, 0
    step = max(1, min(w, h) // 200)
    for y in range(0, h, step):
        for x in range(0, w, step):
            p = px[x, y]
            if is_target_green(p):
                continue              # this is bg, fine
            subject += 1
            if is_green_dominant(p):
                leak += 1
    leak_pct = (leak / subject) if subject else 0.0

    return {
        "size": f"{w}x{h}",
        "bg_purity": bg_purity,
        "avg_corner": avg_bg,
        "subject_pixels_sampled": subject,
        "green_leak_pct": leak_pct,
    }


def fmt(r):
    bg = r["bg_purity"]
    leak = r["green_leak_pct"]
    bg_tag = "OK" if bg > 0.95 else ("MIX" if bg > 0.5 else "BAD")
    leak_tag = "OK" if leak < 0.01 else ("WARN" if leak < 0.05 else "BAD")
    return (f"  {r['size']:>10}  bg_purity={bg*100:5.1f}%[{bg_tag}]  "
            f"avg_bg={r['avg_corner']}  leak={leak*100:5.2f}%[{leak_tag}]")


print("=" * 92)
print("CHROMA AUDIT — target #00B140 = (0, 177, 64), tol +-12")
print("=" * 92)

for label, path in CANDIDATES:
    p = Path(path)
    if not p.exists():
        print(f"\n{label}\n  MISSING: {path}")
        continue
    try:
        r = audit(p)
        print(f"\n{label}")
        print(fmt(r))
    except Exception as e:
        print(f"\n{label}\n  ERROR: {e}")

print("\n" + "=" * 92)
print("READING THE NUMBERS:")
print(" bg_purity   = % of corner pixels that are exactly #00B140 (+-12)")
print("               OK   >95%   = clean chroma background")
print("               MIX  50-95% = partial / faded background")
print("               BAD  <50%   = wrong background color (hand-painted scene, not chroma)")
print(" leak        = % of subject pixels that are unnaturally green-dominant")
print("               OK    <1%   = clean subject")
print("               WARN  1-5%  = some green halo (fixable)")
print("               BAD   >5%   = serious green spill on the subject itself")
print("=" * 92)
