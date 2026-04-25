"""
Auto-screen final images before visual human_review.
Detects obvious rembg failures: mostly green (rembg stripped too much),
too small non-green content area, or degenerate images.

Emits pipeline/auto_review.json classifying each tool as:
  - auto_pass: likely OK, still needs visual check
  - auto_fail_rembg: object was stripped — rembg failure
  - auto_fail_empty: image is nearly all green
  - missing: no final PNG
"""
import json
from pathlib import Path
from PIL import Image

PROJECT = Path(r"C:/Users/azril/OneDrive/Desktop/fincail_game/new")
QA = PROJECT / "pipeline" / "review" / "tools_qa"
ASSETS = PROJECT / "assets" / "tools"
PROMPTS = PROJECT / "pipeline" / "prompts"

CHROMA = (0, 0xB1, 0x40)


def pct_non_chroma(img: Image.Image) -> float:
    img = img.convert("RGB")
    w, h = img.size
    img.thumbnail((256, 256))
    px = img.load()
    tw, th = img.size
    total = tw * th
    non_chroma = 0
    for y in range(th):
        for x in range(tw):
            r, g, b = px[x, y]
            # near-chroma if close to (0, 177, 64)
            if abs(r - CHROMA[0]) < 40 and abs(g - CHROMA[1]) < 40 and abs(b - CHROMA[2]) < 40:
                continue
            non_chroma += 1
    return non_chroma / total


def classify(slug):
    final = QA / f"{slug}_final.png"
    approved = ASSETS / f"{slug}.png"
    if approved.exists():
        return {"status": "already_approved"}
    if not final.exists():
        return {"status": "missing"}
    try:
        img = Image.open(final)
    except Exception as e:
        return {"status": "error_open", "error": str(e)}
    non_ch = pct_non_chroma(img)
    if non_ch < 0.03:
        return {"status": "auto_fail_empty", "non_chroma_pct": round(non_ch, 4)}
    if non_ch < 0.10:
        return {"status": "auto_fail_rembg_stripped", "non_chroma_pct": round(non_ch, 4)}
    return {"status": "auto_pass", "non_chroma_pct": round(non_ch, 4)}


def main():
    slugs = [p.stem for p in sorted(PROMPTS.glob("*.json"))]
    out = {}
    for s in slugs:
        c = classify(s)
        out[s] = c
        print(f"{s:40} {c['status']:30} {c.get('non_chroma_pct','')}", flush=True)
    (PROJECT / "pipeline" / "auto_review.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    counts = {}
    for v in out.values():
        counts[v["status"]] = counts.get(v["status"], 0) + 1
    print("\n== TOTALS ==")
    for k, v in counts.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
