"""1) Chroma-audit ALL boat candidates project-wide -> find cleanest for escape_boat_distant
2) Extract a still frame from old/bg/cave.mp4 -> usable as dark_cave_entrance prop
"""
import sys
import subprocess
from pathlib import Path
from PIL import Image

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ============== CHROMA AUDIT ==============

TARGET = (0, 177, 64)
TOL_BG = 12

def is_bg(p):
    return all(abs(c - t) <= TOL_BG for c, t in zip(p[:3], TARGET))

def chroma_audit(path: Path):
    try:
        im = Image.open(path).convert("RGB")
    except Exception as e:
        return {"error": str(e)[:80]}
    w, h = im.size
    px = im.load()
    # bg purity
    cb, ct = 0, 0
    for cx, cy in [(0, 0), (w-12, 0), (0, h-12), (w-12, h-12)]:
        for y in range(cy, cy+12):
            for x in range(cx, cx+12):
                ct += 1
                if is_bg(px[x, y]):
                    cb += 1
    purity = cb / ct
    # edge color
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
    return {"size": f"{w}x{h}", "purity": round(purity, 3), "edge": avg, "lean": lean}


def verdict(r):
    if "error" in r:
        return "ERROR"
    p, lean = r["purity"], r["lean"]
    if lean is None:
        return "NO_SUBJECT"
    if p < 0.5:
        return "NO_CHROMA"
    if lean <= 3:
        return "CLEAN"
    if lean <= 8:
        return "MILD_HALO"
    if lean <= 20:
        return "FAKE_CLEAN"
    return "DIRTY"


BOATS = [
    # active in assets/scenery
    (r"C:\emerald\assets\scenery\escape_boat_distant.png",       "active   escape_boat_distant"),
    (r"C:\emerald\assets\scenery\main_boat_at_shore.png",        "active   main_boat_at_shore"),
    (r"C:\emerald\assets\scenery\main_boat_at_shore(1).png",     "active   main_boat_at_shore(1)"),
    (r"C:\emerald\assets\scenery\competitor_boat_at_cave.png",   "active   competitor_boat_at_cave"),
    # backups
    (r"C:\emerald\assets\scenery\_orig_backup\escape_boat_distant.png",     "orig     escape_boat_distant"),
    (r"C:\emerald\assets\scenery\_orig_backup\main_boat_at_shore.png",      "orig     main_boat_at_shore"),
    (r"C:\emerald\assets\scenery\_orig_backup\competitor_boat_at_cave.png", "orig     competitor_boat_at_cave"),
    (r"C:\emerald\assets\scenery\_v2_backup\escape_boat_distant.png",       "v2       escape_boat_distant"),
    (r"C:\emerald\assets\scenery\_v2_backup\main_boat_at_shore.png",        "v2       main_boat_at_shore"),
    (r"C:\emerald\assets\scenery\_v2_backup\competitor_boat_at_cave.png",   "v2       competitor_boat_at_cave"),
    # gemini rounds — escape_boat_distant
    (r"C:\emerald\pipeline\review\scenery\_candidates\escape_boat_distant_r1.png", "rN       escape_boat_distant_r1"),
    (r"C:\emerald\pipeline\review\scenery\_candidates\escape_boat_distant_r2.png", "rN       escape_boat_distant_r2"),
    (r"C:\emerald\pipeline\review\scenery\_candidates\escape_boat_distant_r3.png", "rN       escape_boat_distant_r3"),
    (r"C:\emerald\pipeline\review\scenery\_candidates\escape_boat_distant_r4.png", "rN       escape_boat_distant_r4"),
    (r"C:\emerald\pipeline\review\scenery\_candidates\escape_boat_distant_r5.png", "rN       escape_boat_distant_r5"),
    (r"C:\emerald\pipeline\review\scenery\_candidates\escape_boat_distant_r6.png", "rN       escape_boat_distant_r6"),
    (r"C:\emerald\pipeline\review\scenery\_candidates\escape_boat_distant_r7.png", "rN       escape_boat_distant_r7"),
    (r"C:\emerald\pipeline\review\scenery\_candidates\escape_boat_distant_r8.png", "rN       escape_boat_distant_r8"),
    # gemini rounds — main_boat_at_shore (could re-use as escape_boat at small scale)
    (r"C:\emerald\pipeline\review\scenery\_candidates\main_boat_at_shore_r1.png", "rN       main_boat_at_shore_r1"),
    (r"C:\emerald\pipeline\review\scenery\_candidates\main_boat_at_shore_r2.png", "rN       main_boat_at_shore_r2"),
    (r"C:\emerald\pipeline\review\scenery\_candidates\main_boat_at_shore_r3.png", "rN       main_boat_at_shore_r3"),
    (r"C:\emerald\pipeline\review\scenery\_candidates\main_boat_at_shore_r4.png", "rN       main_boat_at_shore_r4"),
    (r"C:\emerald\pipeline\review\scenery\_candidates\main_boat_at_shore_r5.png", "rN       main_boat_at_shore_r5"),
    (r"C:\emerald\pipeline\review\scenery\_candidates\main_boat_at_shore_r6.png", "rN       main_boat_at_shore_r6"),
    (r"C:\emerald\pipeline\review\scenery\_candidates\main_boat_at_shore_r7.png", "rN       main_boat_at_shore_r7"),
    (r"C:\emerald\pipeline\review\scenery\_candidates\main_boat_at_shore_r8.png", "rN       main_boat_at_shore_r8"),
    # nirit's old hand-made
    (r"C:\Users\azril\OneDrive\Desktop\fincail_game\old\scenery\boat_escape.png", "nirit    boat_escape (old)"),
]

print("=" * 80)
print("BOAT CHROMA AUDIT (sorted by best chroma)")
print("=" * 80)
results = []
for path, label in BOATS:
    p = Path(path)
    if not p.exists():
        results.append((path, label, {"error": "missing"}, "MISSING"))
        continue
    r = chroma_audit(p)
    results.append((path, label, r, verdict(r)))

# sort: CLEAN > MILD_HALO > others
order = ["CLEAN", "MILD_HALO", "FAKE_CLEAN", "DIRTY", "NO_CHROMA", "NO_SUBJECT", "MISSING", "ERROR"]
results.sort(key=lambda x: (order.index(x[3]) if x[3] in order else 99))

for path, label, r, v in results:
    if "error" in r:
        print(f"  [{v:<10}]  {label}  -- {r['error']}")
    else:
        size = r.get("size", "?")
        p = r.get("purity", "?")
        lean = r.get("lean", "?")
        print(f"  [{v:<10}]  {label:<40}  {size:>10}  bg={p}  lean={lean}")

print()

# ============== CAVE FRAME EXTRACTION ==============

OUT = Path(r"C:\emerald\pipeline\review\cave_candidates")
OUT.mkdir(parents=True, exist_ok=True)

CAVE_VIDEOS = [
    (r"C:\Users\azril\OneDrive\Desktop\fincail_game\old\bg\cave.mp4",
     "old_bg_cave_full.png"),
    (r"C:\Users\azril\OneDrive\Desktop\fincail_game\old\backgrounds\bg_cave.mp4",
     "old_backgrounds_bg_cave.png"),
    (r"C:\emerald\assets\backgrounds\bg_02.mp4",
     "active_bg_02.png"),
]

print("=" * 80)
print("CAVE FRAME EXTRACTION (frame at 1s of each cave bg)")
print("=" * 80)

for video, out_name in CAVE_VIDEOS:
    if not Path(video).exists():
        print(f"  MISSING: {video}")
        continue
    out_path = OUT / out_name
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-ss", "1.0",
        "-i", video,
        "-frames:v", "1",
        str(out_path),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=30)
        print(f"  -> {out_path}")
    except subprocess.CalledProcessError as e:
        print(f"  FAIL {video}: {e.stderr.decode('utf-8', errors='replace')[:200]}")
    except FileNotFoundError:
        print("  ffmpeg not found in PATH")
        break
    except Exception as e:
        print(f"  ERROR: {e}")

print()
print(f"open output dir: {OUT}")
