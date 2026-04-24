"""Shutterstock RESULT CHECKER — physical visual inspection of thumbnails.

Given the master's command AND the searcher's top-10 results, this agent
downloads each thumbnail as real bytes, passes it to Claude Vision along with
the master's `intent_for_checker` + `hard_rejects`, and collects a per-thumb
verdict. It then picks the first `match` or returns PASS=false with a
concrete feedback string the master can act on in the next round.

No shortcuts. No metadata-only decisions. No "looks plausible by description."
Every candidate gets loaded and seen.
"""
from __future__ import annotations

import base64
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT = Path(__file__).resolve().parent.parent
KEYS = PROJECT / "keys"


def _load_key(env_var: str, file_path: Path) -> str:
    v = os.environ.get(env_var)
    if v:
        return v.strip()
    if file_path.exists():
        return file_path.read_text("utf-8").strip()
    raise RuntimeError(f"missing {env_var} env var or file {file_path}")


CLAUDE_KEY = _load_key("CLAUDE_API_KEY", KEYS / "claude" / "key.txt")
CLAUDE_MODEL = "claude-sonnet-4-5-20250929"


CHECKER_SYSTEM = """You are the SHUTTERSTOCK RESULT CHECKER. You look at real thumbnails, one at a time, and decide whether each one matches the master's intent for a specific production item in a children's Hebrew financial-literacy game.

You were trained by the master (the one who invented Shutterstock). You know exactly what "flat vector, isolated transparent background, no humans" should look like. You know what a sloppy hit looks like: a vaguely-related photo, a vector that includes a cartoon hand gripping the tool, a composition with decorative palm-leaf framing, a watermark in the corner of a preview.

For EACH thumbnail you receive, you return exactly one verdict:

  match   — this image satisfies the intent AND does not trigger any hard_reject.
  partial — subject is correct but something small is off (minor background clutter,
            off-style). Note it but don't use it.
  miss    — fails the intent or triggers a hard_reject.

You do NOT speculate about what might happen after download. You judge what
you see in this thumbnail.

After reviewing all thumbnails, you output a single JSON object with the
verdict per candidate AND a final verdict:

  verdict = PASS with chosen_id = <id of the FIRST match> — OR —
  verdict = RETRY with a concrete, surgical feedback_to_master string.

Feedback must be specific. Examples:

  BAD:  "results weren't good"
  GOOD: "8 of 10 thumbnails contained a cartoon hand gripping the tool — the
         `-hand -holding` negatives didn't catch them because contributors
         tagged them as 'grip' and 'hold'. Add -grip -hold -grasping to
         negatives."

  GOOD: "All 10 thumbnails are photos despite image_type=vector — this means
         Shutterstock substituted related photos because the vector catalog
         for 'airplane emergency door' is empty. Recommend switching to
         image_type=illustration + 'flat illustration' style token."

  GOOD: "Thumbnails 1–3 show only the light bulbs but have palm-leaf framing
         as decoration. Thumbnails 4–10 are correct lights without framing
         BUT all are photos, not vectors. Pick thumbnail 4 (id 12345) —
         switching to photo is acceptable here since the subject is light
         alone and the background will be black, so luma-key works. But note
         this is a deviation."

Output is STRICT JSON, no preamble, no fences:

{
  "item_slug": "...",
  "round": <1|2|3>,
  "candidates_inspected": <int>,
  "candidates_verdicts": [
    {"id": "...", "verdict": "match|partial|miss", "reason": "..."},
    ...
  ],
  "verdict": "PASS|RETRY",
  "chosen_id": "..." | null,
  "chosen_reason": "..." | null,
  "feedback_to_master": "..." | null
}
"""


def _fetch_bytes(url: str, timeout: int = 30) -> bytes | None:
    try:
        req = urllib.request.Request(url, headers={"Accept": "image/*"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except Exception:
        return None


def _guess_media_type(data: bytes) -> str:
    if data.startswith(b"\x89PNG"):
        return "image/png"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data.startswith(b"GIF8"):
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"


def call_claude_vision(system: str, user_text: str,
                       images: list[tuple[str, bytes]],
                       max_tokens: int = 2000,
                       temperature: float = 0.1) -> str:
    """Call Claude with multiple inline images + text.

    images is a list of (label, raw_bytes). Each image is base64-encoded and
    sent inline as a content block. A text block labels each image so Claude
    knows which candidate it is.
    """
    content: list[dict] = [{"type": "text", "text": user_text}]
    for label, data in images:
        content.append({"type": "text", "text": f"\n[{label}]"})
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": _guess_media_type(data),
                "data": base64.b64encode(data).decode("ascii"),
            },
        })
    body = json.dumps({
        "model": CLAUDE_MODEL,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "system": system,
        "messages": [{"role": "user", "content": content}],
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body, method="POST",
        headers={"x-api-key": CLAUDE_KEY,
                 "anthropic-version": "2023-06-01",
                 "content-type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=180) as r:
        data = json.loads(r.read().decode("utf-8"))
    return "".join(b.get("text", "") for b in data.get("content", []))


def extract_json(text: str) -> Any:
    t = text.strip()
    if t.startswith("```"):
        lines = t.split("\n")[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        t = "\n".join(lines).strip()
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        s, e = t.find("{"), t.rfind("}")
        if s >= 0 and e > s:
            return json.loads(t[s:e+1])
        raise


def check_results(master_cmd: dict, search_envelope: dict) -> dict:
    """Physically inspect thumbnails and return a verdict envelope."""
    item = master_cmd.get("_item", {})
    slug = master_cmd.get("item_slug") or item.get("slug")
    round_num = master_cmd.get("_round", 1)

    results = search_envelope.get("results", [])
    if not results:
        return {
            "item_slug": slug, "round": round_num,
            "candidates_inspected": 0,
            "candidates_verdicts": [],
            "verdict": "RETRY",
            "chosen_id": None,
            "chosen_reason": None,
            "feedback_to_master": (
                f"Searcher returned zero usable thumbnails "
                f"(status={search_envelope.get('status')}). "
                f"Recommend broadening query or swapping image_type."
            ),
            "status": "OK_no_results",
        }

    # Fetch thumbs physically.
    fetched: list[tuple[str, bytes, dict]] = []
    fetch_failures = 0
    for r in results[:10]:
        if not r.get("thumb_url"):
            fetch_failures += 1
            continue
        data = _fetch_bytes(r["thumb_url"])
        if not data:
            fetch_failures += 1
            continue
        label = f"candidate_id={r['id']}"
        fetched.append((label, data, r))

    if not fetched:
        return {
            "item_slug": slug, "round": round_num,
            "candidates_inspected": 0,
            "candidates_verdicts": [],
            "verdict": "RETRY",
            "chosen_id": None, "chosen_reason": None,
            "feedback_to_master": "All 10 thumbnails failed to download; Shutterstock CDN may be throttling. Re-issue the same command.",
            "status": "FAIL_no_thumbnails",
        }

    # Build the user message for Vision.
    intent = master_cmd.get("intent_for_checker", "")
    hard_rejects = master_cmd.get("hard_rejects", [])
    user_text = (
        f"ITEM: {slug}  (round {round_num})\n"
        f"CATEGORY: {item.get('category','')}\n"
        f"HEBREW LABEL: {item.get('he_label','')}\n\n"
        f"MASTER'S INTENT:\n{intent}\n\n"
        f"HARD REJECTS (any candidate that triggers one of these MUST be 'miss'):\n"
        + "\n".join(f"  - {hr}" for hr in hard_rejects) + "\n\n"
        f"MASTER'S QUERY: {master_cmd.get('primary_query',{}).get('query','')}\n"
        f"LICENSE FORMAT TARGETED: {master_cmd.get('license',{}).get('format','')}\n\n"
        f"You will now be shown {len(fetched)} thumbnails, each labeled "
        f"[candidate_id=...]. For each one, physically look at it and return "
        f"a verdict in the JSON schema you were given. Pick the FIRST match, "
        f"if any. If none match, return RETRY with surgical feedback."
    )
    images = [(label, data) for (label, data, _r) in fetched]

    raw = call_claude_vision(CHECKER_SYSTEM, user_text, images,
                              max_tokens=3000, temperature=0.1)
    try:
        verdict_envelope = extract_json(raw)
    except Exception as e:
        return {
            "item_slug": slug, "round": round_num,
            "candidates_inspected": len(fetched),
            "candidates_verdicts": [],
            "verdict": "RETRY",
            "chosen_id": None, "chosen_reason": None,
            "feedback_to_master": f"Vision returned unparseable JSON: {e}. Raw head: {raw[:200]}",
            "status": "FAIL_vision_parse",
        }

    # Enrich with the raw candidate info for the ledger.
    verdict_envelope.setdefault("item_slug", slug)
    verdict_envelope.setdefault("round", round_num)
    verdict_envelope["candidates_inspected"] = len(fetched)
    verdict_envelope["status"] = "OK"
    if fetch_failures:
        verdict_envelope["_note"] = (
            f"{fetch_failures} thumbnails could not be fetched; "
            f"inspected {len(fetched)} of {len(results)}."
        )
    return verdict_envelope


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        print("usage: shutterstock_result_checker.py <master_cmd_json> <search_envelope_json>")
        return 1
    master_cmd = json.loads(Path(argv[1]).read_text("utf-8"))
    search_env = json.loads(Path(argv[2]).read_text("utf-8"))
    verdict = check_results(master_cmd, search_env)
    print(json.dumps(verdict, ensure_ascii=False, indent=2))
    return 0 if verdict.get("verdict") == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
