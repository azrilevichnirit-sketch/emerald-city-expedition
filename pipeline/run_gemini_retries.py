"""
Phase 0E — Gemini Imagen 3 fallback for the 11 tools that failed 2 Leonardo rounds.
Uses Google AI Studio REST (no SDK): POST :predict, base64 → PNG → rembg → composite.

Prompts per tool are hand-tailored positive-only descriptions (Imagen 3 ignores
negative_prompt). Target = white studio background; we re-composite on #00B140 after rembg.

Outputs:
  pipeline/review/tools_qa_gemini/{slug}_{raw,rembg,final}.png
  pipeline/gemini_state.json (per-attempt log)
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
OUT_DIR.mkdir(parents=True, exist_ok=True)
STATE_FILE = PROJECT / "pipeline" / "gemini_state.json"

MODEL = "imagen-4.0-generate-001"
ENDPOINT = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:predict"
CHROMA = (0, 0xB1, 0x40)

API_KEY = KEY_FILE.read_text(encoding="utf-8").strip()

STUDIO = (" Photographed as clean studio product photography on a plain pure white seamless "
          "background, soft even lighting with gentle shadow, sharp focus, full object centered "
          "and filling most of the frame, square composition, isolated object, no watermark, "
          "no text overlays.")

PROMPTS = {
    "גלשן_מ01": (
        "A single colorful paragliding wing canopy shown flat and fully inflated, crescent "
        "U-shaped airfoil with bright red, yellow and blue nylon ripstop cells visible, dozens "
        "of thin white suspension lines hanging down from underneath, photographed from slightly "
        "below and 3/4 angle so both the top surface and the lines read clearly."
    ),
    "חבל_קשרים_מ08": (
        "A thick natural-fiber climbing rope hanging straight down vertically with FIVE large "
        "bulky figure-eight knots tied evenly along its length, each knot fat and prominent, "
        "rope about 2 meters long, top of rope disappears upward, bottom end frayed, beige and "
        "tan twisted fibers, photographed straight on."
    ),
    "לום_מ07": (
        "A single red steel crowbar pry tool, long straight heavy metal shaft, one end has a "
        "curved split claw for pulling nails, the other end has a flat chisel tip, painted "
        "glossy red with a black rubber grip in the middle, laid diagonally across the frame, "
        "sharp metallic highlights."
    ),
    "לפיד_יד_מ12": (
        "A handheld medieval wooden torch actively burning: a thick wooden handle about 40cm "
        "long wrapped at the top with oily cloth rags that are on fire with large bright orange "
        "and yellow flames rising 30cm above, wisps of smoke curling up, warm firelight glow, "
        "torch held at 30 degree angle floating in frame, no hand visible."
    ),
    "לפיד_מ05": (
        "A rustic wooden torch standing upright with a burning oil-soaked rag bundle at the top "
        "producing large flickering orange flames reaching upward, tall cylindrical wooden "
        "handle, flames and head fully visible and NOT cut off by frame edges, full torch shown "
        "from base to flame tip, dramatic firelight."
    ),
    "מפה_מ03": (
        "An ancient treasure map on a thick crumpled aged parchment scroll sheet with clearly "
        "curled-up edges and torn corners, rolled slightly at the sides so it reads as a 3D "
        "object with depth and folds not a flat plane, hand-drawn ink illustrations of an island "
        "coastline, a compass rose, a dotted path and a big red X mark, photographed from a "
        "3/4 overhead angle with strong directional lighting casting visible shadows inside "
        "the curls of the parchment, resting on a dark wooden surface."
    ),
    "מצנח_בסיס_מ11": (
        "A BASE-jumping parachute backpack container: small compact rectangular nylon pack "
        "about 45cm tall, matte black main body with yellow and red accent straps, two "
        "shoulder straps with buckles, a visible chest strap and waist strap, a prominent "
        "pilot-chute handle loop protruding from the bottom-right corner, the packed parachute "
        "container shape with folded flaps clearly visible, photographed from the front at "
        "3/4 angle standing upright on its own, NO person wearing it."
    ),
    "סנפלינג_מ11": (
        "A rappelling kit laid out as two separate items side by side: on the LEFT a neat "
        "coiled loop of red and white static climbing rope about 30cm diameter, and on the "
        "RIGHT a black and red climbing harness with waist belt, two leg loops, and a "
        "silver belay carabiner clipped to the front belay loop, both items clearly distinct "
        "and both fully visible, photographed top-down."
    ),
    "סרגל_מ13": (
        "A 30cm clear transparent plastic ruler lying horizontally with black number markings, "
        "AND a small pink rectangular rubber eraser sitting on top of the ruler near the "
        "center, the eraser clearly visible as a separate object resting ON the ruler, "
        "photographed from a 3/4 overhead angle, two distinct office supply items."
    ),
    "פריסקופ_מ07": (
        "A handheld naval submarine periscope in a clear L-shape: one long vertical olive-green "
        "metal cylindrical tube about 50cm tall, with a 90-degree bend at the top ending in a "
        "small horizontal eyepiece tube pointing to the right, AND another 90-degree bend at "
        "the bottom ending in a horizontal eyepiece tube pointing to the left, brass rivets and "
        "fittings, the whole L-shape clearly readable in profile view photographed from the "
        "side."
    ),
    "רשת_מ05": (
        "A rectangular knotted safety cargo net made of thick white nylon rope, a 6x6 grid "
        "mesh pattern with large square holes and visible tight knots at each rope "
        "intersection, the net spread out completely flat and fully open so the grid is "
        "obvious and unambiguous, photographed from directly overhead."
    ),
}


def generate_one(slug, prompt):
    full_prompt = prompt + STUDIO
    body = {
        "instances": [{"prompt": full_prompt}],
        "parameters": {
            "sampleCount": 1,
            "aspectRatio": "1:1",
            "personGeneration": "dont_allow",
        },
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
        err = e.read().decode("utf-8", errors="replace")
        return {"status": "error_http", "code": e.code, "error": err[:500]}
    except Exception as e:
        return {"status": "error_request", "error": str(e)[:500]}

    preds = data.get("predictions") or []
    if not preds:
        return {"status": "error_no_preds", "resp": str(data)[:500]}
    b64 = preds[0].get("bytesBase64Encoded")
    if not b64:
        return {"status": "error_no_bytes", "resp": str(preds[0])[:500]}

    raw_path = OUT_DIR / f"{slug}_raw.png"
    raw_path.write_bytes(base64.b64decode(b64))

    rembg_path = OUT_DIR / f"{slug}_rembg.png"
    transparent = remove(Image.open(raw_path))
    transparent.save(rembg_path)

    final_path = OUT_DIR / f"{slug}_final.png"
    rgba = Image.open(rembg_path).convert("RGBA")
    bg = Image.new("RGB", rgba.size, CHROMA)
    bg.paste(rgba, mask=rgba.split()[3])
    bg.save(final_path)

    return {
        "status": "ok",
        "raw": str(raw_path),
        "rembg": str(rembg_path),
        "final": str(final_path),
    }


def main():
    state = {"attempt": int(time.time()), "tools": {}}
    if STATE_FILE.exists():
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    state.setdefault("tools", {})

    slugs = list(PROMPTS.keys())
    print(f"Gemini Imagen 3 retry for {len(slugs)} tools", flush=True)
    for i, slug in enumerate(slugs, 1):
        print(f"\n[{i}/{len(slugs)}] {slug}", flush=True)
        prior = state["tools"].get(slug) or {}
        if prior.get("status") == "ok" and (OUT_DIR / f"{slug}_final.png").exists():
            print("  SKIP: already generated", flush=True)
            continue
        result = generate_one(slug, PROMPTS[slug])
        state["tools"][slug] = result
        STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  -> {result['status']}", flush=True)

    print("\n=== DONE ===", flush=True)


if __name__ == "__main__":
    main()
