"""Retro-audit fix pass — 13 tools regenerated per director's notes.

Each entry carries:
  fix_note  — what the director said to correct
  prompt    — new cinematic prompt reflecting the fix
  bg        — "white" | "gray" (gray used for white-on-white subjects like the flag)

Outputs land in pipeline/review/tools_qa_gemini/{slug}_rA_final.png for review.
Final approved PNGs are later copied to the clean final folder.
"""
import base64
import json
import urllib.request
from pathlib import Path
from PIL import Image
import numpy as np
import io

PROJECT = Path(r"C:/Users/azril/OneDrive/Desktop/fincail_game/new")
KEY_FILE = PROJECT / "keys" / "gimini_key - Copy" / "key.txt"
OUT_DIR = PROJECT / "pipeline" / "review" / "tools_qa_gemini"
STATE = PROJECT / "pipeline" / "retro_fixes_state.json"
API_KEY = KEY_FILE.read_text(encoding="utf-8").strip()
IMAGEN = "imagen-4.0-generate-001"
CHROMA = np.array([0, 0xB1, 0x40], dtype=float)

STUDIO_WHITE = (
    " Floating isolated centered on a pure white studio background. "
    "No text, no numbers, no letters, no labels, no watermark. "
    "Painterly semi-realistic AAA adventure-game inventory asset art."
)
STUDIO_GRAY = (
    " Floating isolated centered on a plain flat neutral mid-gray studio "
    "background (not white). No text, no numbers, no letters, no labels, "
    "no watermark. Painterly semi-realistic AAA adventure-game inventory "
    "asset art."
)

FIXES = {
    # ---- RED ----
    "דגל_סיום_מ15": {
        "bg": "gray",
        "fix_note": "remove '15' number; pure white flag (plain)",
        "prompt": (
            "A single heroic cinematic adventure-game inventory icon of a "
            "plain PURE WHITE fabric finish-line flag — rectangular white "
            "cloth with a subtle wave, attached to a dark wooden pole with "
            "a polished brass base stand. Absolutely no numbers, no text, "
            "no letters, no logos, no emblems — the flag face is completely "
            "blank plain white fabric. Warm golden-hour side-light rakes "
            "across the cloth giving it soft shadows and folds."
            + STUDIO_GRAY
        ),
    },
    "סולם_חבלים_מ08": {
        "bg": "white",
        "fix_note": "classic vertical rope ladder with wooden rungs, not a 2D mesh",
        "prompt": (
            "A single heroic cinematic adventure-game inventory icon of a "
            "CLASSIC VERTICAL ROPE LADDER — two parallel thick braided jute "
            "ropes hanging vertically from top to bottom, connected by "
            "approximately six horizontal wooden rungs spaced evenly apart. "
            "The wooden rungs are smooth rounded logs of dark wood. The "
            "ropes are weathered natural tan fiber with visible braid "
            "texture. The ladder is hanging straight down and swaying "
            "slightly as if suspended from above, with a gentle diagonal "
            "tilt. Warm golden-hour sunlight from the upper-left gives the "
            "wood and rope warm highlights and shadows."
            + STUDIO_WHITE
        ),
    },
    "זיקוק_מ15": {
        "bg": "white",
        "fix_note": "festive celebratory firework bursting, not a military rocket",
        "prompt": (
            "A single heroic cinematic adventure-game inventory icon of a "
            "COLORFUL FESTIVE FIREWORK in mid-burst — a slim paper-wrapped "
            "rocket tube trailing upward from the bottom of the frame, with "
            "a LARGE SPECTACULAR STARBURST EXPLOSION of rainbow sparks at "
            "the top: brilliant red, gold, green, blue and magenta spark "
            "trails radiating outward like a flower, with glowing bright "
            "star particles and trailing curls of light. The overall feel "
            "is celebration, carnival, Chinese New Year, NOT military, NOT "
            "a missile. The sparks and bright spectacle dominate the icon. "
            "Warm bokeh glow all around the burst."
            + STUDIO_WHITE
        ),
    },
    # ---- ORANGE ----
    "מצנח_מ01": {
        "bg": "white",
        "fix_note": "side/below angle (not top-down); classic round canopy deployed",
        "prompt": (
            "A single heroic cinematic adventure-game inventory icon of a "
            "CLASSIC ROUND WIDE PARACHUTE canopy seen from a 3/4 side-below "
            "angle — the round dome of the canopy is fully inflated and "
            "visible from underneath, showing the mushroom-dome shape with "
            "alternating orange and white radial fabric gores. Many thin "
            "black suspension lines fan down from the bottom rim of the "
            "canopy and converge into a small empty cloth harness seat "
            "hanging below the center. No pilot, no rider, no ground, no "
            "sky. Warm golden-hour sunlight on the top of the canopy, cool "
            "blue rim-light on the underside."
            + STUDIO_WHITE
        ),
    },
    "פטיש_מ02": {
        "bg": "white",
        "fix_note": "several shiny nails prominently visible, not tiny",
        "prompt": (
            "A single heroic cinematic adventure-game inventory icon of a "
            "CLAW HAMMER with a wooden handle and polished steel head, "
            "lying diagonally across the frame, surrounded by SIX LARGE "
            "SHINY STEEL NAILS scattered prominently around it — each nail "
            "clearly visible with round flat heads and pointed tips, the "
            "nails are substantial, roughly 1/3 the length of the hammer "
            "handle, arrayed dramatically. Warm golden-hour sunlight gives "
            "the metal highlights and the wood warm tones."
            + STUDIO_WHITE
        ),
    },
    "מפתח_מ03": {
        "bg": "white",
        "fix_note": "ATV/quad-bike key, rugged rubber grip, not modern sedan fob",
        "prompt": (
            "A single heroic cinematic adventure-game inventory icon of an "
            "OFF-ROAD ATV QUAD-BIKE IGNITION KEY — a rugged rubberized key "
            "with a thick black-and-orange plastic grip shaped like an "
            "off-road tool, a simple bare silver metal blade with notched "
            "teeth, a small key-ring with a dirt-stained leather tag. "
            "Distinctly an off-road vehicle key, NOT a modern sleek car "
            "remote fob. Warm golden-hour sunlight reflections on the metal."
            + STUDIO_WHITE
        ),
    },
    "רובה_חבלים_מ04": {
        "bg": "white",
        "fix_note": "grappling gun — visible hook projectile at muzzle, not industrial stapler",
        "prompt": (
            "A single heroic cinematic adventure-game inventory icon of an "
            "ADVENTURE-STYLE GRAPPLING HOOK GUN — a handheld launcher "
            "shaped like a cinematic grapnel gun with a prominent LARGE "
            "SILVER-STEEL GRAPPLING HOOK projectile protruding from the "
            "front muzzle (the hook has three sharp curved prongs), a thick "
            "braided cable trailing from the back of the gun and coiling "
            "beside it, polished brass and dark wood body with a pistol "
            "grip and trigger. Steampunk-adventure aesthetic, not a modern "
            "staple gun. Warm golden-hour highlights on the brass."
            + STUDIO_WHITE
        ),
    },
    "רשת_מ05": {
        "bg": "white",
        "fix_note": "dynamic defensive net with weighted edges, not a static small mesh",
        "prompt": (
            "A single heroic cinematic adventure-game inventory icon of a "
            "THROWN DEFENSIVE ROPE NET — a heavy braided dark brown rope "
            "net captured MID-AIR, partially spread open with loose "
            "diamond-shaped mesh cells, with prominent iron ball weights "
            "attached at the corners and edges of the net (about six dark "
            "metal weights visible along the perimeter), suggesting motion "
            "and impending trap. Dramatic diagonal spread. Warm golden "
            "sunlight on the rope and steel highlights on the weights."
            + STUDIO_WHITE
        ),
    },
    "לפיד_מ05": {
        "bg": "white",
        "fix_note": "compact square proportions for inventory, not thin+tall",
        "prompt": (
            "A single heroic cinematic adventure-game inventory icon of a "
            "BURNING TORCH, composed into a SQUARE 1:1 FRAMING — a "
            "substantial bamboo or wrapped-cloth torch held diagonally "
            "across the frame at a 45-degree angle with a LARGE DYNAMIC "
            "orange-yellow flame at the top filling the upper portion of "
            "the frame. The torch handle is thick dark wrapped fabric with "
            "leather bindings and brass rivets. The overall composition "
            "fills the square frame evenly — flame in one corner, handle "
            "in the opposite corner. Cinematic ember sparks drift near the "
            "flame. Warm fire-glow lighting the subject."
            + STUDIO_WHITE
        ),
    },
    "חבל_קשרים_מ08": {
        "bg": "white",
        "fix_note": "square frame — coiled or folded rope, not thin-tall strip",
        "prompt": (
            "A single heroic cinematic adventure-game inventory icon of a "
            "THICK BRAIDED ROPE WITH LARGE KNOTS — the rope is doubled-back "
            "and COILED into a compact bundle filling a square frame, with "
            "FIVE LARGE PROMINENT KNOTS clearly visible along its length "
            "at regular intervals. Natural tan-colored fiber rope with "
            "visible braid texture, slightly weathered. The composition "
            "fills the frame evenly. Warm golden-hour sunlight giving warm "
            "shadows on the rope fiber."
            + STUDIO_WHITE
        ),
    },
    "רב_כלי_מ09": {
        "bg": "white",
        "fix_note": "folded Leatherman-style multi-tool, one compact unit",
        "prompt": (
            "A single heroic cinematic adventure-game inventory icon of a "
            "CLASSIC FOLDING MULTI-TOOL (Leatherman-style) — ONE COMPACT "
            "POCKET-SIZED UNIT with a polished stainless steel body shaped "
            "like a rectangular pliers-handle, with THREE OR FOUR BLADES "
            "AND TOOLS fanned partially open at different angles from the "
            "body (a blade, a screwdriver, a can-opener, a small saw). "
            "Single integrated unit, NOT scattered separate pieces. Warm "
            "golden-hour highlights on brushed steel."
            + STUDIO_WHITE
        ),
    },
    "שמיכה_מ10": {
        "bg": "white",
        "fix_note": "clearer blast blanket / protective shield reading, not pillow-on-case",
        "prompt": (
            "A single heroic cinematic adventure-game inventory icon of a "
            "TACTICAL BLAST-PROTECTION BLANKET — a heavy dark-gray armored "
            "ballistic shield-blanket, thick and quilted with visible "
            "kevlar-weave diagonal stitching pattern, folded once and "
            "draped with one corner pulled back to show the layered armor "
            "thickness, with prominent yellow-and-black hazard-warning "
            "stripe tape along one edge and a tactical carrying handle. "
            "Clearly reads as PROTECTIVE SHIELD, not a pillow or cushion. "
            "Warm golden-hour top-light."
            + STUDIO_WHITE
        ),
    },
    "בנגי_מ11": {
        "bg": "white",
        "fix_note": "stretched extended bungee cord, visibly elastic, not coiled like rope",
        "prompt": (
            "A single heroic cinematic adventure-game inventory icon of an "
            "EXTREME-SPORT BUNGEE CORD — a thick elastic cord STRETCHED "
            "AND EXTENDED in a diagonal arc across the frame (NOT coiled), "
            "with a spiraling colorful stretchy fabric cover in vivid "
            "rainbow stripes of red-yellow-blue that visibly stretches and "
            "reveals the elastic rubber core between turns of the wrap. A "
            "LARGE POLISHED STEEL CARABINER clip is attached at each end. "
            "The cord sags slightly in the middle from its own elasticity, "
            "clearly reading as STRETCHY and SPRINGY. Warm golden-hour "
            "highlights on the carabiners."
            + STUDIO_WHITE
        ),
    },
}


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
    final = OUT_DIR / f"{slug}_rA_final.png"
    Image.fromarray(comp).save(final)
    return final


def main():
    state = {"tools": {}}
    for slug, cfg in FIXES.items():
        print(f"{slug} — {cfg['fix_note']}", flush=True)
        try:
            raw = imagen(cfg["prompt"])
            (OUT_DIR / f"{slug}_rA_raw.png").write_bytes(raw)
            final = chroma(raw, slug)
            state["tools"][slug] = {"status": "ok", "final": str(final),
                                     "fix_note": cfg["fix_note"],
                                     "bg": cfg["bg"]}
            print(f"  -> {final.name}", flush=True)
        except Exception as e:
            state["tools"][slug] = {"status": "error", "error": str(e)}
            print(f"  ERROR: {e}", flush=True)
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2),
                     encoding="utf-8")
    print("DONE")


if __name__ == "__main__":
    main()
