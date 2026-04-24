"""Shutterstock DOWNLOAD CHECKER — physical verification on the real file.

Runs after the downloader writes the binary to disk. Does TWO passes:

  1. Deterministic (PIL) — file exists, opens, matches format, correct
     resolution, has real alpha when the master asked for PNG.
  2. Visual (Claude Vision) — loads the real file and compares it to the
     master's `intent_for_checker` + `hard_rejects`. Catches watermarks,
     hidden text, brand logos, decorative junk that snuck past the thumbnail
     review.

Returns PASS (orchestrator keeps the file and moves on) or RETRY with
concrete feedback the master can act on.

NEVER modifies the file. Read-only inspection.
"""
from __future__ import annotations

import base64
import io
import json
import os
import sys
import urllib.request
from pathlib import Path
from typing import Any

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

try:
    from PIL import Image
except Exception as _e:
    print(f"FATAL: Pillow (PIL) is required. pip install Pillow. ({_e})",
          file=sys.stderr)
    raise

PROJECT = Path(__file__).resolve().parent.parent
KEYS = PROJECT / "keys"


def _load_key(env_var: str, file_path: Path) -> str:
    v = os.environ.get(env_var)
    if v:
        return v.strip()
    if file_path.exists():
        return file_path.read_text("utf-8").strip()
    raise RuntimeError(f"missing {env_var} env var or file {file_path}")


CLAUDE_KEY = _load_key("CLAUDE_API_KEY", KEYS / "claude" / "key.txt")
CLAUDE_MODEL = "claude-sonnet-4-5-20250929"


CHECKER_SYSTEM = """You are the SHUTTERSTOCK DOWNLOAD CHECKER. The downloader just licensed and saved an image file. You now open that file and verify — with your own eyes — that it matches the master's intent and doesn't carry any hidden disqualifying element that a thumbnail-sized preview couldn't reveal.

Things ONLY visible at full resolution:
  - contributor watermarks ("Sample", "Preview", "ShutterstockPro") in corners
  - small text/copyright in edges
  - brand logos hidden in product labels
  - decorative framing the thumbnail cropped off
  - visible edges where an AI-generated image has inconsistency artifacts

You return a single JSON verdict. Be specific in the reason — the master
reads it and makes a surgical change.

{
  "verdict": "match|miss",
  "reason": "...",
  "hard_reject_found": null | "<which rule from hard_rejects>"
}
"""


def _deterministic_checks(path: Path, master_cmd: dict) -> dict:
    checks: dict[str, Any] = {
        "file_exists": False,
        "size_bytes": 0,
        "pil_opens": False,
        "format_matches_master": False,
        "resolution_ok": False,
        "has_alpha_channel": None,
        "transparent_pixel_percent": None,
        "notes": [],
    }
    lic = master_cmd.get("license", {})
    fmt_want = (lic.get("format") or "").lower()

    if not path.exists():
        checks["notes"].append("file not found on disk")
        return checks
    checks["file_exists"] = True
    checks["size_bytes"] = path.stat().st_size
    if checks["size_bytes"] < 1024:
        checks["notes"].append("file smaller than 1 KB — likely truncated or error body")
        return checks

    # Magic-byte format detection.
    head = path.read_bytes()[:12]
    detected = None
    if head.startswith(b"\x89PNG"):
        detected = "png"
    elif head[:3] == b"\xff\xd8\xff":
        detected = "jpg"
    elif head[:2] == b"%!":
        detected = "eps"
    elif head[:5] == b"<?xml" or head[:4] == b"<svg":
        detected = "svg"
    checks["detected_format"] = detected
    if fmt_want and detected == fmt_want:
        checks["format_matches_master"] = True
    elif fmt_want and detected != fmt_want:
        checks["notes"].append(f"file is {detected} but master asked for {fmt_want}")

    # PIL open for raster only.
    if detected in ("png", "jpg"):
        try:
            with Image.open(path) as img:
                img.load()
                checks["pil_opens"] = True
                w, h = img.size
                checks["width"] = w
                checks["height"] = h
                if max(w, h) >= 1500:
                    checks["resolution_ok"] = True
                else:
                    checks["notes"].append(f"resolution {w}x{h} below 1500px long edge")

                if img.mode in ("RGBA", "LA", "PA"):
                    alpha = img.getchannel("A") if img.mode == "RGBA" else img.split()[-1]
                    pixels = alpha.getdata()
                    total = len(pixels)
                    transparent = sum(1 for a in pixels if a < 255)
                    full_transparent = sum(1 for a in pixels if a == 0)
                    pct = (transparent / total * 100.0) if total else 0.0
                    full_pct = (full_transparent / total * 100.0) if total else 0.0
                    checks["has_alpha_channel"] = True
                    checks["transparent_pixel_percent"] = round(pct, 2)
                    checks["fully_transparent_percent"] = round(full_pct, 2)
                    if fmt_want == "png" and full_pct < 1.0:
                        checks["notes"].append(
                            "PNG has RGBA mode but <1% fully-transparent pixels — "
                            "likely a fake-alpha export (opaque everywhere). "
                            "Master should switch to EPS or illustration+jpg."
                        )
                else:
                    checks["has_alpha_channel"] = False
                    if fmt_want == "png":
                        checks["notes"].append(
                            "PNG has no alpha channel (mode=" + img.mode + "). "
                            "Master's image_type=vector should have yielded alpha."
                        )
        except Exception as e:
            checks["notes"].append(f"PIL failed: {type(e).__name__}: {e}")
    else:
        # Vector formats — accept if present and non-trivial.
        checks["pil_opens"] = True
        checks["resolution_ok"] = True
        checks["has_alpha_channel"] = True
        checks["notes"].append(f"{detected} format — skipping raster checks")

    return checks


def _encode_image_for_vision(path: Path, max_edge: int = 1600) -> tuple[str, str]:
    """Return (media_type, base64). Downscale huge images for Vision efficiency."""
    detected = "image/png"
    raw = path.read_bytes()
    if raw.startswith(b"\x89PNG"):
        detected = "image/png"
    elif raw[:3] == b"\xff\xd8\xff":
        detected = "image/jpeg"
    elif raw[:5] == b"<?xml" or raw[:4] == b"<svg":
        # Vision doesn't accept SVG — convert via PIL if we can (we can't
        # natively). Return the raw XML and let the visual check skip.
        return "text/xml", base64.b64encode(raw).decode("ascii")

    try:
        with Image.open(path) as img:
            if img.mode not in ("RGB", "RGBA"):
                img = img.convert("RGBA")
            w, h = img.size
            if max(w, h) > max_edge:
                scale = max_edge / max(w, h)
                img = img.resize((int(w * scale), int(h * scale)))
            buf = io.BytesIO()
            # Preserve alpha if present.
            if img.mode == "RGBA":
                img.save(buf, format="PNG")
                return "image/png", base64.b64encode(buf.getvalue()).decode("ascii")
            img.save(buf, format="JPEG", quality=85)
            return "image/jpeg", base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception:
        return detected, base64.b64encode(raw).decode("ascii")


def _vision_check(path: Path, master_cmd: dict) -> dict:
    intent = master_cmd.get("intent_for_checker", "")
    hard_rejects = master_cmd.get("hard_rejects", [])
    user_text = (
        "MASTER'S INTENT:\n" + intent + "\n\n"
        "HARD REJECTS:\n" + "\n".join(f"  - {hr}" for hr in hard_rejects) + "\n\n"
        "You will now see the actual file the downloader saved. Physically "
        "inspect it. If a watermark, preview-sample text, brand logo, or any "
        "hard_reject element appears — return miss with the specific thing you "
        "saw. If the image cleanly satisfies the intent, return match.\n\n"
        "Output ONLY the JSON verdict, no preamble."
    )
    media_type, b64 = _encode_image_for_vision(path)
    if media_type == "text/xml":
        return {"verdict": "match", "reason": "SVG — visual check skipped", "hard_reject_found": None}

    content = [
        {"type": "text", "text": user_text},
        {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": b64}},
    ]
    body = json.dumps({
        "model": CLAUDE_MODEL,
        "max_tokens": 600,
        "temperature": 0.1,
        "system": CHECKER_SYSTEM,
        "messages": [{"role": "user", "content": content}],
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body, method="POST",
        headers={"x-api-key": CLAUDE_KEY,
                 "anthropic-version": "2023-06-01",
                 "content-type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            d = json.loads(r.read().decode("utf-8"))
    except Exception as e:
        return {"verdict": "miss", "reason": f"vision API error: {type(e).__name__}: {e}",
                "hard_reject_found": None, "_vision_api_failed": True}

    text = "".join(b.get("text", "") for b in d.get("content", []))
    t = text.strip()
    if t.startswith("```"):
        lines = t.split("\n")[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        t = "\n".join(lines).strip()
    try:
        return json.loads(t)
    except Exception:
        s, e = t.find("{"), t.rfind("}")
        if s >= 0 and e > s:
            try:
                return json.loads(t[s:e+1])
            except Exception:
                pass
        return {"verdict": "miss", "reason": f"unparseable vision output: {text[:160]}",
                "hard_reject_found": None}


def check_download(master_cmd: dict, saved_path: Path) -> dict:
    round_num = master_cmd.get("_round", 1)
    slug = master_cmd.get("item_slug") or master_cmd.get("_item", {}).get("slug")

    det = _deterministic_checks(saved_path, master_cmd)
    report: dict = {
        "item_slug": slug,
        "round": round_num,
        "saved_path": str(saved_path),
        "deterministic_checks": det,
    }

    # Gate 1: deterministic must pass before we waste Vision on a broken file.
    det_ok = (det.get("file_exists") and det.get("pil_opens")
              and det.get("format_matches_master") and det.get("resolution_ok"))
    if not det_ok:
        report["vision_check"] = None
        report["verdict"] = "RETRY"
        notes = det.get("notes", [])
        report["feedback_to_master"] = (
            "Downloaded file failed deterministic checks: "
            + "; ".join(notes) if notes else "Downloaded file failed deterministic checks."
        )
        report["status"] = "OK"
        return report

    # Gate 2: visual inspection.
    vision = _vision_check(saved_path, master_cmd)
    report["vision_check"] = vision

    if vision.get("verdict") == "match":
        report["verdict"] = "PASS"
        report["feedback_to_master"] = None
    else:
        report["verdict"] = "RETRY"
        reason = vision.get("reason", "unspecified")
        hr = vision.get("hard_reject_found")
        if hr:
            report["feedback_to_master"] = f"Hard reject triggered on downloaded file: {hr}. Vision said: {reason}"
        else:
            report["feedback_to_master"] = f"Downloaded file failed visual check: {reason}"

    report["status"] = "OK"
    return report


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print("usage: shutterstock_download_checker.py <master_cmd_json> <saved_path>")
        return 1
    master_cmd = json.loads(Path(argv[1]).read_text("utf-8"))
    saved_path = Path(argv[2])
    report = check_download(master_cmd, saved_path)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("verdict") == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
