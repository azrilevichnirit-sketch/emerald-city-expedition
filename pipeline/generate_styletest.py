"""
Image Generator — Style Test run
Calls OpenAI DALL-E 3 for the 3 style test tool prompts.
Stdlib only (urllib.request) to avoid pip installs.
"""
import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path

PROJECT = Path(r"C:/Users/azril/OneDrive/Desktop/fincail_game/new")
KEY_FILE = PROJECT / "openai" / "openai_KEY.txt"
PROMPTS_DIR = PROJECT / "pipeline" / "prompts"
OUT_DIR = PROJECT / "assets" / "tools"

OUT_DIR.mkdir(parents=True, exist_ok=True)

api_key = KEY_FILE.read_text(encoding="utf-8").strip()
if not api_key:
    print("ERROR: empty api key", file=sys.stderr); sys.exit(1)

prompt_files = [
    PROMPTS_DIR / "מצנח_מ01.json",
    PROMPTS_DIR / "פנס_עוצמתי_מ05.json",
    PROMPTS_DIR / "סולם_חבלים_מ08.json",
]

results = []

for pf in prompt_files:
    print(f"\n=== {pf.name} ===", flush=True)
    data = json.loads(pf.read_text(encoding="utf-8"))
    if not data.get("approval", {}).get("status"):
        print(f"  SKIP — not approved"); continue

    prompt_text = data["prompts"]["dalle"]
    asset_name = data["asset"]

    body = json.dumps({
        "model": "dall-e-3",
        "prompt": prompt_text,
        "size": "1024x1024",
        "quality": "hd",
        "n": 1
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.openai.com/v1/images/generations",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        print(f"  HTTP {e.code}: {err_body}");
        results.append({"asset": asset_name, "status": "error", "error": err_body})
        continue
    except Exception as e:
        print(f"  ERROR: {e}")
        results.append({"asset": asset_name, "status": "error", "error": str(e)})
        continue

    image_url = payload["data"][0]["url"]
    revised = payload["data"][0].get("revised_prompt", "")
    print(f"  image_url received")
    print(f"  revised_prompt: {revised[:200]}...")

    img_bytes = urllib.request.urlopen(image_url, timeout=120).read()
    out_path = OUT_DIR / f"{asset_name}_styletest_v1.png"
    out_path.write_bytes(img_bytes)
    print(f"  SAVED: {out_path}  ({len(img_bytes)} bytes)")

    results.append({
        "asset": asset_name,
        "status": "saved",
        "path": str(out_path.relative_to(PROJECT)).replace("\\", "/"),
        "revised_prompt": revised,
    })

print("\n=== SUMMARY ===")
print(json.dumps(results, ensure_ascii=False, indent=2))

(PROJECT / "pipeline" / "styletest_results.json").write_text(
    json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
)
