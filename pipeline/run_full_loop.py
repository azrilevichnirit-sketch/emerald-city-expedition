"""
Phase 0E — Full loop runner for all tools.
For each prompt JSON in pipeline/prompts/ (approved:true):
  - Skip if <asset>.png already exists in assets/tools/ (= already approved)
  - Otherwise: Leonardo POST → poll → download RAW → rembg → composite on #00B140
  - Saves to pipeline/review/tools_qa/<asset>_{raw,rembg,final}.png
  - Updates pipeline/loop_state.json after each tool
"""
import json
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
from rembg import remove
from PIL import Image

PROJECT = Path(r"C:/Users/azril/OneDrive/Desktop/fincail_game/new")
KEY_FILE = PROJECT / "leonardo_key" / "leonardo.txt"
PROMPTS_DIR = PROJECT / "pipeline" / "prompts"
OUT_DIR = PROJECT / "pipeline" / "review" / "tools_qa"
OUT_DIR.mkdir(parents=True, exist_ok=True)
ASSETS_DIR = PROJECT / "assets" / "tools"
STATE_FILE = PROJECT / "pipeline" / "loop_state.json"

LEONARDO_BASE = "https://cloud.leonardo.ai/api/rest/v1"
CHROMA = (0, 0xB1, 0x40)

api_key = KEY_FILE.read_text(encoding="utf-8").strip()
HEADERS = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}
DL_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def post_json(url, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                  headers=HEADERS, method="POST")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_json(url):
    req = urllib.request.Request(url, headers=HEADERS, method="GET")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def load_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {"tools": {}, "started_at": time.strftime("%Y-%m-%d %H:%M:%S")}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def generate_one(data):
    asset = data["asset"]
    if not data.get("approved"):
        return {"status": "skipped_not_approved"}

    p = data["prompts"]["leonardo"]
    neg = data["prompts"].get("leonardo_negative", "")
    params = data["leonardo_params"]
    body = {
        "prompt": p,
        "negative_prompt": neg,
        "modelId": params["modelId"],
        "width": params.get("width", 1024),
        "height": params.get("height", 1024),
        "num_images": params.get("num_images", 1),
        "alchemy": params.get("alchemy", True),
    }
    if params.get("photoReal"):
        body["photoReal"] = True

    try:
        start_resp = post_json(f"{LEONARDO_BASE}/generations", body)
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")
        return {"status": "error_post", "error": err[:500]}
    except Exception as e:
        return {"status": "error_post", "error": str(e)[:500]}

    gen_id = start_resp.get("sdGenerationJob", {}).get("generationId")
    if not gen_id:
        return {"status": "error_no_genid", "resp": str(start_resp)[:500]}

    img_url = None
    for i in range(72):
        time.sleep(5)
        try:
            poll = get_json(f"{LEONARDO_BASE}/generations/{gen_id}")
        except Exception:
            continue
        gj = poll.get("generations_by_pk") or {}
        status = gj.get("status")
        imgs = gj.get("generated_images") or []
        if status == "COMPLETE" and imgs:
            img_url = imgs[0]["url"]
            break
        if status == "FAILED":
            return {"status": "error_generation_failed", "gen_id": gen_id}

    if not img_url:
        return {"status": "error_timeout", "gen_id": gen_id}

    raw_path = OUT_DIR / f"{asset}_raw.png"
    try:
        dl_req = urllib.request.Request(img_url, headers=DL_HEADERS)
        img_bytes = urllib.request.urlopen(dl_req, timeout=120).read()
    except Exception as e:
        return {"status": "error_download", "error": str(e)[:300], "img_url": img_url}
    raw_path.write_bytes(img_bytes)

    rembg_path = OUT_DIR / f"{asset}_rembg.png"
    try:
        transparent = remove(Image.open(raw_path))
        transparent.save(rembg_path)
    except Exception as e:
        return {"status": "error_rembg", "error": str(e)[:300]}

    final_path = OUT_DIR / f"{asset}_final.png"
    try:
        rgba = Image.open(rembg_path).convert("RGBA")
        bg = Image.new("RGB", rgba.size, CHROMA)
        bg.paste(rgba, mask=rgba.split()[3])
        bg.save(final_path)
    except Exception as e:
        return {"status": "error_composite", "error": str(e)[:300]}

    return {
        "status": "ok",
        "gen_id": gen_id,
        "raw": str(raw_path),
        "rembg": str(rembg_path),
        "final": str(final_path),
    }


def should_skip(slug, state):
    # Skip if already in assets/tools (= human_review PASS already)
    if (ASSETS_DIR / f"{slug}.png").exists():
        return "already_approved"
    # Skip if already OK in state
    prior = state["tools"].get(slug)
    if prior and prior.get("status") == "ok" and (OUT_DIR / f"{slug}_final.png").exists():
        return "already_generated"
    return None


def main():
    state = load_state()
    prompt_files = sorted(PROMPTS_DIR.glob("*.json"))
    print(f"Found {len(prompt_files)} prompt JSONs", flush=True)

    for i, pf in enumerate(prompt_files, 1):
        data = json.loads(pf.read_text(encoding="utf-8"))
        slug = data["asset"]
        print(f"\n[{i}/{len(prompt_files)}] {slug}", flush=True)

        skip_reason = should_skip(slug, state)
        if skip_reason:
            print(f"  SKIP: {skip_reason}", flush=True)
            state["tools"][slug] = state["tools"].get(slug) or {"status": skip_reason}
            save_state(state)
            continue

        result = generate_one(data)
        state["tools"][slug] = result
        save_state(state)
        print(f"  -> {result['status']}", flush=True)

    state["finished_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    save_state(state)
    print("\n=== DONE ===")


if __name__ == "__main__":
    main()
