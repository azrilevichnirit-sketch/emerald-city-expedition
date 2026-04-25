"""V2 — per-prop subject-aware re-background.

The v1 pass was too permissive: Nano Banana kept decorative framing
(palm silhouettes, foliage borders) as "part of the prop". This v2 pass
re-reads from the ORIGINAL backup and tells Nano Banana the EXACT subject
to keep (from the Hebrew label in _props_structured.json), and demands
everything else be removed.

Re-runs from: assets/scenery/_orig_backup/*.png
Overwrites:   assets/scenery/*.png
Log:          pipeline/review/scenery/_rebackground_v2_log.json
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
PROPS_JSON = PROJECT / "pipeline" / "debates" / "scenery" / "_props_structured.json"
LOG = PROJECT / "pipeline" / "review" / "scenery" / "_rebackground_v2_log.json"
KEY_FILE = PROJECT / "keys" / "gimini_key - Copy" / "key.txt"

API_KEY = KEY_FILE.read_text(encoding="utf-8").strip()
NANO = "gemini-2.5-flash-image"


def build_instruction(slug: str, he_label: str, en_prompt: str) -> str:
    # First sentence of en_prompt — the core subject description
    first_sentence = en_prompt.split(".")[0].strip() if en_prompt else slug
    return (
        f"The SUBJECT of this image is: '{slug}' ({he_label}). "
        f"Specifically: {first_sentence}.\n\n"
        f"KEEP ONLY the subject, exactly as shown — same shape, same colors, "
        f"same textures, same lighting, same angle, same size, same position. "
        f"Do NOT redraw or modify the subject itself.\n\n"
        f"REMOVE everything that is not the subject. This includes (but is not "
        f"limited to): palm fronds framing the image, banana leaves, decorative "
        f"silhouettes, surrounding trees that are not the subject, ground/floor "
        f"under the subject, walls, sky gradient, haze/fog, cast shadows on the "
        f"ground, environmental lighting spill, atmospheric blur.\n\n"
        f"REPLACE everything you removed with a SOLID FLAT PURE GREEN color, "
        f"hex #00B140 (rgb 0, 177, 64). The entire area outside the subject must "
        f"be uniform flat #00B140 green — NO gradient, NO vignette, NO fog, "
        f"NO light spill, NO cast shadow on ground.\n\n"
        f"Edge case: if the subject ITSELF includes foliage/trees (e.g. slug is "
        f"'dense_jungle' or 'jungle_trees'), keep all of those — they ARE the "
        f"subject. But any framing elements outside the main subject area must "
        f"still be replaced with flat green.\n\n"
        f"Result: the subject floating on a flat green studio screen, ready for "
        f"chroma-key compositing."
    )


def nano_edit(image_bytes: bytes, instruction: str) -> bytes:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{NANO}:generateContent?key={API_KEY}"
    body = {
        "contents": [{
            "parts": [
                {"inline_data": {"mime_type": "image/png",
                                 "data": base64.b64encode(image_bytes).decode()}},
                {"text": instruction},
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
    raise RuntimeError(f"no image in response: {json.dumps(data)[:400]}")


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
    props = json.loads(PROPS_JSON.read_text("utf-8"))
    log = load_log()
    total = len(props)
    done = sum(1 for p in props if log.get(p["slug"], {}).get("status") == "done")
    print(f"V2 re-background: {total} props, {done} already done, {total-done} remaining")
    print("-" * 60)

    for i, prop in enumerate(props, 1):
        slug = prop["slug"]
        if log.get(slug, {}).get("status") == "done":
            print(f"[{i:02}/{total}] {slug}: skip (done)")
            continue

        backup = BACKUP / f"{slug}.png"
        target = SCENERY / f"{slug}.png"
        if not backup.exists():
            print(f"[{i:02}/{total}] {slug}: SKIP — no backup at {backup}")
            log[slug] = {"status": "skip_nobackup"}
            save_log(log)
            continue

        instr = build_instruction(slug, prop.get("he", ""), prop.get("en_prompt", ""))
        print(f"[{i:02}/{total}] {slug} ({prop.get('he','')}): editing ...", flush=True)
        t0 = time.time()
        attempts = 0
        last_err = None
        while attempts < 3:
            attempts += 1
            try:
                new_bytes = nano_edit(backup.read_bytes(), instr)
                target.write_bytes(new_bytes)
                elapsed = round(time.time() - t0, 1)
                log[slug] = {"status": "done", "attempts": attempts,
                             "elapsed_s": elapsed,
                             "instruction_first_60": instr[:60]}
                save_log(log)
                print(f"    -> done ({elapsed}s, attempt {attempts})")
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
            print(f"    -> FAIL: {last_err}")

    print("\n" + "=" * 60)
    print("V2 RE-BACKGROUND COMPLETE")
    ok = sum(1 for v in log.values() if v.get("status") == "done")
    fl = sum(1 for v in log.values() if v.get("status") == "fail")
    sk = sum(1 for v in log.values() if v.get("status","").startswith("skip"))
    print(f"  done: {ok}   failed: {fl}   skipped: {sk}")


if __name__ == "__main__":
    main()
