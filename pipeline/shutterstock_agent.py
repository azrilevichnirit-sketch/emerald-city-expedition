"""Shutterstock Agent — Claude-brain stock-photo fetcher for scenery + tools.

Nirit's diagnosis (2026-04-24):
  Shutterstock is NOT prompted like a generative AI. It's a keyword-tagged
  stock library. Direct en_prompt ("tropical expedition path with dappled
  sunlight...") fetches stylized/illustrated junk. The agent's "skill" is
  knowing the stock-photo idiom:
    - scenery: "dirt path rainforest", "jungle trail mud", "forest path mossy"
    - tools:   "claw hammer isolated white", "expedition shovel studio"

Architecture (two Claude stages):
  Stage 1 — QUERY CRAFTER:
    Input:  slug + he_label + en_prompt + category + mission_text
    Output: 3 ranked Shutterstock-idiom queries (each 3-7 keywords)
    Brain:  Claude Sonnet 4.5 with a system prompt that teaches stock idiom.

  Stage 2 — VISUAL SELECTOR:
    Input:  director notes + up to 15 thumbnail URLs
    Output: chosen image_id  OR  "REJECT" + new query to try
    Brain:  Claude Sonnet 4.5 vision (URL-based image input).

  Stage 3 — LICENSE + DOWNLOAD:
    POST /v2/images/licenses → save to pipeline/staging/shutterstock/{cat}/{slug}.jpg

Budget awareness:
  500 downloads/month. Search is free. Agent licenses only after Stage 2
  confirms a pick, so worst-case ~1 license per item (51 scenery + 45 tools
  = ~96 images, well within budget).

Resume:
  pipeline/staging/shutterstock/_log.json tracks state per slug.
  Re-running resumes from where it stopped.

Usage:
  python pipeline/shutterstock_agent.py scenery              # all 51
  python pipeline/shutterstock_agent.py tools                # all 45
  python pipeline/shutterstock_agent.py scenery broken_door  # one slug
  python pipeline/shutterstock_agent.py --dry-run scenery    # no licensing
"""
from __future__ import annotations

import json
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path
from typing import Iterable

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT = Path(__file__).resolve().parent.parent
KEYS = PROJECT / "keys"


def _load_key(env_var: str, file_path: Path) -> str:
    """Read a secret from env var (CI) or fall back to file (local dev)."""
    import os
    v = os.environ.get(env_var)
    if v:
        return v.strip()
    if file_path.exists():
        return file_path.read_text(encoding="utf-8").strip()
    raise RuntimeError(
        f"missing secret: set env {env_var} or create file {file_path}"
    )


CLAUDE_KEY = _load_key("CLAUDE_API_KEY", KEYS / "claude" / "key.txt")
SS_TOKEN = _load_key("SHUTTERSTOCK_TOKEN", KEYS / "shutterstock" / "access_token.txt")

CLAUDE_MODEL = "claude-sonnet-4-5"
SS_API = "https://api.shutterstock.com/v2"
# Subscription id is per-user; discover at startup to survive renewals.
_SUBSCRIPTION_ID_CACHE: str | None = None

PROPS_JSON = PROJECT / "pipeline" / "debates" / "scenery" / "_props_structured.json"
CONTENT_LOCK = PROJECT / "content_lock.json"

STAGING = PROJECT / "pipeline" / "staging" / "shutterstock"
STAGING.mkdir(parents=True, exist_ok=True)
(STAGING / "scenery").mkdir(exist_ok=True)
(STAGING / "tools").mkdir(exist_ok=True)
LOG_PATH = STAGING / "_log.json"

# ─────────────────────────────── HTTP helpers ───────────────────────────────

def _post_json(url: str, body: dict, headers: dict, timeout: int = 90) -> dict:
    hdrs = {"Content-Type": "application/json", **headers}
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=hdrs, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _get_json(url: str, headers: dict, timeout: int = 60) -> dict:
    req = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


# ───────────────────────── Claude brain (2 stages) ──────────────────────────

def call_claude(system: str, user_text: str, image_urls: list[str] | None = None,
                max_tokens: int = 800) -> str:
    """Claude API. Supports URL-based image inputs (Anthropic API since 2024)."""
    content = []
    if image_urls:
        for u in image_urls:
            content.append({"type": "image", "source": {"type": "url", "url": u}})
    content.append({"type": "text", "text": user_text})
    body = {
        "model": CLAUDE_MODEL,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": content}],
    }
    data = _post_json(
        "https://api.anthropic.com/v1/messages", body,
        {"x-api-key": CLAUDE_KEY, "anthropic-version": "2023-06-01"},
    )
    return "".join(b.get("text", "") for b in data.get("content", []))


QUERY_CRAFTER_SYSTEM = """You are a senior stock-photo researcher specialized in Shutterstock's keyword index.

Your job: translate a game-art-director's free-form description into 3 Shutterstock search queries that will actually surface the right photograph.

Shutterstock indexing reality:
- Photographers tag with concrete nouns, materials, and framing terms, not artistic direction.
- "Tropical expedition jungle path at golden hour, dappled sunlight" → 0 real hits.
- "jungle trail dirt path" → thousands. "rainforest path mud" → thousands.
- The stock idiom favors: common-word nouns (dirt, mud, moss, rock, cliff, vine),
  angle/framing (aerial, close-up, top view, low angle, landscape, vertical),
  material/state (weathered, rusty, wet, worn, mossy, overgrown, broken),
  lighting/mood (dramatic, misty, golden hour, stormy, sunlit).
- For ISOLATED TOOLS on green-screen target: ALWAYS append "isolated white background"
  or "studio shot isolated" — this is the standard photographer tag for cut-out usable photos.
- Drop any "photorealistic", "expedition-style", "dramatic lighting" adjectives — Shutterstock
  ignores/misinterprets them.

Category rules:
- scenery/environment: 4-6 keywords, favor the environment-noun + texture/state + framing.
  Examples:
    "dense tropical jungle" → "rainforest canopy aerial view"
    "rope bridge over chasm" → "rope bridge jungle wooden"
    "expedition path through jungle" → "dirt path rainforest jungle"
    "dark cave entrance" → "cave entrance dark rock"
    "distant celebration lights at night" → "festival lights night distant landscape"
- props/tools: always include ONE of: "isolated white background", "studio shot",
  "cut out", "transparent background". The goal is a clean photo we can chroma-key.
  Examples:
    "weathered expedition parachute" → "parachute canopy isolated white background"
    "hang glider for flying" → "hang glider isolated white background studio"
    "rusty jerrycan oil can" → "jerrycan isolated white background studio"

Hebrew hint: the `he_label` often reveals the simple common-word version of what
the item actually is. Trust it over the English prompt's decoration.

Output format — STRICT:
Return ONLY a JSON array of 3 strings, no preamble, no markdown fence.
Example: ["dirt path rainforest","jungle trail mud","forest path mossy vines"]
Each query MUST be 3-7 words, lowercase, no punctuation, no quotes inside."""


VISUAL_SELECTOR_SYSTEM = """You are a visual director picking the best stock photo for a specific game-art slot.

You will see up to 15 candidate thumbnails from Shutterstock searches. Each is listed
with its numeric id and one-line description.

Your job: pick the SINGLE id that best matches the director's intent — or reject all and request a new search.

Selection criteria (in priority order):
1. Subject match: the photo shows what the director asked for, not a close cousin.
2. Usable framing: for scenery — good composition, no watermark over subject, minimal
   human faces (unless the prop IS people). For tools — isolated on white/simple bg,
   single clear subject, usable for cut-out.
3. Mood/lighting match: does it feel like the scene the director described?
4. Technical: no heavy text/logos, not obviously AI-generated (unless that fits).

Rejection triggers (return REJECT):
- All candidates are wrong subject (e.g., director asked for a rope bridge, all
  shots are metal bridges).
- All candidates are illustrations when the game needs photography.
- No candidate has clean isolation when the item is a tool.

Output format — STRICT:
Return ONLY a single JSON object, no markdown fence.
  Pick:    {"choice":"pick","image_id":"1234567890","reason":"why this one"}
  Reject:  {"choice":"reject","new_query":"better keywords here","reason":"why all failed"}"""


def craft_queries(item: dict) -> list[str]:
    """Stage 1: Claude → 3 Shutterstock-idiom queries."""
    payload = {
        "slug": item["slug"],
        "he_label": item.get("he", ""),
        "en_prompt": item.get("en_prompt", ""),
        "category": item["category"],             # "scenery" or "tools"
        "mission_text": item.get("mission_text", ""),
    }
    user = (
        "Director's request:\n"
        f"  slug:         {payload['slug']}\n"
        f"  category:     {payload['category']}\n"
        f"  hebrew label: {payload['he_label']}\n"
        f"  mission ctx:  {payload['mission_text']}\n"
        f"  en_prompt:    {payload['en_prompt']}\n"
        "\nGive me the 3 queries (JSON array only)."
    )
    raw = call_claude(QUERY_CRAFTER_SYSTEM, user, max_tokens=300)
    raw = raw.strip()
    # tolerate ```json fences
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    try:
        arr = json.loads(raw)
        if isinstance(arr, list) and all(isinstance(q, str) for q in arr):
            return [q.strip() for q in arr if q.strip()][:3]
    except Exception:
        pass
    # fallback: one word salad query
    fallback = item.get("he", "") or item.get("slug", "").replace("_", " ")
    return [fallback]


def pick_from_thumbnails(item: dict, candidates: list[dict]) -> dict:
    """Stage 2: Claude vision → {choice, image_id|new_query, reason}.

    candidates = [{"image_id": "..", "description": "..",
                   "preview_url": "https://..."}, ...]
    """
    lines = ["Director's request:"]
    lines.append(f"  slug:      {item['slug']}")
    lines.append(f"  category:  {item['category']}")
    lines.append(f"  hebrew:    {item.get('he','')}")
    lines.append(f"  director:  {item.get('en_prompt','')}")
    lines.append("")
    lines.append("Candidates (shown below in same order):")
    for i, c in enumerate(candidates, 1):
        lines.append(f"  [{i}] id={c['image_id']} — {c['description']}")
    lines.append("")
    lines.append("Pick the best or reject all. JSON only.")
    user = "\n".join(lines)
    urls = [c["preview_url"] for c in candidates]
    raw = call_claude(VISUAL_SELECTOR_SYSTEM, user, image_urls=urls,
                      max_tokens=400).strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    try:
        return json.loads(raw)
    except Exception:
        return {"choice": "reject",
                "new_query": item.get("he", item["slug"]),
                "reason": f"selector returned unparseable JSON: {raw[:120]}"}


# ───────────────────────── Shutterstock API wrappers ────────────────────────

def ss_headers() -> dict:
    return {"Authorization": f"Bearer {SS_TOKEN}",
            "Accept": "application/json"}


def ss_subscription_id() -> str:
    global _SUBSCRIPTION_ID_CACHE
    if _SUBSCRIPTION_ID_CACHE:
        return _SUBSCRIPTION_ID_CACHE
    data = _get_json(f"{SS_API}/user/subscriptions", ss_headers())
    subs = data.get("data", [])
    if not subs:
        raise RuntimeError("no active Shutterstock subscription on this account")
    _SUBSCRIPTION_ID_CACHE = subs[0]["id"]
    return _SUBSCRIPTION_ID_CACHE


def ss_search(query: str, per_page: int = 5, image_type: str = "photo") -> list[dict]:
    params = urllib.parse.urlencode({
        "query": query,
        "per_page": per_page,
        "sort": "relevance",
        "image_type": image_type,
        "safe": "true",
    })
    data = _get_json(f"{SS_API}/images/search?{params}", ss_headers())
    out = []
    for r in data.get("data", []):
        preview = r.get("assets", {}).get("preview_600", {}).get("url") or \
                  r.get("assets", {}).get("preview", {}).get("url")
        out.append({
            "image_id": r["id"],
            "description": r.get("description", "")[:140],
            "preview_url": preview,
            "aspect": r.get("aspect", 1.0),
            "has_model_release": r.get("has_model_release", False),
        })
    return out


def ss_license(image_id: str, size: str = "huge", fmt: str = "jpg") -> str:
    sub = ss_subscription_id()
    url = f"{SS_API}/images/licenses?subscription_id={sub}&format={fmt}&size={size}"
    body = {"images": [{"image_id": image_id}]}
    data = _post_json(url, body, ss_headers())
    entry = data["data"][0]
    if "download" not in entry or "url" not in entry["download"]:
        raise RuntimeError(f"license returned no download url: {entry}")
    return entry["download"]["url"]


def ss_download(url: str, target: Path) -> int:
    req = urllib.request.Request(url, headers={"Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=180) as r:
        data = r.read()
    target.write_bytes(data)
    return len(data)


# ───────────────────────────── Item loaders ─────────────────────────────────

def load_scenery() -> list[dict]:
    lock = json.loads(CONTENT_LOCK.read_text("utf-8"))
    mission_text = {mid: m["mission_text"] for mid, m in lock["missions"].items()}
    props = json.loads(PROPS_JSON.read_text("utf-8"))
    out = []
    for p in props:
        out.append({
            "slug": p["slug"],
            "he": p.get("he", ""),
            "en_prompt": p.get("en_prompt", ""),
            "mission": p.get("mission", ""),
            "mission_text": mission_text.get(p.get("mission", ""), ""),
            "category": "scenery",
        })
    return out


# Small curated English hints so query crafter doesn't guess wildly at obscure
# Hebrew tool names. Optional — crafter also sees the Hebrew label.
TOOL_EN_HINTS = {
    "מצנח עגול רחב": "wide round parachute canopy",
    "גלשן רחיפה": "hang glider",
    "חליפת כנפיים": "wingsuit",
    "יריעת ברזנט": "tarp canvas sheet",
    "פטיש ומסמרים": "claw hammer with nails",
    "אוהל סיירים": "scout tent camping",
    "המפה המקומטת": "old crumpled treasure map paper",
    "משקפת שדה": "binoculars field",
    "מפתח לטרקטורון מונע": "ATV quad bike ignition key",
    "לוחות עץ ופטיש": "wooden planks and hammer",
    "רתמת אבטחה": "climbing safety harness",
    "רובה חבלים": "rope launcher grappling gun",
    "פנס עוצמתי": "heavy flashlight torch",
    "רשת הגנה": "protective net",
    "לפיד בוער": "burning torch fire",
    "ג'ריקן שמן": "metal jerrycan oil fuel",
    "ערכת כלי עבודה": "tool kit toolbox",
    "אופני הרים": "mountain bike",
    "דגל המשימה המקורי": "expedition flag on pole",
    "פריסקופ": "periscope optical",
    "לום ברזל": "crowbar iron pry bar",
    "חבל טיפוס": "climbing rope",
    "כריות אוויר מתנפחות": "inflatable airbags",
    "גרזן טיפוס": "ice climbing axe",
    "ערכת כריתה": "cutting tool kit saw",
    "מגל": "sickle hand scythe",
    "מצית חזק": "heavy duty lighter",
    "תיק חילוץ": "rescue kit backpack",
    "חבל ארוך": "long thick rope coil",
    "סולם חבלים": "rope ladder",
    "גלגלת": "pulley mechanical",
    "מסכת גז": "gas mask protective",
    "סכין רב-שימושי": "multi tool knife",
    "ערכת עזרה ראשונה": "first aid kit open",
    "פנס ראש": "headlamp head torch",
    "רדיו שדה": "field radio military",
    "דגל סיום": "finish line flag",
    "זיקוק חגיגה": "celebration flare firework",
    "כוס הניצחון": "victory trophy cup",
    "שלט מנצח": "winner podium sign",
    "מגאפון": "megaphone bullhorn",
    "כפפות טיפוס": "climbing gloves leather",
    "פטישון סדק": "chisel rock hammer",
    "מפתח ברגים": "wrench spanner",
}


def load_tools() -> list[dict]:
    """Flatten tools from content_lock.json into one item per (mission,slot).

    Builds synthetic en_prompt from Hebrew label + optional English hint.
    """
    lock = json.loads(CONTENT_LOCK.read_text("utf-8"))
    out = []
    for mid, m in lock["missions"].items():
        for t in m.get("tools", []):
            he = t["label"]
            en_hint = TOOL_EN_HINTS.get(he, "")
            slug = f"{mid}_{t['slot']}"  # e.g. "M1_A"
            en_prompt = (
                f"{en_hint}, isolated on white background, studio shot, "
                f"commercial catalog photo"
            ) if en_hint else (
                f"{he} — isolated on white background, studio shot, single subject"
            )
            out.append({
                "slug": slug,
                "he": he,
                "en_prompt": en_prompt,
                "mission": mid,
                "mission_text": m["mission_text"],
                "category": "tools",
                "expected_file": t["file"],  # preserve original Hebrew filename
                "points": t["points"],
            })
    return out


# ─────────────────────────────── Main loop ──────────────────────────────────

def load_log() -> dict:
    if LOG_PATH.exists():
        try:
            return json.loads(LOG_PATH.read_text("utf-8"))
        except Exception:
            return {}
    return {}


def save_log(log: dict) -> None:
    LOG_PATH.write_text(json.dumps(log, ensure_ascii=False, indent=2), "utf-8")


def process_item(item: dict, log: dict, dry_run: bool = False,
                 max_query_rounds: int = 2, per_query: int = 5) -> dict:
    slug = item["slug"]
    cat = item["category"]
    target = STAGING / cat / f"{slug}.jpg"
    entry = {"slug": slug, "category": cat, "he": item.get("he", ""),
             "status": "pending", "rounds": []}

    if log.get(f"{cat}/{slug}", {}).get("status") == "done" and target.exists():
        return {**log[f"{cat}/{slug}"], "skipped": True}

    queries = craft_queries(item)
    tried: set[str] = set()

    for rnd in range(max_query_rounds):
        # Collect candidates across all queries this round
        candidates: list[dict] = []
        seen_ids: set[str] = set()
        round_queries = queries[:3]
        for q in round_queries:
            if q in tried:
                continue
            tried.add(q)
            try:
                hits = ss_search(q, per_page=per_query)
            except urllib.error.HTTPError as e:
                entry["rounds"].append({"round": rnd + 1, "query": q,
                                        "error": f"search_http_{e.code}"})
                continue
            for h in hits:
                if h["image_id"] in seen_ids:
                    continue
                seen_ids.add(h["image_id"])
                candidates.append(h)

        if not candidates:
            entry["rounds"].append({"round": rnd + 1, "queries": round_queries,
                                    "error": "no_candidates"})
            break

        # Claude vision pick
        try:
            pick = pick_from_thumbnails(item, candidates[:15])
        except urllib.error.HTTPError as e:
            entry["rounds"].append({"round": rnd + 1, "queries": round_queries,
                                    "error": f"selector_http_{e.code}"})
            break

        entry["rounds"].append({
            "round": rnd + 1, "queries": round_queries,
            "candidates_shown": len(candidates[:15]),
            "pick": pick,
        })

        if pick.get("choice") == "pick":
            image_id = pick["image_id"]
            if dry_run:
                entry["status"] = "dry_pick"
                entry["picked_id"] = image_id
                return entry

            try:
                dl_url = ss_license(image_id)
                size = ss_download(dl_url, target)
                entry["status"] = "done"
                entry["picked_id"] = image_id
                entry["file"] = str(target)
                entry["bytes"] = size
                return entry
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", "replace")[:200]
                entry["rounds"][-1]["license_error"] = f"http_{e.code}: {body}"
                entry["status"] = "license_fail"
                return entry
            except Exception as e:
                entry["rounds"][-1]["license_error"] = f"{type(e).__name__}: {e}"
                entry["status"] = "license_fail"
                return entry

        # Rejected — get new query
        new_q = pick.get("new_query", "").strip()
        if new_q and new_q not in tried:
            queries = [new_q]  # try just this one next round
        else:
            entry["status"] = "reject_no_retry"
            return entry

    if entry["status"] == "pending":
        entry["status"] = "exhausted_rounds"
    return entry


def main(argv: list[str]) -> int:
    args = argv[1:]
    dry_run = False
    if "--dry-run" in args:
        dry_run = True
        args.remove("--dry-run")

    if not args:
        print("usage: shutterstock_agent.py [--dry-run] <scenery|tools|both> [slug_filter]")
        return 1

    mode = args[0]
    slug_filter = args[1] if len(args) > 1 else None

    items: list[dict] = []
    if mode in ("scenery", "both"):
        items += load_scenery()
    if mode in ("tools", "both"):
        items += load_tools()

    if slug_filter:
        items = [i for i in items if i["slug"] == slug_filter]
        if not items:
            print(f"no items match slug={slug_filter}")
            return 1

    log = load_log()
    total = len(items)
    print(f"Shutterstock Agent: {total} items ({mode}){' DRY RUN' if dry_run else ''}")
    print(f"Subscription: {ss_subscription_id()}")
    print("-" * 60)

    for i, item in enumerate(items, 1):
        slug = item["slug"]
        key = f"{item['category']}/{slug}"
        existing = log.get(key, {})
        if existing.get("status") == "done" and (STAGING / item["category"] / f"{slug}.jpg").exists():
            print(f"[{i:02}/{total}] {slug}: skip (done, id={existing.get('picked_id')})")
            continue

        print(f"[{i:02}/{total}] {slug} ({item.get('he','')}): processing...", flush=True)
        t0 = time.time()
        try:
            result = process_item(item, log, dry_run=dry_run)
        except Exception as e:
            result = {"slug": slug, "category": item["category"],
                      "status": "agent_crash", "error": f"{type(e).__name__}: {e}"}
        result["elapsed_s"] = round(time.time() - t0, 1)
        log[key] = result
        save_log(log)

        status = result.get("status", "?")
        pid = result.get("picked_id", "-")
        print(f"    -> {status} (id={pid}, {result['elapsed_s']}s)")

    print("\n" + "=" * 60)
    done = sum(1 for k, v in log.items() if v.get("status") == "done")
    fail = sum(1 for k, v in log.items() if v.get("status", "").endswith("_fail")
               or v.get("status") == "agent_crash")
    print(f"DONE: {done}   FAIL: {fail}   TOTAL_TRACKED: {len(log)}")
    print(f"Log: {LOG_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
