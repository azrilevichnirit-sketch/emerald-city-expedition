"""Extract 4 keyframes (t=1,3,5,7s) per bg_*.mp4, stitch into 2x2 grid."""
import subprocess
from pathlib import Path
from PIL import Image

PROJECT = Path(__file__).resolve().parent.parent
BG_DIR = PROJECT / "assets" / "backgrounds"
OUT_DIR = PROJECT / "pipeline" / "bg_keyframes"
OUT_DIR.mkdir(parents=True, exist_ok=True)

FFMPEG = "ffmpeg"
TIMES = [0.5, 1.8, 3.1, 4.5]


def extract(bg_file):
    slug = bg_file.stem
    frames = []
    for t in TIMES:
        out = OUT_DIR / f"{slug}_t{t}.png"
        if not out.exists():
            subprocess.run(
                [FFMPEG, "-y", "-loglevel", "error",
                 "-ss", str(t), "-i", str(bg_file),
                 "-vframes", "1", "-q:v", "2", str(out)],
                check=True,
            )
        frames.append(out)
    # stitch 2x2
    imgs = [Image.open(f) for f in frames]
    w, h = imgs[0].size
    scale = 640 / max(w, h)
    tw, th = int(w * scale), int(h * scale)
    imgs = [i.resize((tw, th)) for i in imgs]
    grid = Image.new("RGB", (tw * 2, th * 2))
    grid.paste(imgs[0], (0, 0))
    grid.paste(imgs[1], (tw, 0))
    grid.paste(imgs[2], (0, th))
    grid.paste(imgs[3], (tw, th))
    grid_path = OUT_DIR / f"{slug}_grid.png"
    grid.save(grid_path, "PNG")
    return grid_path


def main():
    bgs = sorted(BG_DIR.glob("bg_*.mp4"))
    print(f"found {len(bgs)} backgrounds")
    for bg in bgs:
        g = extract(bg)
        print(f"  {bg.name} -> {g.name}")


if __name__ == "__main__":
    main()
