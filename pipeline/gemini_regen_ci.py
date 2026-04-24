"""Gemini Imagen regen — CI-safe orchestrator.

Reads pipeline/gemini_state_rejects.json (items that failed earlier rounds),
retries each via Imagen 4.0, applies rembg + chroma composite to #00B140,
writes a new attempt log, and (in CI) the workflow commits results back.

- Paths are relative to the repo root (works on GitHub Actions and locally).
- API key comes from env GEMINI_API_KEY (falls back to GEMINI_API_KEY_2), else
  keys/gimini_key - Copy/key.txt for local runs.
- Silently no-ops if rejects.json is missing or empty (cron-friendly).
"""
from __future__ import annotations

import base64
import io
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT = Path(__file__).resolve().parent.parent
REJECTS = PROJECT / "pipeline" / "gemini_state_rejects.json"
OUT_DIR = PROJECT / "pipeline" / "review" / "tools_qa_gemini_ci"
STATE_OUT = PROJECT / "pipeline" / "gemini_regen_ci_state.json"
OUT_DIR.mkdir(parents=True, exist_ok=True)

MODEL = "imagen-4.0-generate-001"
ENDPOINT = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:predict"
CHROMA = (0, 0xB1, 0x40)


def load_key() -> str:
    for env in ("GEMINI_API_KEY", "GEMINI_API_KEY_2"):
        v = os.environ.get(env)
        if v:
            return v.strip()
    f = PROJECT / "keys" / "gimini_key - Copy" / "key.txt"
    if f.exists():
        return f.read_text("utf-8").strip().split("\n")[0].strip()
    raise RuntimeError("missing GEMINI_API_KEY env var and no local key file")


def imagen_generate(prompt: str, key: str) -> bytes:
    body = json.dumps({
        "instances": [{"prompt": prompt}],
        "parameters": {"sampleCount": 1, "aspectRatio": "1:1"},
    }).encode("utf-8")
    req = urllib.request.Request(
        ENDPOINT + f"?key={key}", data=body, method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=180) as r:
        resp = json.loads(r.read().decode("utf-8"))
    preds = resp.get("predictions", [])
    if not preds or "bytesBase64Encoded" not in preds[0]:
        raise RuntimeError(f"no image in response: {str(resp)[:300]}")
    return base64.b64decode(preds[0]["bytesBase64Encoded"])


def rembg_and_chroma(raw_png: bytes) -> bytes:
    """Remove background and composite onto #00B140."""
    from PIL import Image
    from rembg import remove

    cut = remove(raw_png)
    fg = Image.open(io.BytesIO(cut)).convert("RGBA")
    bg = Image.new("RGBA", fg.size, CHROMA + (255,))
    bg.paste(fg, (0, 0), fg)
    buf = io.BytesIO()
    bg.convert("RGB").save(buf, "PNG")
    return buf.getvalue()


def run() -> int:
    if not REJECTS.exists():
        print("no rejects.json — nothing to regenerate. exit 0.")
        STATE_OUT.write_text(json.dumps(
            {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
             "processed": [], "skipped_reason": "no_rejects_file"},
            ensure_ascii=False, indent=2), "utf-8")
        return 0

    data = json.loads(REJECTS.read_text("utf-8"))
    tools = data.get("tools", {})
    if not tools:
        print("rejects.json is empty. nothing to do.")
        STATE_OUT.write_text(json.dumps(
            {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
             "processed": [], "skipped_reason": "empty_rejects"},
            ensure_ascii=False, indent=2), "utf-8")
        return 0

    key = load_key()
    results = []
    for slug, meta in tools.items():
        prompt = meta.get("prompt", "")
        if not prompt:
            results.append({"slug": slug, "status": "SKIP_no_prompt"})
            continue
        try:
            print(f"[{slug}] Imagen…")
            raw = imagen_generate(prompt, key)
            raw_path = OUT_DIR / f"{slug}_raw.png"
            raw_path.write_bytes(raw)
            try:
                final = rembg_and_chroma(raw)
                final_path = OUT_DIR / f"{slug}_final.png"
                final_path.write_bytes(final)
                results.append({"slug": slug, "status": "OK",
                                 "raw": str(raw_path.relative_to(PROJECT)),
                                 "final": str(final_path.relative_to(PROJECT))})
                print(f"  [{slug}] OK -> {final_path.name}")
            except Exception as e:
                results.append({"slug": slug, "status": "OK_raw_only",
                                 "error": f"{type(e).__name__}: {e}",
                                 "raw": str(raw_path.relative_to(PROJECT))})
                print(f"  [{slug}] raw written but composite failed: {e}")
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")[:300]
            results.append({"slug": slug, "status": f"HTTP_{e.code}",
                             "error": body})
            print(f"  [{slug}] HTTP {e.code}: {body[:150]}")
        except Exception as e:
            results.append({"slug": slug, "status": "EXC",
                             "error": f"{type(e).__name__}: {e}"})
            print(f"  [{slug}] {type(e).__name__}: {e}")
        time.sleep(2)

    STATE_OUT.write_text(json.dumps({
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "model": MODEL,
        "processed": results,
    }, ensure_ascii=False, indent=2), "utf-8")
    print(f"\nDone. state -> {STATE_OUT.relative_to(PROJECT)}")
    print(f"raw+final assets -> {OUT_DIR.relative_to(PROJECT)}")
    return 0


if __name__ == "__main__":
    sys.exit(run())
