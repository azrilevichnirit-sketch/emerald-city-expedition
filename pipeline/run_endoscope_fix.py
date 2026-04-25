"""Re-render מצלמה_זעירה_מ10 — endoscopic/probe camera, NOT a stills camera.

Nirit's direction: the icon should read instantly as a medical/exploration
lens-probe camera (endoscope-style) — the kind you use to peek/examine inside
a space. The previous icon read as a photo camera, which doesn't match the
'investigate impulsively' slot semantics.
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
FINAL_DIR = PROJECT / "assets" / "tools_final"
API_KEY = KEY_FILE.read_text(encoding="utf-8").strip()
IMAGEN = "imagen-4.0-generate-001"
CHROMA = np.array([0, 0xB1, 0x40], dtype=float)

PROMPT = (
    "A single heroic cinematic adventure-game inventory icon of a "
    "MINIATURE ENDOSCOPIC PROBE CAMERA — the kind used in medical procedures "
    "or for inspecting inside tight spaces. The device consists of: a thin "
    "flexible silver-brass metal wand/tube about 15cm long ending in a small "
    "round glass lens tip that glows faintly cyan; attached at the other end "
    "is a small compact handheld grip with a tiny round viewfinder screen "
    "showing a faint image. The whole thing reads instantly as 'EXPLORATION "
    "CAMERA — peek inside, investigate, examine' — NOT a photography camera, "
    "NOT a smartphone, NOT a dSLR. This is a surgical/industrial borescope "
    "aesthetic in adventure-game style. Floating isolated centered in a "
    "square 1:1 composition on a pure #00B140 CHROMA KEY GREEN STUDIO "
    "BACKGROUND (flat solid chroma green, no gradients, no shadows on the "
    "background). The object itself is in full bright light, 3/4 front angle, "
    "slightly tilted dynamic pose. Adventure-game painterly semi-realistic "
    "AAA icon art. Colors: polished silver wand, warm brass handle accents, "
    "cyan lens glow, cobalt blue viewfinder screen. No text, no numbers, no "
    "letters. No human hands. The probe and grip fill the frame."
)


def imagen(prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{IMAGEN}:predict?key={API_KEY}"
    body = {"instances": [{"prompt": prompt}],
            "parameters": {"sampleCount": 1, "aspectRatio": "1:1"}}
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                  headers={"Content-Type": "application/json"},
                                  method="POST")
    with urllib.request.urlopen(req, timeout=180) as resp:
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
    final = OUT_DIR / f"{slug}_rC_final.png"
    Image.fromarray(comp).save(final)
    return final


def main():
    slug = "מצלמה_זעירה_מ10"
    raw = imagen(PROMPT)
    (OUT_DIR / f"{slug}_rC_raw.png").write_bytes(raw)
    final = chroma(raw, slug)

    # Replace in assets/tools_final/
    target = FINAL_DIR / f"{slug}.png"
    target.write_bytes(final.read_bytes())
    print(f"new raw:   {OUT_DIR / f'{slug}_rC_raw.png'}")
    print(f"chromaed:  {final}")
    print(f"replaced:  {target}")


if __name__ == "__main__":
    main()
