"""STRICT edge-color chroma audit on ALL tool PNGs.

Mirrors audit_chroma_edges_all_scenery.py but targets assets/tools/.

Per project memo: tool icons must match Hebrew player intuition (not literal
reality). Beyond that, they MUST sit on the same #00B140 chroma as scenery so
Builder can composite uniformly. This script catches:
  - Tools missing chroma entirely (transparent or wrong background)
  - Tools with green-halo edges (Gemini's FAKE_CLEAN failure mode)
  - Tools with heavy spill into the subject (DIRTY)
"""
import sys
import json
import time
from pathlib import Path
from PIL import Image

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT = Path(r"C:\emerald")
TOOLS = PROJECT / "assets" / "tools"
OUT = PROJECT / "pipeline" / "review" / "tools_chroma_edges.json"
OUT.parent.mkdir(parents=True, exist_ok=True)

TARGET = (0, 177, 64)
TOL_BG = 12


def is_bg(p):
    return all(abs(c - t) <= TOL_BG for c, t in zip(p[:3], TARGET))


def audit_one(path: Path):
    im = Image.open(path)
    has_alpha = im.mode in ("RGBA", "LA") or "transparency" in im.info
    im_rgb = im.convert("RGB")
    w, h = im_rgb.size
    px = im_rgb.load()

    # Corner sample size scales with image size
    sample = max(8, min(w, h) // 40)
    corner_total, corner_bg = 0, 0
    for cx, cy in [(0, 0), (w - sample, 0),
                   (0, h - sample), (w - sample, h - sample)]:
        for y in range(cy, cy + sample):
            for x in range(cx, cx + sample):
                corner_total += 1
                if is_bg(px[x, y]):
                    corner_bg += 1
    bg_purity = corner_bg / corner_total if corner_total else 0

    # Detect transparent-bg tools (legitimate alternative to chroma)
    if has_alpha and bg_purity < 0.05:
        # Check actual alpha
        im_a = im.convert("RGBA")
        ax = im_a.load()
        transparent = sum(
            1 for cx, cy in [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]
            if ax[cx, cy][3] < 30
        )
        if transparent >= 3:
            return {
                "bg_purity": round(bg_purity, 3),
                "edge_pixels_sampled": 0,
                "edge_color": None,
                "green_lean": None,
                "verdict": "TRANSPARENT_BG",
                "_note": "alpha-channel cutout, no chroma needed",
            }

    # Edge sample
    edge_pixels = []
    step = max(1, min(w, h) // 600)
    for y in range(1, h - 1, step):
        for x in range(1, w - 1, step):
            if is_bg(px[x, y]):
                continue
            if any(is_bg(px[x + dx, y + dy])
                   for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]):
                edge_pixels.append(px[x, y])
                if len(edge_pixels) >= 3000:
                    break
        if len(edge_pixels) >= 3000:
            break

    if not edge_pixels:
        return {
            "bg_purity": round(bg_purity, 3),
            "edge_pixels_sampled": 0,
            "edge_color": None,
            "green_lean": None,
            "verdict": "NO_CHROMA" if bg_purity < 0.5 else "ALL_BG_NO_SUBJECT",
        }

    avg = tuple(sum(c[i] for c in edge_pixels) // len(edge_pixels)
                for i in range(3))
    lean = avg[1] - max(avg[0], avg[2])

    if bg_purity < 0.5:
        verdict = "NO_CHROMA"
    elif lean <= 3:
        verdict = "CLEAN"
    elif lean <= 8:
        verdict = "MILD_HALO"
    elif lean <= 20:
        verdict = "FAKE_CLEAN"
    else:
        verdict = "DIRTY"

    return {
        "bg_purity": round(bg_purity, 3),
        "edge_pixels_sampled": len(edge_pixels),
        "edge_color": list(avg),
        "green_lean": lean,
        "verdict": verdict,
    }


files = sorted(p for p in TOOLS.glob("*.png") if not p.name.startswith("_"))
print(f"scanning {len(files)} tool PNGs for chroma fidelity...")
print()

results = {}
counts = {}
for i, f in enumerate(files, 1):
    try:
        r = audit_one(f)
    except Exception as e:
        r = {"_error": str(e)[:200]}
    results[f.stem] = r
    v = r.get("verdict", "_error")
    counts[v] = counts.get(v, 0) + 1
    bg = r.get("bg_purity", "?")
    lean = r.get("green_lean", "?")
    print(f"  [{i:>2}/{len(files)}]  {f.stem:<32}  bg={bg!s:<5}  lean={lean!s:<4}  {v}")

print()
print("=" * 60)
print("SUMMARY:")
for v in ["CLEAN", "MILD_HALO", "TRANSPARENT_BG", "FAKE_CLEAN", "DIRTY",
          "NO_CHROMA", "ALL_BG_NO_SUBJECT", "_error"]:
    if v in counts:
        print(f"  {v:<22}  {counts[v]:>3}")
print("=" * 60)

out = {
    "_audited_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    "_target_chroma": list(TARGET),
    "_summary": counts,
    "items": results,
}
OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\nsaved -> {OUT}")
