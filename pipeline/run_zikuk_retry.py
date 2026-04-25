"""Retry זיקוק_מ15 — the first attempt rendered on night-sky background
which chroma-key couldn't remove. Force daylight studio product framing.
"""
import base64
import json
import urllib.request
import io
from pathlib import Path
from PIL import Image
import numpy as np

PROJECT = Path(r"C:/Users/azril/OneDrive/Desktop/fincail_game/new")
KEY_FILE = PROJECT / "keys" / "gimini_key - Copy" / "key.txt"
OUT_DIR = PROJECT / "pipeline" / "review" / "tools_qa_gemini"
API_KEY = KEY_FILE.read_text(encoding="utf-8").strip()
IMAGEN = "imagen-4.0-generate-001"
CHROMA = np.array([0, 0xB1, 0x40], dtype=float)

PROMPT = (
    "A single heroic cinematic adventure-game inventory icon of a "
    "FESTIVE CELEBRATION FIREWORK as a PRODUCT ICON SHOT in bright "
    "daylight studio — NOT a night scene. The firework is an unlit "
    "colorful paper-wrapped rocket tube with bright red-gold-green-blue "
    "spiral stripe wrapping, a small dark fuse at the top, and a thin "
    "wooden launching stick attached to the bottom. Alongside the rocket, "
    "small colorful spark burst icons (small stylized starbursts in "
    "rainbow colors) float around it as decorative motifs, signaling "
    "'this makes colorful celebratory sparks.' Clearly reads as "
    "fireworks/pyrotechnic party firework — Chinese New Year or July 4th "
    "celebration aesthetic. NOT a missile, NOT military, NOT on a dark "
    "night sky — this is a DAYLIGHT STUDIO PRODUCT SHOT. Floating "
    "isolated centered on a PURE BRIGHT WHITE STUDIO BACKGROUND (white, "
    "not black, not dark). No text, no numbers, no letters. Painterly "
    "semi-realistic AAA adventure-game inventory asset art."
)


def imagen(prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{IMAGEN}:predict?key={API_KEY}"
    body = {"instances": [{"prompt": prompt}],
            "parameters": {"sampleCount": 1, "aspectRatio": "1:1"}}
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                  headers={"Content-Type": "application/json"},
                                  method="POST")
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return base64.b64decode(data["predictions"][0]["bytesBase64Encoded"])


def chroma(raw_bytes, slug):
    img = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
    arr = np.array(img).astype(float)
    bg = arr[:30, :30].reshape(-1, 3).mean(axis=0)
    dist = np.linalg.norm(arr - bg, axis=2)
    mask = np.clip((dist - 25) / 35, 0, 1)
    a = mask[..., None]
    comp = (arr * a + CHROMA * (1 - a)).clip(0, 255).astype(np.uint8)
    final = OUT_DIR / f"{slug}_rB_final.png"
    Image.fromarray(comp).save(final)
    return final


def main():
    raw = imagen(PROMPT)
    (OUT_DIR / "זיקוק_מ15_rB_raw.png").write_bytes(raw)
    final = chroma(raw, "זיקוק_מ15")
    print(f"done: {final}")


if __name__ == "__main__":
    main()
