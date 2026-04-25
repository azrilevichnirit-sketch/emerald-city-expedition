"""Swap the baked scene background on every scenery prop with solid green #00B140.

Uses Nano Banana (gemini-2.5-flash-image) as image-to-image editor.
Preserves the prop's shape, colors, lighting — only replaces surrounding scene.

Output: assets/scenery/<slug>.png (overwrites), original backed up to
        assets/scenery/_orig_backup/<slug>.png on first run.

Idempotent resume via pipeline/review/scenery/_rebackground_log.json.
"""
import base64
import json
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT = Path(__file__).resolve().parent.parent
SCENERY = PROJECT / "assets" / "scenery"
BACKUP = SCENERY / "_orig_backup"
BACKUP.mkdir(exist_ok=True)
LOG = PROJECT / "pipeline" / "review" / "scenery" / "_rebackground_log.json"
LOG.parent.mkdir(parents=True, exist_ok=True)

KEY_FILE = PROJECT / "keys" / "gimini_key - Copy" / "key.txt"
API_KEY = KEY_FILE.read_text(encoding="utf-8").strip()
NANO = "gemini-2.5-flash-image"

INSTRUCTION = (
    "Keep the main subject (the prop) EXACTLY as it is: same shape, same colors, "
    "same textures, same lighting, same angle, same size, same position. "
    "Do NOT redraw the prop. Do NOT change its details.\n\n"
    "CHANGE ONLY the background: replace ALL environment around the prop "
    "(ground, floor, grass, rocks, walls, sky, fog, haze, trees, scene, baked shadows) "
    "with a SOLID FLAT PURE GREEN SCREEN, hex color #00B140 "
    "(rgb 0, 177, 64). The entire area outside the prop must be uniform flat #00B140 green, "
    "absolutely no gradients, no vignette, no environmental light spill, no cast shadow "
    "on ground.\n\n"
    "Result: the prop floating on a flat green studio screen, ready for chroma-key compositing."
)


def nano_edit(image_bytes):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{NANO}:generateContent?key={API_KEY}"
    body = {
        "contents": [{
            "parts": [
                {"inline_data": {"mime_type": "image/png", "data": base64.b64encode(image_bytes).decode()}},
                {"text": INSTRUCTION},
            ],
        }],
        "generationConfig": {"responseModalities": ["IMAGE"]},
    }
    req = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    for p in data["candidates"][0]["content"]["parts"]:
        inline = p.get("inline_data") or p.get("inlineData")
        if inline:
            return base64.b64decode(inline["data"])
    raise RuntimeError(f"no image in nano response: {json.dumps(data)[:400]}")


def load_log():
    if LOG.exists():
        try:
            return json.loads(LOG.read_text("utf-8"))
        except Exception:
            return {}
    return {}


def save_log(log):
    LOG.write_text(json.dumps(log, ensure_ascii=False, indent=2), "utf-8")


def main():
    log = load_log()
    pngs = sorted(p for p in SCENERY.glob("*.png") if p.is_file())
    total = len(pngs)
    print(f"Found {total} scenery PNGs to re-background.")
    done = sum(1 for p in pngs if log.get(p.stem, {}).get("status") == "done")
    print(f"Already done in prior run: {done}. Remaining: {total - done}.")
    print("-" * 60)

    for i, png in enumerate(pngs, 1):
        slug = png.stem
        if log.get(slug, {}).get("status") == "done":
            print(f"[{i:02}/{total}] {slug}: skip (done)")
            continue

        # Backup original on first touch
        backup = BACKUP / png.name
        if not backup.exists():
            backup.write_bytes(png.read_bytes())

        print(f"[{i:02}/{total}] {slug}: nano-editing ...", flush=True)
        t0 = time.time()
        attempts = 0
        last_err = None
        while attempts < 3:
            attempts += 1
            try:
                new_bytes = nano_edit(backup.read_bytes())
                png.write_bytes(new_bytes)
                log[slug] = {"status": "done", "attempts": attempts,
                             "elapsed_s": round(time.time() - t0, 1)}
                save_log(log)
                print(f"    -> done ({round(time.time()-t0,1)}s, attempt {attempts})")
                break
            except urllib.error.HTTPError as e:
                last_err = f"HTTP {e.code}: {e.read().decode('utf-8','replace')[:200]}"
                time.sleep(3 * attempts)
            except Exception as e:
                last_err = f"{type(e).__name__}: {e}"
                time.sleep(3 * attempts)
        else:
            log[slug] = {"status": "fail", "attempts": attempts, "error": last_err}
            save_log(log)
            print(f"    -> FAIL after {attempts} attempts: {last_err}")

    print("\n" + "=" * 60)
    print("RE-BACKGROUND COMPLETE")
    ok = sum(1 for v in log.values() if v.get("status") == "done")
    fl = sum(1 for v in log.values() if v.get("status") == "fail")
    print(f"  done: {ok}   failed: {fl}")
    if fl:
        print("  failed items:")
        for k, v in log.items():
            if v.get("status") == "fail":
                print(f"    {k}: {v.get('error','')[:120]}")


if __name__ == "__main__":
    main()
