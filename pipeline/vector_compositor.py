"""Vector COMPOSITOR — the editing agent.

Takes the raw Shutterstock asset that just landed in the review folder and
turns it into a game-ready PNG with the right alpha and the right composition.

This is the agent Nirit asked for. The whole production company has directors
and writers but until now, none of them edited pixels. This one does. It is
deterministic — no Gemini, no Imagen, no AI repaint. Just PIL transforms
driven by a `compositor_spec` that the master agent emits per item.

Why it exists:
  - Shutterstock vectors arrive on transparent OR on a hard-keyed background
    (white / chroma green / black). When a prop ships on a green that
    overlaps the scenery green-screen video (#00B140), the keyer in the
    builder cannot tell prop-edge from scene-edge. Result: green on green.
  - Some slugs are not literal: a "shadow of guards" prop is best fetched as
    a guard silhouette and recolored to black. Some are multiplicative: a
    "jungle" is best fetched as one tree and tiled.
  - The master is the planner. The compositor is the executor. Together they
    let us pull atomic vectors and ship composed scene props.

Operations supported (all deterministic, no model calls):
  remove_background
      Detect dominant non-alpha background color from the image corners,
      key it out to alpha. Tolerance is bg-aware (white loose, green tight).
  silhouette
      Fill every visible (non-alpha) pixel with a flat color. Default black.
      Optional opacity for soft shadows.
  tile
      Repeat the image as an N x M grid with optional overlap. Useful for
      grove/forest/jungle from a single tree.
  scale_to
      Resize so the longest side equals N pixels, preserving aspect.
  pad_to
      Pad with transparency to a target canvas size, centered.
  flatten_to_color
      Flatten alpha onto a chosen background color. Use only when the
      builder explicitly needs a non-transparent prop (rare).

Input:
  raw_path        — file the downloader just wrote.
  compositor_spec — JSON dict from the master, see schema below.
  target_path     — where the composed PNG should land. Same folder, same
                    slug, .png extension forced.

Output:
  {
    "status": "OK" | "FAIL_<reason>",
    "ops_applied": [list of op names],
    "input_bytes": int,
    "output_bytes": int,
    "saved_path": "<target_path>",
    "notes": "<short>"
  }

Spec schema (what the master writes):
  {
    "remove_background": true | false,
    "background_hint": "auto" | "white" | "green" | "black" | "#RRGGBB" | null,
    "transforms": [
       {"op": "silhouette", "color": "#000000", "opacity": 1.0},
       {"op": "tile", "cols": 4, "rows": 1, "overlap_pct": 0.15},
       {"op": "scale_to", "max_side": 1600},
       {"op": "pad_to", "width": 2400, "height": 1600},
       {"op": "flatten_to_color", "color": "#FFFFFF"}
    ]
  }

If `compositor_spec` is missing or empty, the compositor still runs a SAFE
default pass: detect-and-remove a solid background, normalize to PNG with
alpha, never touch pixels otherwise. So every item gets at least clean alpha.
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from typing import Any

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    from PIL import Image, ImageOps
except ImportError as e:  # pragma: no cover
    raise SystemExit(
        "Pillow is required for the vector compositor. "
        "Add `Pillow>=10.0` to requirements.txt and re-install."
    ) from e


# ---------- color helpers ----------

NAMED = {
    "white": (255, 255, 255),
    "black": (0, 0, 0),
    "green": (0, 177, 64),       # #00B140 — the scenery chroma green
    "chroma_green": (0, 177, 64),
    "shutterstock_green": (0, 177, 64),
    "transparent": None,
}


def _parse_color(value: str | None, default: tuple[int, int, int] = (0, 0, 0)
                 ) -> tuple[int, int, int]:
    if not value:
        return default
    if value in NAMED and NAMED[value] is not None:
        return NAMED[value]
    s = value.strip().lstrip("#")
    if len(s) == 3:
        s = "".join(c * 2 for c in s)
    if len(s) == 6:
        try:
            return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))
        except ValueError:
            pass
    return default


def _color_distance(c1: tuple[int, int, int],
                    c2: tuple[int, int, int]) -> float:
    return ((c1[0] - c2[0]) ** 2 +
            (c1[1] - c2[1]) ** 2 +
            (c1[2] - c2[2]) ** 2) ** 0.5


# ---------- background detection ----------

def _detect_bg_color(img: Image.Image,
                     hint: str | None = None
                     ) -> tuple[tuple[int, int, int] | None, str]:
    """Return (rgb, source) where source is "hint", "corners", or "none".

    If the image has meaningful alpha already, returns (None, "alpha").
    """
    if img.mode == "RGBA":
        # If a meaningful chunk of pixels are already transparent, trust it.
        a = img.split()[3]
        # Check the histogram of alpha — if at least 5% are fully transparent
        # AND at least 5% are fully opaque, we already have alpha.
        hist = a.histogram()
        total = sum(hist)
        if total > 0:
            transparent_pct = hist[0] / total
            opaque_pct = hist[255] / total
            if transparent_pct > 0.05 and opaque_pct > 0.05:
                return (None, "alpha")

    if hint and hint != "auto":
        return (_parse_color(hint), "hint")

    rgb = img.convert("RGB")
    w, h = rgb.size
    # Sample 12 corner-region pixels (3 per corner).
    samples = []
    for cx, cy in [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]:
        for dx, dy in [(0, 0), (1, 0), (0, 1)]:
            x = max(0, min(w - 1, cx + (dx if cx == 0 else -dx)))
            y = max(0, min(h - 1, cy + (dy if cy == 0 else -dy)))
            samples.append(rgb.getpixel((x, y)))

    # Use the median (per-channel) so a stray dark pixel doesn't poison.
    rs = sorted(s[0] for s in samples)
    gs = sorted(s[1] for s in samples)
    bs = sorted(s[2] for s in samples)
    mid = len(samples) // 2
    median = (rs[mid], gs[mid], bs[mid])

    # If the corners disagree wildly the image probably has no solid bg.
    # Compute spread.
    spread = max(rs[-1] - rs[0], gs[-1] - gs[0], bs[-1] - bs[0])
    if spread > 60:
        return (None, "none")
    return (median, "corners")


def _tolerance_for(bg: tuple[int, int, int]) -> int:
    """Looser tolerance for white (anti-aliased edges fade into white),
    tighter for saturated backgrounds (green needs to keep prop greens)."""
    r, g, b = bg
    if r > 240 and g > 240 and b > 240:
        return 28          # white
    # saturated chroma — stay tight so prop's own green/red survives.
    return 24


# ---------- core ops ----------

def _key_out_color(img: Image.Image,
                   bg: tuple[int, int, int],
                   tolerance: int) -> Image.Image:
    """Replace pixels within `tolerance` of `bg` with full transparency.
    Soft edges around the threshold get partial alpha so the cut isn't crispy.
    """
    rgba = img.convert("RGBA")
    px = rgba.load()
    w, h = rgba.size
    soft = max(8, tolerance // 2)
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            d = _color_distance((r, g, b), bg)
            if d <= tolerance:
                px[x, y] = (r, g, b, 0)
            elif d <= tolerance + soft:
                # ramp alpha from 0 (at threshold) to current alpha (at +soft)
                ramp = (d - tolerance) / soft
                px[x, y] = (r, g, b, int(a * ramp))
    return rgba


def _silhouette(img: Image.Image,
                color: tuple[int, int, int],
                opacity: float) -> Image.Image:
    """Replace every visible pixel with `color` and scale alpha by opacity."""
    rgba = img.convert("RGBA")
    r0, g0, b0 = color
    a_scale = max(0.0, min(1.0, opacity))
    px = rgba.load()
    w, h = rgba.size
    for y in range(h):
        for x in range(w):
            _, _, _, a = px[x, y]
            if a == 0:
                continue
            px[x, y] = (r0, g0, b0, int(a * a_scale))
    return rgba


def _tile(img: Image.Image, cols: int, rows: int,
          overlap_pct: float) -> Image.Image:
    cols = max(1, int(cols))
    rows = max(1, int(rows))
    overlap_pct = max(0.0, min(0.5, float(overlap_pct or 0.0)))
    rgba = img.convert("RGBA")
    iw, ih = rgba.size
    step_x = int(iw * (1.0 - overlap_pct))
    step_y = int(ih * (1.0 - overlap_pct))
    canvas_w = step_x * (cols - 1) + iw
    canvas_h = step_y * (rows - 1) + ih
    canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    for r in range(rows):
        for c in range(cols):
            x = c * step_x
            y = r * step_y
            canvas.alpha_composite(rgba, (x, y))
    return canvas


def _scale_to(img: Image.Image, max_side: int) -> Image.Image:
    max_side = max(64, int(max_side))
    w, h = img.size
    longest = max(w, h)
    if longest <= max_side:
        return img
    scale = max_side / longest
    new = (max(1, int(w * scale)), max(1, int(h * scale)))
    return img.resize(new, Image.LANCZOS)


def _pad_to(img: Image.Image, width: int, height: int) -> Image.Image:
    width = max(img.size[0], int(width))
    height = max(img.size[1], int(height))
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    ox = (width - img.size[0]) // 2
    oy = (height - img.size[1]) // 2
    canvas.alpha_composite(img.convert("RGBA"), (ox, oy))
    return canvas


def _flatten_to_color(img: Image.Image,
                      color: tuple[int, int, int]) -> Image.Image:
    rgba = img.convert("RGBA")
    bg = Image.new("RGBA", rgba.size, color + (255,))
    bg.alpha_composite(rgba)
    return bg.convert("RGB")


# ---------- public entry ----------

def composite_one(raw_path: Path,
                  target_path: Path,
                  compositor_spec: dict | None) -> dict[str, Any]:
    """Run the spec on `raw_path` and write the composed PNG to `target_path`.

    Always force PNG output. The orchestrator passes us the same target the
    downloader wrote, but we re-extension it to .png to guarantee alpha.
    """
    raw_path = Path(raw_path)
    target_path = Path(target_path).with_suffix(".png")
    spec = compositor_spec or {}
    ops_applied: list[str] = []
    notes: list[str] = []

    if not raw_path.exists():
        return {"status": "FAIL_no_raw", "ops_applied": [], "input_bytes": 0,
                "output_bytes": 0, "saved_path": str(target_path),
                "notes": f"raw not found: {raw_path}"}

    input_bytes = raw_path.stat().st_size
    try:
        img = Image.open(raw_path)
        img.load()
    except Exception as e:
        return {"status": "FAIL_open", "ops_applied": [], "input_bytes": input_bytes,
                "output_bytes": 0, "saved_path": str(target_path),
                "notes": f"{type(e).__name__}: {e}"}

    # Normalize palette / 1-bit to RGBA so all ops are uniform.
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGBA")

    # ---- 1) Background removal (default ON; spec can disable) ----
    remove_bg = spec.get("remove_background", True)
    if remove_bg:
        bg, source = _detect_bg_color(img, spec.get("background_hint"))
        if bg is not None:
            tol = _tolerance_for(bg)
            img = _key_out_color(img, bg, tol)
            ops_applied.append(f"remove_background({source}={bg}, tol={tol})")
        else:
            ops_applied.append(f"remove_background(skipped: {source})")
    else:
        ops_applied.append("remove_background(disabled)")

    # ---- 2) Apply transforms in order ----
    for tr in spec.get("transforms", []) or []:
        op = tr.get("op", "").lower()
        if op == "silhouette":
            color = _parse_color(tr.get("color"), (0, 0, 0))
            opacity = float(tr.get("opacity", 1.0))
            img = _silhouette(img, color, opacity)
            ops_applied.append(f"silhouette(color={color}, opacity={opacity})")
        elif op == "tile":
            cols = int(tr.get("cols", 1))
            rows = int(tr.get("rows", 1))
            overlap = float(tr.get("overlap_pct", 0.0))
            img = _tile(img, cols, rows, overlap)
            ops_applied.append(f"tile({cols}x{rows}, overlap={overlap})")
        elif op == "scale_to":
            max_side = int(tr.get("max_side", 1600))
            img = _scale_to(img, max_side)
            ops_applied.append(f"scale_to({max_side})")
        elif op == "pad_to":
            w = int(tr.get("width", img.size[0]))
            h = int(tr.get("height", img.size[1]))
            img = _pad_to(img, w, h)
            ops_applied.append(f"pad_to({w}x{h})")
        elif op == "flatten_to_color":
            color = _parse_color(tr.get("color"), (255, 255, 255))
            img = _flatten_to_color(img, color)
            ops_applied.append(f"flatten_to_color({color})")
        else:
            notes.append(f"unknown op: {op}")

    # ---- 3) Save as PNG with alpha (unless flatten was requested last) ----
    target_path.parent.mkdir(parents=True, exist_ok=True)
    save_kwargs: dict[str, Any] = {"optimize": True}
    if img.mode == "RGB":
        # flatten_to_color was the last op; keep RGB.
        img.save(target_path, format="PNG", **save_kwargs)
    else:
        img.convert("RGBA").save(target_path, format="PNG", **save_kwargs)

    output_bytes = target_path.stat().st_size

    # If we made the file smaller in a way that suggests we keyed too
    # aggressively, leave a note for the orchestrator's checker.
    if output_bytes < 0.05 * input_bytes:
        notes.append("output is <5% of input — possible over-key")

    # NOTE: this compositor never deletes the raw input. The caller (the
    # orchestrator) decides whether to drop a stale .jpg next to a fresh
    # .png. Keeping the raw intact also lets a smoke test re-run without
    # losing the source.

    return {
        "status": "OK",
        "ops_applied": ops_applied,
        "input_bytes": input_bytes,
        "output_bytes": output_bytes,
        "saved_path": str(target_path),
        "notes": "; ".join(notes) if notes else "",
    }


# ---------- CLI for manual reruns ----------

def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print("usage: vector_compositor.py <raw_path> <target_path> [<spec_json>]")
        return 1
    raw = Path(argv[1])
    target = Path(argv[2])
    spec: dict | None = None
    if len(argv) > 3:
        spec_arg = argv[3]
        if Path(spec_arg).exists():
            spec = json.loads(Path(spec_arg).read_text("utf-8"))
        else:
            spec = json.loads(spec_arg)
    result = composite_one(raw, target, spec)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "OK" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
