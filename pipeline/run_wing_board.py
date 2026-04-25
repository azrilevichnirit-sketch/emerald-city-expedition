"""Director's cinematic re-pivot for גלשן_מ01 — a winged flying BOARD
(foot-attached, intuitive reading), per Nirit's intuitive-identification rule.
Round 9.
"""
import base64
import json
import urllib.request
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
    "A single heroic cinematic adventure-game inventory icon of a flying "
    "surfboard — a sleek aerodynamic deck-shaped board with two small "
    "swept-back wing-fins jutting from its left and right sides. Prominent "
    "bright orange foot-straps are clearly mounted on the TOP surface of the "
    "deck, signaling 'you stand on this with your feet.' The board is rich "
    "dark polished wood down the center with bold saturated adventure-color "
    "stripes — crimson red, burnt sunset gold, and cobalt blue — running "
    "along its edges and along the wing-fins. The board is tilted dynamically "
    "at a 3/4 low front-side angle, banking 15 degrees as if riding an "
    "invisible air current. Warm golden-hour sunlight rakes across the top "
    "surface from the upper-left and a cool cobalt rim-light glows along the "
    "underside of the wings. Floating isolated centered on a pure white "
    "studio background. No pilot, no rider, no feet, no legs, no person, no "
    "canopy above, no suspension lines, no harness, no ground, no sky, no "
    "clouds — just the winged flying board itself as a single solid "
    "collectible object. Painterly semi-realistic AAA adventure-game "
    "inventory asset art."
)


def imagen(prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{IMAGEN}:predict?key={API_KEY}"
    body = {"instances": [{"prompt": prompt}], "parameters": {"sampleCount": 1, "aspectRatio": "1:1"}}
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                  headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return base64.b64decode(data["predictions"][0]["bytesBase64Encoded"])


def chroma_white(raw_bytes, slug):
    import io
    img = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
    arr = np.array(img).astype(float)
    bg = arr[:30, :30].reshape(-1, 3).mean(axis=0)
    dist = np.linalg.norm(arr - bg, axis=2)
    mask = np.clip((dist - 25) / 35, 0, 1)
    a = mask[..., None]
    comp = (arr * a + CHROMA * (1 - a)).clip(0, 255).astype(np.uint8)
    final = OUT_DIR / f"{slug}_r9_final.png"
    Image.fromarray(comp).save(final)
    return final


def main():
    raw = imagen(PROMPT)
    (OUT_DIR / "גלשן_מ01_r9_raw.png").write_bytes(raw)
    final = chroma_white(raw, "גלשן_מ01")
    print(f"done: {final}")


if __name__ == "__main__":
    main()
