"""
Image Generator (Leonardo) — Style Test run v2
Reads 3 approved prompt JSONs, posts to Leonardo API, polls until complete,
downloads PNG to pipeline/review/styletest/.

Gate rule per visual_prompt_writer.md / image_generator.md:
  - If "approved" field != true  -> SKIP that prompt.
Stdlib only (urllib.request).
"""
import json
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

PROJECT = Path(r"C:/Users/azril/OneDrive/Desktop/fincail_game/new")
KEY_FILE = PROJECT / "leonardo_key" / "leonardo.txt"
PROMPTS_DIR = PROJECT / "pipeline" / "prompts"
OUT_DIR = PROJECT / "pipeline" / "review" / "styletest"

LEONARDO_BASE = "https://cloud.leonardo.ai/api/rest/v1"
POLL_INTERVAL = 5
POLL_MAX = 60  # ~5 min max

OUT_DIR.mkdir(parents=True, exist_ok=True)

api_key = KEY_FILE.read_text(encoding="utf-8").strip()
if not api_key:
    print("ERROR: empty leonardo api key", file=sys.stderr); sys.exit(1)

HEADERS = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json",
    "Accept": "application/json",
}

prompt_files = [
    PROMPTS_DIR / "מצנח_מ01.json",
    PROMPTS_DIR / "פנס_עוצמתי_מ05.json",
    PROMPTS_DIR / "סולם_חבלים_מ08.json",
]

def post_json(url, body):
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers=HEADERS,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))

def get_json(url):
    req = urllib.request.Request(url, headers=HEADERS, method="GET")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))

results = []

for pf in prompt_files:
    print(f"\n=== {pf.name} ===", flush=True)
    data = json.loads(pf.read_text(encoding="utf-8"))
    asset = data["asset"]

    if not data.get("approved"):
        print("  SKIP — approved != true")
        results.append({"asset": asset, "status": "skipped_not_approved"})
        continue

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
    # photoReal is optional; only include when true (Phoenix accepts it w/ alchemy)
    if params.get("photoReal"):
        body["photoReal"] = True

    print(f"  POST /generations  modelId={body['modelId']}")
    try:
        start_resp = post_json(f"{LEONARDO_BASE}/generations", body)
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        print(f"  HTTP {e.code}: {err_body}")
        results.append({"asset": asset, "status": "error", "error": err_body})
        continue
    except Exception as e:
        print(f"  ERROR: {e}")
        results.append({"asset": asset, "status": "error", "error": str(e)})
        continue

    gen_id = start_resp.get("sdGenerationJob", {}).get("generationId")
    if not gen_id:
        print(f"  ERROR: no generationId in response: {start_resp}")
        results.append({"asset": asset, "status": "error", "error": "no generationId", "raw": start_resp})
        continue

    print(f"  generationId={gen_id}  polling...")

    img_url = None
    final_status = None
    for i in range(POLL_MAX):
        time.sleep(POLL_INTERVAL)
        try:
            poll = get_json(f"{LEONARDO_BASE}/generations/{gen_id}")
        except Exception as e:
            print(f"  poll #{i+1} error: {e}")
            continue
        gj = poll.get("generations_by_pk") or {}
        status = gj.get("status")
        imgs = gj.get("generated_images") or []
        print(f"  poll #{i+1}  status={status}  images={len(imgs)}")
        final_status = status
        if status == "COMPLETE" and imgs:
            img_url = imgs[0].get("url")
            break
        if status == "FAILED":
            break

    if not img_url:
        print(f"  FAILED — final_status={final_status}")
        results.append({"asset": asset, "status": "error", "error": f"generation {final_status}", "generationId": gen_id})
        continue

    print(f"  img_url received, downloading...")
    try:
        dl_req = urllib.request.Request(img_url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "image/*,*/*",
        })
        img_bytes = urllib.request.urlopen(dl_req, timeout=120).read()
    except urllib.error.HTTPError as e:
        print(f"  DOWNLOAD HTTP {e.code} — saving url for manual retry")
        results.append({"asset": asset, "status": "download_failed", "generationId": gen_id, "img_url": img_url, "http_code": e.code})
        continue
    out_path = OUT_DIR / f"{asset}_styletest_v4.png"
    out_path.write_bytes(img_bytes)
    print(f"  SAVED: {out_path}  ({len(img_bytes)} bytes)")

    results.append({
        "asset": asset,
        "status": "saved",
        "path": str(out_path).replace("\\", "/"),
        "generationId": gen_id,
        "size_bytes": len(img_bytes),
    })

print("\n=== SUMMARY ===")
print(json.dumps(results, ensure_ascii=False, indent=2))

(PROJECT / "pipeline" / "styletest_leonardo_results.json").write_text(
    json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
)
