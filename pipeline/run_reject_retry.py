"""Re-generate 2 tools rejected by Nirit:
- גלשן_מ01: must be clearly identifiable as paraglider (not round parachute/balloon)
  → side-profile, crescent airfoil, air cells on leading edge, harness hanging below
- מצנח_בסיס_מ11: must be OPEN canopy in the AIR (not a packed backpack)
  → rectangular deployed ram-air canopy, suspension lines, harness below

Uses Imagen 4; manual chroma-key on uniform sky (rembg can't cleanly separate
thin suspension lines from blue sky).
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
STATE_FILE = PROJECT / "pipeline" / "gemini_state_rejects.json"

MODEL = "imagen-4.0-generate-001"
ENDPOINT = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:predict"
CHROMA = np.array([0, 0xB1, 0x40], dtype=float)
API_KEY = KEY_FILE.read_text(encoding="utf-8").strip()

PROMPTS = {
    "גלשן_מ01": (
        "A single colorful paragliding wing in full flight, seen from the SIDE in clear "
        "PROFILE view so the distinctive long horizontal banana-curved crescent airfoil "
        "shape is unmistakable. The wing is a wide elongated inflatable fabric airfoil "
        "stretching across the entire width of the frame, with many individual cells in "
        "alternating red, yellow, green and blue fabric. The LEADING EDGE facing forward "
        "shows a row of small dark rectangular air intake openings — the signature feature "
        "of a paragliding ram-air wing. About thirty thin black suspension lines spread "
        "out from underneath the wing and converge downward into a small empty cloth "
        "harness seat hanging below the center of the wing. The wing is mid-air, floating, "
        "photographed against a plain uniform light blue sky with no clouds and no ground "
        "visible. No pilot in the harness. Sports catalog photography of paragliding "
        "equipment, side-profile angle, crescent airfoil shape clearly readable."
    ),
    "מצנח_בסיס_מ11": (
        "A fully deployed open skydiving ram-air parachute canopy in mid-flight, shown "
        "from below at a 3/4 angle so the full rectangular gliding wing is clearly visible "
        "from underneath. The canopy is a rectangular NINE-CELL ram-air parachute in bold "
        "orange and white alternating vertical stripes, stiff and fully inflated like a "
        "rigid rectangular mattress floating in the sky. Many thin black suspension lines "
        "fan down from the bottom surface of the canopy and converge into a small empty "
        "climbing harness hanging below the center, with no jumper in it. The canopy is "
        "photographed in an open clear blue sky with a few soft white clouds in the "
        "distance, no ground visible. Skydiving stock photography, the rectangular gliding "
        "parachute shape is unambiguously an open deployed BASE/skydiving canopy, not a "
        "backpack and not a round classic parachute."
    ),
}


def generate(slug, prompt):
    body = {
        "instances": [{"prompt": prompt}],
        "parameters": {"sampleCount": 1, "aspectRatio": "1:1"},
    }
    req = urllib.request.Request(
        f"{ENDPOINT}?key={API_KEY}",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    b64 = data["predictions"][0]["bytesBase64Encoded"]
    raw = OUT_DIR / f"{slug}_r5_raw.png"
    raw.write_bytes(base64.b64decode(b64))
    return raw


def chroma_key_sky(raw_path, slug):
    """Sky-blue chroma keying: pixels close to sky color become transparent.
    The suspension lines are thin and dark against sky — keep anything not sky-blue.
    """
    img = Image.open(raw_path).convert("RGB")
    arr = np.array(img).astype(float)
    # Sample sky from top-left corner (which is empty sky)
    sky = arr[:40, :40].reshape(-1, 3).mean(axis=0)
    # Distance in RGB from sky
    dist = np.linalg.norm(arr - sky, axis=2)
    # Pixels far from sky = foreground; smooth ramp 20..60
    mask = np.clip((dist - 20) / 40, 0, 1)
    alpha = (mask * 255).astype(np.uint8)
    # Composite
    a = alpha[..., None] / 255.0
    comp = (arr * a + CHROMA * (1 - a)).clip(0, 255).astype(np.uint8)
    final = OUT_DIR / f"{slug}_r5_final.png"
    Image.fromarray(comp).save(final)
    rgba_arr = np.concatenate([arr.astype(np.uint8), alpha[..., None]], axis=2)
    Image.fromarray(rgba_arr, "RGBA").save(OUT_DIR / f"{slug}_r5_rembg.png")
    return final


def main():
    state = {"tools": {}}
    for slug, prompt in PROMPTS.items():
        print(f"\n{slug}", flush=True)
        raw = generate(slug, prompt)
        print(f"  raw: {raw.name}", flush=True)
        final = chroma_key_sky(raw, slug)
        print(f"  final: {final.name}", flush=True)
        state["tools"][slug] = {"raw": str(raw), "final": str(final), "prompt": prompt}
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\nDONE")


if __name__ == "__main__":
    main()
