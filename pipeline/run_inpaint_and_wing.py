"""
Nirit feedback round:
- מצנח_בסיס_מ11: keep canopy+lines, remove the person via inpainting (gemini-2.5-flash-image)
- גלשן_מ01: brand-new Imagen 4 prompt for a wide flat double-layer paraglider wing, no figure
"""
import base64
import json
import urllib.request
import urllib.error
from pathlib import Path
from PIL import Image
import numpy as np

PROJECT = Path(r"C:/Users/azril/OneDrive/Desktop/fincail_game/new")
KEY_FILE = PROJECT / "keys" / "gimini_key - Copy" / "key.txt"
OUT_DIR = PROJECT / "pipeline" / "review" / "tools_qa_gemini"
STATE_FILE = PROJECT / "pipeline" / "gemini_state_r6.json"

API_KEY = KEY_FILE.read_text(encoding="utf-8").strip()
IMAGEN = "imagen-4.0-generate-001"
NANO = "gemini-2.5-flash-image"
CHROMA = np.array([0, 0xB1, 0x40], dtype=float)

WING_PROMPT = (
    "A single paragliding wing shown ALONE as a product shot, displayed as a large "
    "horizontally wide double-layer ram-air fabric airfoil. The wing is VERY WIDE and "
    "relatively SHORT in height, a long horizontally elongated shape stretching from "
    "the far left edge to the far right edge of the frame — width-to-height ratio "
    "approximately 5:1 — with a subtle crescent curve. It is built from two parallel "
    "fabric skins (top surface and bottom surface) separated by internal ribs forming "
    "a row of open rectangular air cells along the entire leading edge. Bright rainbow "
    "stripes in red orange yellow green and blue ripstop nylon. Dozens of thin suspension "
    "lines hang straight down from the bottom skin. Floating centered on a plain pure "
    "white studio background. NO person, NO pilot, NO harness seat, NO ground, just the "
    "wing itself. Stock catalog photography of a paraglider canopy as isolated product."
)


def imagen_generate(prompt):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{IMAGEN}:predict?key={API_KEY}"
    body = {"instances": [{"prompt": prompt}], "parameters": {"sampleCount": 1, "aspectRatio": "1:1"}}
    req = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return base64.b64decode(data["predictions"][0]["bytesBase64Encoded"])


def nano_edit(image_bytes, instruction):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{NANO}:generateContent?key={API_KEY}"
    body = {
        "contents": [{
            "parts": [
                {"inline_data": {"mime_type": "image/png", "data": base64.b64encode(image_bytes).decode()}},
                {"text": instruction},
            ]
        }],
        "generationConfig": {"responseModalities": ["IMAGE"]},
    }
    req = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    parts = data["candidates"][0]["content"]["parts"]
    for p in parts:
        inline = p.get("inline_data") or p.get("inlineData")
        if inline:
            return base64.b64decode(inline["data"])
    raise RuntimeError(f"no image in response: {json.dumps(data)[:400]}")


def chroma_key_white(raw_bytes, slug):
    img = Image.open(__import__("io").BytesIO(raw_bytes)).convert("RGB")
    arr = np.array(img).astype(float)
    # Studio white: sample from corner
    bg = arr[:30, :30].reshape(-1, 3).mean(axis=0)
    dist = np.linalg.norm(arr - bg, axis=2)
    mask = np.clip((dist - 30) / 40, 0, 1)
    a = mask[..., None]
    comp = (arr * a + CHROMA * (1 - a)).clip(0, 255).astype(np.uint8)
    final = OUT_DIR / f"{slug}_r6_final.png"
    Image.fromarray(comp).save(final)
    return final


def chroma_key_sky(raw_bytes, slug):
    img = Image.open(__import__("io").BytesIO(raw_bytes)).convert("RGB")
    arr = np.array(img).astype(float)
    sky = arr[:30, :30].reshape(-1, 3).mean(axis=0)
    dist = np.linalg.norm(arr - sky, axis=2)
    mask = np.clip((dist - 25) / 50, 0, 1)
    a = mask[..., None]
    comp = (arr * a + CHROMA * (1 - a)).clip(0, 255).astype(np.uint8)
    final = OUT_DIR / f"{slug}_r6_final.png"
    Image.fromarray(comp).save(final)
    return final


def main():
    state = {"tools": {}}

    # 1. גלשן_מ01 — fresh Imagen 4
    print("גלשן_מ01 — Imagen 4 fresh generation", flush=True)
    raw = imagen_generate(WING_PROMPT)
    (OUT_DIR / "גלשן_מ01_r6_raw.png").write_bytes(raw)
    chroma_key_white(raw, "גלשן_מ01")
    state["tools"]["גלשן_מ01"] = {"method": "imagen4_fresh", "prompt": WING_PROMPT}
    print("  done", flush=True)

    # 2. מצנח_בסיס_מ11 — inpaint to remove person
    print("\nמצנח_בסיס_מ11 — nano-banana inpaint to remove person", flush=True)
    src_path = OUT_DIR / "מצנח_בסיס_מ11_r5_raw.png"
    instruction = (
        "Edit this photograph: remove the person/skydiver hanging in the harness below "
        "the parachute canopy. Keep the orange and white rectangular ram-air parachute "
        "canopy exactly as it is, keep the suspension lines exactly as they are, and keep "
        "the empty harness itself visible but with NO person in it. Fill in the area where "
        "the person was with matching blue sky and clouds continuing naturally. The result "
        "should look like the exact same parachute scene but with an empty harness and no "
        "human figure anywhere in the image."
    )
    edited = nano_edit(src_path.read_bytes(), instruction)
    (OUT_DIR / "מצנח_בסיס_מ11_r6_raw.png").write_bytes(edited)
    chroma_key_sky(edited, "מצנח_בסיס_מ11")
    state["tools"]["מצנח_בסיס_מ11"] = {"method": "nano_inpaint", "instruction": instruction}
    print("  done", flush=True)

    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nDONE")


if __name__ == "__main__":
    main()
