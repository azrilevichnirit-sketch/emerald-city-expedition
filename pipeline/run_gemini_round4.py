"""Round-4 Imagen 4 retry for 3 tools that failed round 3. Drops personGeneration
restriction (blocked paraglider), rewords prompts from scratch to avoid the specific
failure modes observed in round 3.
"""
import base64
import json
import time
import urllib.request
import urllib.error
from pathlib import Path
from rembg import remove
from PIL import Image

PROJECT = Path(r"C:/Users/azril/OneDrive/Desktop/fincail_game/new")
KEY_FILE = PROJECT / "keys" / "gimini_key - Copy" / "key.txt"
OUT_DIR = PROJECT / "pipeline" / "review" / "tools_qa_gemini"
STATE_FILE = PROJECT / "pipeline" / "gemini_state_r4.json"

MODEL = "imagen-4.0-generate-001"
ENDPOINT = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:predict"
CHROMA = (0, 0xB1, 0x40)
API_KEY = KEY_FILE.read_text(encoding="utf-8").strip()

# Rewritten prompts — positive descriptions only, no negative cues that could trip safety.
PROMPTS = {
    "גלשן_מ01": (
        "A vibrant multicolored paragliding wing canopy laid out flat on the ground, "
        "crescent-shaped airfoil fabric showing rainbow stripes in red orange yellow green "
        "and blue, all cells inflated and puffy with the full U-curve silhouette visible, "
        "thin white suspension lines fanning out from underneath toward a central triangle "
        "harness hanging off frame, photographed from slightly in front at ground level on "
        "a grassy clearing, sports equipment catalog photography, nobody flying it, sunny "
        "daylight, crisp detail."
    ),
    "חבל_קשרים_מ08": (
        "A thick rugged beige manila climbing rope hanging straight vertically down the "
        "center of the frame, about four centimeters diameter, with FIVE very prominent "
        "bulky chunky knots tied along its length at regular intervals, each knot clearly "
        "distinct and readable as a figure-eight knot. The rope is set against a dark "
        "chocolate-brown plain solid matte background for strong contrast, dramatic side "
        "lighting making the rope texture pop, tightly cropped so the rope fills the "
        "vertical axis of the frame, studio product shot of climbing equipment."
    ),
    "מפה_מ03": (
        "An old weathered pirate treasure map drawn on thick parchment paper scroll, the "
        "parchment is clearly three-dimensional with curled rolled-up edges on the left and "
        "right sides like a scroll partly unrolled, the center flat portion shows hand-drawn "
        "brown ink illustrations of an island with palm trees, a compass rose symbol in the "
        "top corner, dotted trail lines crossing the landscape, and a large bold red X mark "
        "in the middle marking the treasure spot. The parchment rests on a dark mahogany "
        "wood table photographed from a 3/4 aerial angle, warm directional lamplight casting "
        "soft shadows into the curled edges, top-down pirate map prop photography, NO "
        "animals, NO people, just the map document."
    ),
}

STUDIO = (" Sharp focus, subject fills most of frame, square composition, photographic "
          "realism, no text captions or watermarks.")


def generate_one(slug, prompt):
    body = {
        "instances": [{"prompt": prompt + STUDIO}],
        "parameters": {"sampleCount": 1, "aspectRatio": "1:1"},
    }
    url = f"{ENDPOINT}?key={API_KEY}"
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"status": "error_http", "code": e.code, "error": e.read().decode("utf-8", errors="replace")[:500]}

    preds = data.get("predictions") or []
    if not preds or not preds[0].get("bytesBase64Encoded"):
        return {"status": "error_no_preds", "resp": str(data)[:500]}

    raw = OUT_DIR / f"{slug}_r4_raw.png"
    raw.write_bytes(base64.b64decode(preds[0]["bytesBase64Encoded"]))

    rembg_path = OUT_DIR / f"{slug}_r4_rembg.png"
    remove(Image.open(raw)).save(rembg_path)

    final = OUT_DIR / f"{slug}_r4_final.png"
    rgba = Image.open(rembg_path).convert("RGBA")
    bg = Image.new("RGB", rgba.size, CHROMA)
    bg.paste(rgba, mask=rgba.split()[3])
    bg.save(final)
    return {"status": "ok", "raw": str(raw), "final": str(final)}


def main():
    state = {"tools": {}}
    for slug, prompt in PROMPTS.items():
        print(f"\n{slug}", flush=True)
        r = generate_one(slug, prompt)
        state["tools"][slug] = r
        STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  -> {r['status']}", flush=True)


if __name__ == "__main__":
    main()
