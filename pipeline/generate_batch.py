"""
Batch tool generator — Phase 0E pipeline.
For each prompt JSON with approved:true:
  1. POST Leonardo → poll → download RAW to pipeline/review/tools_qa/<asset>_raw.png
  2. rembg → transparent PNG
  3. composite on #00B140 → pipeline/review/tools_qa/<asset>_final.png

Usage:  python pipeline/generate_batch.py <prompt_json1> <prompt_json2> ...
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
OUT_DIR = PROJECT / "pipeline" / "review" / "tools_qa"
OUT_DIR.mkdir(parents=True, exist_ok=True)

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
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers=HEADERS, method="POST")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))

def get_json(url):
    req = urllib.request.Request(url, headers=HEADERS, method="GET")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))

def generate_one(prompt_path: Path):
    data = json.loads(prompt_path.read_text(encoding="utf-8"))
    asset = data["asset"]
    print(f"\n=== {asset} ===", flush=True)
    if not data.get("approved"):
        print("  SKIP — approved != true")
        return {"asset": asset, "status": "skipped_not_approved"}

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
        print(f"  HTTP {e.code}: {err}")
        return {"asset": asset, "status": "error", "error": err}

    gen_id = start_resp.get("sdGenerationJob", {}).get("generationId")
    print(f"  generationId={gen_id}")

    img_url = None
    for i in range(60):
        time.sleep(5)
        try:
            poll = get_json(f"{LEONARDO_BASE}/generations/{gen_id}")
        except Exception as e:
            print(f"  poll err: {e}")
            continue
        gj = poll.get("generations_by_pk") or {}
        status = gj.get("status")
        imgs = gj.get("generated_images") or []
        print(f"  poll #{i+1} status={status} images={len(imgs)}")
        if status == "COMPLETE" and imgs:
            img_url = imgs[0]["url"]
            break
        if status == "FAILED":
            return {"asset": asset, "status": "error", "error": "generation FAILED"}

    if not img_url:
        return {"asset": asset, "status": "error", "error": "timeout"}

    # Download raw
    raw_path = OUT_DIR / f"{asset}_raw.png"
    try:
        dl_req = urllib.request.Request(img_url, headers=DL_HEADERS)
        img_bytes = urllib.request.urlopen(dl_req, timeout=120).read()
    except urllib.error.HTTPError as e:
        return {"asset": asset, "status": "download_failed", "http_code": e.code, "img_url": img_url}
    raw_path.write_bytes(img_bytes)
    print(f"  RAW saved: {raw_path.name}")

    # rembg
    rembg_path = OUT_DIR / f"{asset}_rembg.png"
    transparent = remove(Image.open(raw_path))
    transparent.save(rembg_path)
    print(f"  REMBG saved: {rembg_path.name}")

    # composite
    final_path = OUT_DIR / f"{asset}_final.png"
    rgba = Image.open(rembg_path).convert("RGBA")
    bg = Image.new("RGB", rgba.size, CHROMA)
    bg.paste(rgba, mask=rgba.split()[3])
    bg.save(final_path)
    print(f"  FINAL saved: {final_path.name}")

    return {
        "asset": asset,
        "status": "ok",
        "generationId": gen_id,
        "raw": str(raw_path),
        "rembg": str(rembg_path),
        "final": str(final_path),
    }


def main(paths):
    results = []
    for p in paths:
        pp = Path(p)
        if not pp.is_absolute():
            pp = PROJECT / p
        results.append(generate_one(pp))

    print("\n=== SUMMARY ===")
    print(json.dumps(results, ensure_ascii=False, indent=2))
    (PROJECT / "pipeline" / "batch_results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: generate_batch.py <prompt1.json> [prompt2.json ...]")
        sys.exit(1)
    main(sys.argv[1:])
