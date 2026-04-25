"""Subject Extractor — cuts a subject out of any visual + composites onto chroma.

Complement to vector_compositor (which only handles Shutterstock vectors,
deterministic). This one handles arbitrary source images with unwanted
backgrounds — old/ assets, Veo frames, Gemini round candidates with bad bg, etc.

Modes:
  rembg     — generic AI-based subject extraction (boats, jeeps, props,
              human silhouettes — anything photographic on any bg)
  luma      — luminance matte for smoke/dust/fog on dark bg (bright -> alpha,
              dark -> transparent). Use this for flare_smoke, engine_smoke etc.
  inverse_luma — opposite: dark -> alpha, bright -> transparent. For shadows
                 and silhouettes on bright bg.

Output: PNG on #00B140 chroma, with proper alpha-fringe handling so the
edge doesn't develop the green halo signature we just hunted down.
"""
import sys
import argparse
from pathlib import Path
from PIL import Image, ImageFilter

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CHROMA = (0, 177, 64)


def extract_rembg(src: Image.Image) -> Image.Image:
    """rembg = U^2-Net based salient object segmentation."""
    from rembg import remove
    out = remove(src)  # returns RGBA with bg removed
    return out


def extract_luma(src: Image.Image, threshold: int = 30, gamma: float = 1.5) -> Image.Image:
    """Bright pixel -> opaque alpha. Dark pixel -> transparent.
    Good for smoke/dust/fog on black bg.
    """
    rgba = src.convert("RGBA")
    px = rgba.load()
    w, h = rgba.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            lum = max(r, g, b)  # use max so colored highlights survive
            if lum < threshold:
                px[x, y] = (r, g, b, 0)
            else:
                # smooth alpha ramp from threshold to 255
                a_norm = (lum - threshold) / (255 - threshold)
                a_curved = min(1.0, a_norm ** (1 / gamma))
                px[x, y] = (r, g, b, int(a_curved * 255))
    return rgba


def extract_inverse_luma(src: Image.Image, threshold: int = 200) -> Image.Image:
    """Dark pixel -> opaque alpha. Bright pixel -> transparent.
    Good for shadows/silhouettes on bright bg.
    """
    rgba = src.convert("RGBA")
    px = rgba.load()
    w, h = rgba.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            lum = (r + g + b) // 3
            if lum > threshold:
                px[x, y] = (r, g, b, 0)
            else:
                a_norm = (threshold - lum) / threshold
                px[x, y] = (r, g, b, int(a_norm * 255))
    return rgba


def composite_on_chroma(rgba: Image.Image, defringe: bool = True,
                        alpha_threshold: int = 128) -> Image.Image:
    """HARD-edge composite onto #00B140.

    The naive way: paste rgba onto chroma using alpha-blend. This produces
    feathered edges that mix subject color with chroma -> the SAME green halo
    we just spent half a day hunting down. Don't do that.

    The right way:
      1. Spill-suppress: for any pixel with significant alpha, if G > R+15 AND
         G > B+15, pull G down to avg(R,B). Kills green spill from the original
         scene's lighting.
      2. Threshold alpha to {0, 255}. No feathering. Hard edge.
      3. Composite. Pixels with alpha=255 keep their (despilled) color.
         Pixels with alpha=0 become solid chroma. NO blended pixels.

    This produces a slightly aliased edge but ZERO halo. The chroma keyer at
    runtime gets a clean signal.
    """
    r, g, b, a = rgba.split()

    if defringe:
        rp, gp, bp = r.load(), g.load(), b.load()
        ap = a.load()
        w, h = rgba.size
        for y in range(h):
            for x in range(w):
                if ap[x, y] < 30:
                    continue
                R, G, B = rp[x, y], gp[x, y], bp[x, y]
                if G > R + 15 and G > B + 15:
                    gp[x, y] = (R + B) // 2

    # Threshold alpha to hard {0, 255}
    a_hard = a.point(lambda v: 255 if v >= alpha_threshold else 0)

    bg = Image.new("RGB", rgba.size, CHROMA)
    bg.paste(Image.merge("RGB", (r, g, b)), (0, 0), a_hard)
    return bg


def save_alpha_png(rgba: Image.Image, output_path: Path):
    """Save as PNG-with-alpha, NO chroma composite. For translucent things
    (smoke, fog, dust, shadows) where the player needs the actual alpha
    channel, not a chroma key.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rgba.save(output_path)


def chroma_check(im: Image.Image) -> dict:
    """Quick chroma audit on the output."""
    w, h = im.size
    px = im.load()
    cb, ct = 0, 0
    for cx, cy in [(0, 0), (w-12, 0), (0, h-12), (w-12, h-12)]:
        for y in range(cy, cy+12):
            for x in range(cx, cx+12):
                ct += 1
                r, g, b = px[x, y][:3]
                if all(abs(c - t) <= 12 for c, t in zip((r, g, b), CHROMA)):
                    cb += 1
    purity = cb / ct
    edge = []
    step = max(1, min(w, h) // 800)
    for y in range(1, h-1, step):
        for x in range(1, w-1, step):
            r, g, b = px[x, y][:3]
            if all(abs(c - t) <= 12 for c, t in zip((r, g, b), CHROMA)):
                continue
            ok = False
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nr, ng, nb = px[x+dx, y+dy][:3]
                if all(abs(c - t) <= 12 for c, t in zip((nr, ng, nb), CHROMA)):
                    ok = True
                    break
            if ok:
                edge.append((r, g, b))
                if len(edge) >= 2000:
                    break
        if len(edge) >= 2000:
            break
    if not edge:
        return {"purity": purity, "edge": None, "lean": None}
    avg = tuple(sum(c[i] for c in edge) // len(edge) for i in range(3))
    lean = avg[1] - max(avg[0], avg[2])
    return {"purity": round(purity, 3), "edge": list(avg), "lean": lean}


def verdict(c):
    if c["lean"] is None:
        return "NO_SUBJECT"
    if c["purity"] < 0.5:
        return "NO_CHROMA"
    if c["lean"] <= 3:
        return "CLEAN"
    if c["lean"] <= 8:
        return "MILD_HALO"
    if c["lean"] <= 20:
        return "FAKE_CLEAN"
    return "DIRTY"


def run(input_path: Path, output_path: Path, mode: str, **kw):
    print(f"\n>>> {input_path.name}  mode={mode}")
    src = Image.open(input_path)
    if mode == "rembg":
        rgba = extract_rembg(src)
    elif mode == "luma":
        rgba = extract_luma(src, threshold=kw.get("threshold", 30),
                            gamma=kw.get("gamma", 1.5))
    elif mode == "inverse_luma":
        rgba = extract_inverse_luma(src, threshold=kw.get("threshold", 200))
    else:
        raise ValueError(f"unknown mode {mode}")

    out = composite_on_chroma(rgba, defringe=kw.get("defringe", True))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    out.save(output_path)

    c = chroma_check(out)
    v = verdict(c)
    print(f"    saved -> {output_path}")
    print(f"    chroma: purity={c['purity']}  edge={c['edge']}  lean={c['lean']}  [{v}]")
    return v, c


# ============== TEST RUNS ==============

if __name__ == "__main__" and len(sys.argv) == 1:
    OUT = Path(r"C:\emerald\pipeline\review\extracted_v2")
    OUT.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print("SUBJECT EXTRACTOR — proof of concept on 3 real cases")
    print("=" * 70)

    # CASE 1: Nirit's hand-made boat (jungle/scene bg) -> chroma cutout
    run(
        Path(r"C:\Users\azril\OneDrive\Desktop\fincail_game\old\scenery\boat_escape.png"),
        OUT / "boat_escape_chroma.png",
        mode="rembg",
    )

    # CASE 2: flare_smoke -> alpha PNG (NO chroma, smoke is translucent)
    src = Image.open(r"C:\Users\azril\OneDrive\Desktop\fincail_game\old\bg_extra_assets_video\flare_smoke.png")
    rgba = extract_luma(src, threshold=20, gamma=1.4)
    save_alpha_png(rgba, OUT / "flare_smoke_alpha.png")
    print(f"\n>>> flare_smoke.png  mode=luma -> alpha PNG\n    saved -> {OUT / 'flare_smoke_alpha.png'}")

    # CASE 3: engine_smoke -> alpha PNG
    src = Image.open(r"C:\Users\azril\OneDrive\Desktop\fincail_game\old\bg_extra_assets_video\engine_smoke.png")
    rgba = extract_luma(src, threshold=15, gamma=1.3)
    save_alpha_png(rgba, OUT / "engine_smoke_alpha.png")
    print(f"\n>>> engine_smoke.png  mode=luma -> alpha PNG\n    saved -> {OUT / 'engine_smoke_alpha.png'}")

    # CASE 4: jeep_hood_open from Nirit's old/ -> chroma cutout (replaces smoking_jeep)
    run(
        Path(r"C:\Users\azril\OneDrive\Desktop\fincail_game\old\scenery\jeep_hood_open.png"),
        OUT / "jeep_hood_open_chroma.png",
        mode="rembg",
    )

    # CASE 5: parked_vehicles -- already CLEAN, but as a control test
    # ... skip, already verified clean

    # CASE 6: altar_stone from old/ -> if exists
    p = Path(r"C:\Users\azril\OneDrive\Desktop\fincail_game\old\scenery\altar_stone.png")
    if p.exists():
        run(p, OUT / "altar_stone_chroma.png", mode="rembg")

    print()
    print("=" * 70)
    print(f"open output dir: {OUT}")
    print("=" * 70)
