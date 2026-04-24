"""Shutterstock SEARCHER — simple executor #1.

Runs one Shutterstock search exactly per the master's command. No choices,
no filters beyond what the master specified, no interpretation. Returns the
top-N results as a JSON envelope for the result_checker to inspect visually.

The searcher does NOT download images. It does NOT license. It only searches
and returns metadata + thumbnail URLs.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT = Path(__file__).resolve().parent.parent
KEYS = PROJECT / "keys"
SS_API = "https://api.shutterstock.com/v2"


def _load_key(env_var: str, file_path: Path) -> str:
    v = os.environ.get(env_var)
    if v:
        return v.strip()
    if file_path.exists():
        return file_path.read_text("utf-8").strip()
    raise RuntimeError(f"missing {env_var} env var or file {file_path}")


SS_TOKEN = _load_key("SHUTTERSTOCK_TOKEN", KEYS / "shutterstock" / "access_token.txt")


def ss_headers() -> dict:
    return {"Authorization": f"Bearer {SS_TOKEN}", "Accept": "application/json"}


def search(q: dict, per_page: int = 10) -> dict:
    """Run a single Shutterstock search per the master's query spec.

    q is the master's `primary_query` (or a fallback_query merged with primary
    defaults). Returns a raw-ish envelope suitable for the result_checker.
    """
    params: dict[str, str] = {
        "query": q["query"],
        "per_page": str(per_page),
        "sort": q.get("sort", "relevance"),
        "image_type": q["image_type"],
        "safe": "true" if q.get("safe", True) else "false",
    }
    orient = q.get("orientation")
    if orient and orient not in ("null", "None", ""):
        params["orientation"] = orient
    nop = q.get("number_of_people")
    if nop and nop not in ("null", "None", ""):
        params["number_of_people"] = str(nop)
    cat = q.get("category")
    if cat not in (None, "null", "None", ""):
        params["category"] = str(cat)

    url = f"{SS_API}/images/search?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers=ss_headers(), method="GET")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")[:400]
        return {"status": f"FAIL_http_{e.code}", "error": body,
                "query_used": q, "results": [], "total_count": 0, "returned": 0}
    except Exception as e:
        return {"status": "FAIL_exception", "error": f"{type(e).__name__}: {e}",
                "query_used": q, "results": [], "total_count": 0, "returned": 0}

    data = raw.get("data", [])
    results = []
    for r in data:
        assets = r.get("assets", {})
        # Pick the biggest reasonable thumbnail for vision inspection.
        thumb = (assets.get("preview_1500", {}).get("url")
                 or assets.get("preview_1000", {}).get("url")
                 or assets.get("preview", {}).get("url")
                 or assets.get("huge_thumb", {}).get("url")
                 or assets.get("large_thumb", {}).get("url"))
        results.append({
            "id": r.get("id"),
            "description": r.get("description", ""),
            "thumb_url": thumb,
            "aspect": r.get("aspect"),
            "image_type": r.get("image_type"),
            "has_model_release": r.get("has_model_release"),
        })

    total = raw.get("total_count", 0)
    return {
        "status": "OK" if results else "FAIL_zero_results",
        "query_used": q,
        "total_count": total,
        "returned": len(results),
        "results": results,
    }


def search_with_fallbacks(master_cmd: dict, per_page: int = 10) -> dict:
    """Run the master's primary_query; if zero results, cascade to fallbacks.

    Returns a single envelope with:
      - the query that actually produced results (may be a fallback)
      - a trail of attempts (for the ledger/checker)
    """
    attempts = []
    queries = [master_cmd["primary_query"]]
    for fb in master_cmd.get("fallback_queries", []):
        merged = {**master_cmd["primary_query"], **fb}
        queries.append(merged)

    last_envelope = None
    for q in queries:
        env = search(q, per_page=per_page)
        attempts.append({
            "query": q.get("query"),
            "image_type": q.get("image_type"),
            "status": env["status"],
            "total_count": env.get("total_count", 0),
            "returned": env.get("returned", 0),
        })
        last_envelope = env
        if env["status"] == "OK":
            env["attempts"] = attempts
            return env

    # All queries came back empty or errored.
    return {
        "status": "FAIL_all_queries_empty",
        "attempts": attempts,
        "query_used": queries[-1],
        "total_count": 0,
        "returned": 0,
        "results": [],
    }


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: shutterstock_searcher.py <master_cmd_json_file>")
        return 1
    master_cmd = json.loads(Path(argv[1]).read_text("utf-8"))
    env = search_with_fallbacks(master_cmd)
    env["item_slug"] = master_cmd.get("item_slug")
    env["round"] = master_cmd.get("_round", 1)
    print(json.dumps(env, ensure_ascii=False, indent=2))
    return 0 if env["status"] == "OK" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
