"""STRICT edge-color chroma audit on ALL 52 scenery props.

The standard "bg_purity > 95%" check is misleading because Gemini paints
green-lit lighting onto subjects, leaving an avg edge color around (80, 91, 70)
even when the corner pixels are perfect #00B140.

This script catches that. For every PNG in assets/scenery/ (excluding _backups
and underscored files), it reports:
  - bg_purity   : % corner pixels exact #00B140
  - edge_color  : avg color of pixels touching the chroma boundary
  - green_lean  : G - max(R, B) of edge color
  - verdict     : CLEAN / FAKE_CLEAN / DIRTY / NO_CHROMA
"""
import sys
import json
import time
from pathlib import Path
from PIL import Image

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT = Path(r"C:\emerald")
SCENERY = PROJECT / "assets" / "scenery"
OUT = PROJECT / "pipeline" / "review" / "scenery_chroma_edges.json"
OUT.parent.mkdir(parents=True, exist_ok=True)

TARGET = (0, 177, 64)
TOL_BG = 12


def is_bg(p):
    return all(abs(c - t) <= TOL_BG for c, t in zip(p[:3], TARGET))


def audit_one(path: Path):
    im = Image.open(path).convert("RGB")
    w, h = im.size
    px = im.load()

    # 1) bg_purity from corners
    corner_total, corner_bg = 0, 0
    for cx, cy in [(0, 0), (w - 12, 0), (0, h - 12), (w - 12, h - 12)]:
        for y in range(cy, cy + 12):
            for x in range(cx, cx + 12):
                corner_total += 1
                if is_bg(px[x, y]):
                    corner_bg += 1
    bg_purity = corner_bg / corner_total

    # 2) Edge sample — pixels right next to chroma bg
    edge_pixels = []
    step = max(1, min(w, h) // 800)  # sparse scan
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

    avg = tuple(sum(c[i] for c in edge_pixels) // len(edge_pixels) for i in range(3))
    lean = avg[1] - max(avg[0], avg[2])

    # Verdict logic
    if bg_purity < 0.5:
        verdict = "NO_CHROMA"          # not even on chroma bg
    elif lean <= 3:
        verdict = "CLEAN"              # edges neutral — true cutout
    elif lean <= 8:
        verdict = "MILD_HALO"          # acceptable for demo
    elif lean <= 20:
        verdict = "FAKE_CLEAN"         # Gemini's signature: pure bg + green-tinted edges
    else:
        verdict = "DIRTY"              # severe spill

    return {
        "bg_purity": round(bg_purity, 3),
        "edge_pixels_sampled": len(edge_pixels),
        "edge_color": list(avg),
        "green_lean": lean,
        "verdict": verdict,
    }


files = sorted(p for p in SCENERY.glob("*.png") if not p.name.startswith("_"))
print(f"scanning {len(files)} scenery props for FAKE-CLEAN chroma...")
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
    print(f"  [{i:>2}/{len(files)}]  {f.stem:<35}  bg={bg}  lean={lean!s:<4}  {v}")

print()
print("=" * 60)
print("SUMMARY:")
for v in ["CLEAN", "MILD_HALO", "FAKE_CLEAN", "DIRTY", "NO_CHROMA",
          "ALL_BG_NO_SUBJECT", "_error"]:
    if v in counts:
        print(f"  {v:<20}  {counts[v]:>3}")
print("=" * 60)
print()
print("LEGEND:")
print("  CLEAN       — true cutout, ready to composite anywhere")
print("  MILD_HALO   — slight edge tint, acceptable for demo")
print("  FAKE_CLEAN  — bg looks pure but edges are green-tinted = Gemini's")
print("                signature failure mode. Will halo at scale.")
print("  DIRTY       — heavy green spill into subject")
print("  NO_CHROMA   — image is a scene, not on chroma bg at all")

out = {
    "_audited_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    "_target_chroma": list(TARGET),
    "_summary": counts,
    "_explanation": {
        "CLEAN": "edges within +/- 3 of neutral",
        "MILD_HALO": "edges 4-8 green-leaning, demo-acceptable",
        "FAKE_CLEAN": "edges 9-20 green-leaning despite pure corner bg",
        "DIRTY": "edges >20 green-leaning",
        "NO_CHROMA": "corners not on chroma bg",
    },
    "items": results,
}
OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\nsaved -> {OUT}")
