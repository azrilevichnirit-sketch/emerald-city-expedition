"""line_producer.run — compresses APPROVED assets into assets/optimized/.

PER agents/line_producer.md spec:
  - Operates ONLY on approved assets (delivered to assets/<type>/).
  - Produces compressed copies in assets/optimized/<type>/.
  - NEVER modifies originals.
  - NEVER calls Veo/Imagen/etc. — local encoders only (ffmpeg, Pillow).
  - Writes optimization_log.json with per-asset before/after sizes.
  - Pair files (before vs after) are written to pipeline/line_producer/_panel_input/
    for the weight_auditor (panel_audit.py) to verdict.

Compression strategy:
  - MP4 (transitions, backgrounds, poses): ffmpeg H.264 CRF 27, preset slow, max width 1280.
  - PNG (tools, scenery, rivals): Pillow -> WebP q85 with alpha. Keeps original PNG too as fallback.

Run:
  python pipeline/line_producer/run.py            # all approved assets
  python pipeline/line_producer/run.py --conservative  # higher quality (after retry verdict)
  python pipeline/line_producer/run.py --type backgrounds  # only one category

Output:
  pipeline/line_producer/optimization_log.json
  pipeline/line_producer/_panel_input/<type>/<name>_pair.json
  assets/optimized/<type>/<name>.<ext>
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT = Path(r"C:\emerald")
LP_DIR = PROJECT / "pipeline" / "line_producer"
OPT_ROOT = PROJECT / "assets" / "optimized"
PANEL_IN = LP_DIR / "_panel_input"
LOG_PATH = LP_DIR / "optimization_log.json"

BUDGET = json.loads((LP_DIR / "budget.json").read_text("utf-8"))
ENCODER = BUDGET["encoder_defaults"]
BUDGETS_KB = {k: v["max_kb"] for k, v in BUDGET["budgets"].items()}


def ffmpeg_compress_mp4(src: Path, dst: Path, crf: int, max_width: int) -> bool:
    dst.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(src),
        "-c:v", "libx264", "-crf", str(crf), "-preset", ENCODER["video_h264"]["preset"],
        "-vf", f"scale='min({max_width},iw)':-2",
        "-c:a", "aac", "-b:a", "96k",
        "-movflags", "+faststart",
        str(dst),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"  ffmpeg fail: {r.stderr[:200]}")
        return False
    return True


def pillow_to_webp(src: Path, dst: Path, q: int) -> bool:
    from PIL import Image
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        im = Image.open(src)
        # preserve alpha if RGBA
        kwargs = {"quality": q, "method": ENCODER["image_webp"]["method"]}
        if im.mode in ("RGBA", "LA"):
            kwargs["lossless"] = False
            kwargs["alpha_quality"] = ENCODER["image_webp"]["alpha_q"]
        im.save(dst, "WEBP", **kwargs)
        return True
    except Exception as e:
        print(f"  pillow fail: {e}")
        return False


# ---- per-type drivers ----

def process_mp4_dir(src_dir: Path, type_key: str, conservative: bool, log: list) -> None:
    if not src_dir.exists():
        return
    crf_field = "conservative_crf" if conservative else "default_crf"
    crf = ENCODER["video_h264"][crf_field]
    max_w = ENCODER["video_h264"]["max_width_px"]
    out_dir = OPT_ROOT / src_dir.name
    panel_dir = PANEL_IN / src_dir.name
    panel_dir.mkdir(parents=True, exist_ok=True)
    budget_kb = BUDGETS_KB[type_key]

    for src in sorted(src_dir.glob("*.mp4")):
        dst = out_dir / src.name
        before_kb = round(src.stat().st_size / 1024)
        ok = ffmpeg_compress_mp4(src, dst, crf=crf, max_width=max_w)
        if not ok:
            log.append({"asset": src.name, "type": type_key, "status": "encode_fail"})
            continue
        after_kb = round(dst.stat().st_size / 1024)
        in_budget = after_kb <= budget_kb
        ratio = round(before_kb / max(1, after_kb), 2)
        entry = {
            "asset": src.name, "type": type_key,
            "before_kb": before_kb, "after_kb": after_kb,
            "ratio": ratio, "in_budget": in_budget, "budget_kb": budget_kb,
            "codec": f"H.264 CRF {crf}, max_w {max_w}, preset {ENCODER['video_h264']['preset']}",
            "src": str(src.relative_to(PROJECT)),
            "dst": str(dst.relative_to(PROJECT)),
            "status": "compressed_pending_panel",
            "_already_conservative": conservative,
        }
        log.append(entry)
        # write panel pair input
        (panel_dir / f"{src.stem}_pair.json").write_text(
            json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"  [{src.name}] {before_kb}KB -> {after_kb}KB (x{ratio}) "
              f"{'OK' if in_budget else f'OVER budget {budget_kb}KB'}")


def process_png_dir(src_dir: Path, type_key: str, conservative: bool, log: list) -> None:
    if not src_dir.exists():
        return
    q = ENCODER["image_webp"]["conservative_q"] if conservative else ENCODER["image_webp"]["default_q"]
    out_dir = OPT_ROOT / src_dir.name
    panel_dir = PANEL_IN / src_dir.name
    panel_dir.mkdir(parents=True, exist_ok=True)
    budget_kb = BUDGETS_KB[type_key]

    for src in sorted(src_dir.glob("*.png")):
        dst = out_dir / (src.stem + ".webp")
        before_kb = round(src.stat().st_size / 1024)
        ok = pillow_to_webp(src, dst, q=q)
        if not ok:
            log.append({"asset": src.name, "type": type_key, "status": "encode_fail"})
            continue
        after_kb = round(dst.stat().st_size / 1024)
        in_budget = after_kb <= budget_kb
        ratio = round(before_kb / max(1, after_kb), 2)
        entry = {
            "asset": src.name, "type": type_key,
            "before_kb": before_kb, "after_kb": after_kb,
            "ratio": ratio, "in_budget": in_budget, "budget_kb": budget_kb,
            "codec": f"WebP q{q} alpha_q{ENCODER['image_webp']['alpha_q']}",
            "src": str(src.relative_to(PROJECT)),
            "dst": str(dst.relative_to(PROJECT)),
            "status": "compressed_pending_panel",
            "_already_conservative": conservative,
        }
        log.append(entry)
        (panel_dir / f"{src.stem}_pair.json").write_text(
            json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"  [{src.name}] {before_kb}KB -> {after_kb}KB (x{ratio}) "
              f"{'OK' if in_budget else f'OVER budget {budget_kb}KB'}")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--conservative", action="store_true",
                     help="Use higher quality (after retry verdict)")
    ap.add_argument("--type", default="all",
                     choices=["all", "transitions", "backgrounds", "tools",
                              "scenery", "rivals", "player"])
    args = ap.parse_args(argv[1:])

    print("=" * 70)
    print(f"line_producer.run — conservative={args.conservative} type={args.type}")
    print("=" * 70)

    log: list = []
    t0 = time.time()

    plan = {
        "transitions": ("transition_mp4", "mp4"),
        "backgrounds": ("background_mp4", "mp4"),
        "player":      ("pose_mp4", "mp4"),
        "tools":       ("tool_png", "png"),
        "scenery":     ("scenery_png", "png"),
        "rivals":      ("rival_portrait", "png"),
    }
    for sub, (type_key, ext) in plan.items():
        if args.type != "all" and args.type != sub:
            continue
        src_dir = PROJECT / "assets" / sub
        print(f"\n--- {sub} ({type_key}) ---")
        if ext == "mp4":
            process_mp4_dir(src_dir, type_key, args.conservative, log)
        else:
            process_png_dir(src_dir, type_key, args.conservative, log)

    elapsed = round(time.time() - t0, 1)
    summary = {
        "_run_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "_elapsed_sec": elapsed,
        "_conservative_pass": args.conservative,
        "total_assets": len(log),
        "compressed": sum(1 for e in log if e.get("status") == "compressed_pending_panel"),
        "encode_failures": sum(1 for e in log if e.get("status") == "encode_fail"),
        "in_budget": sum(1 for e in log if e.get("in_budget")),
        "over_budget": sum(1 for e in log if e.get("in_budget") is False),
        "total_kb_before": sum(e.get("before_kb", 0) for e in log),
        "total_kb_after": sum(e.get("after_kb", 0) for e in log),
    }
    if summary["total_kb_after"]:
        summary["overall_ratio"] = round(
            summary["total_kb_before"] / summary["total_kb_after"], 2
        )

    out = {"_summary": summary, "items": log}
    LOG_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n" + "=" * 70)
    print(f"DONE in {elapsed}s  total={summary['total_assets']}  "
          f"compressed={summary['compressed']}  in_budget={summary['in_budget']}/"
          f"{summary['compressed']}  ratio=x{summary.get('overall_ratio', '?')}")
    print(f"  before={round(summary['total_kb_before']/1024, 1)}MB -> "
          f"after={round(summary['total_kb_after']/1024, 1)}MB")
    print(f"  log: {LOG_PATH.relative_to(PROJECT)}")
    print(f"  panel input: {PANEL_IN.relative_to(PROJECT)}/<type>/<name>_pair.json")
    print(f"  next: python pipeline/line_producer/panel_audit.py")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
