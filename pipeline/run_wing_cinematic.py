"""Director's cinematic wing retry for גלשן_מ01 — AAA adventure-game asset style.
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
    "A single paragliding wing presented as a heroic cinematic game-asset inventory icon. "
    "The wing is shown from a 3/4 low front-side angle so its wide elongated crescent airfoil "
    "shape reads instantly as a flying wing. Bold saturated adventure-game color stripes — "
    "deep crimson red, burnt sunset orange, warm gold, and cobalt blue — alternating across "
    "the fabric cells, each cell glowing as warm golden-hour sunlight rakes across the top "
    "surface from the upper-left and a soft rim light glows along the trailing edge. The wing "
    "is tilted dynamically as if banking into a thermal, conveying the thrill of the parachute "
    "opening mid-air. Thin suspension lines fan down from the bottom surface like harp strings, "
    "catching glints of sunlight. No pilot, no harness, no ground, no horizon, no clouds, no "
    "mist, no smoke — just the wing itself, a single solid isolated object, floating centered "
    "on a clean pure white studio background, as a heroic adventure-game collectible item. "
    "Painterly semi-realistic cinematic illustration style, AAA adventure game inventory art, "
    "evokes the moment a paraglider canopy catches air."
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
    final = OUT_DIR / f"{slug}_r8_final.png"
    Image.fromarray(comp).save(final)
    return final


def main():
    raw = imagen(PROMPT)
    (OUT_DIR / "גלשן_מ01_r8_raw.png").write_bytes(raw)
    final = chroma_white(raw, "גלשן_מ01")
    print(f"done: {final}")


if __name__ == "__main__":
    main()
