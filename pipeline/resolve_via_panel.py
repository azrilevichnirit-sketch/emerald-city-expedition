"""Panel-based resolver for the 5 stuck scenery props.

The single-Director judgment was noisy: the same Claude vision call flipped
PASS -> REDO on visually equivalent images across attempts. Fix: replace the
single judge with a 3-engine panel (Claude + Gemini + GPT), each playing the
Director role on the same image with the same criteria. A candidate promotes
to final ONLY when QA (Gemini, lenient) passes AND all three directors pass.

We don't spend more Imagen quota — we re-evaluate the 8 tmp candidates already
on disk at pipeline/review/scenery/<slug>_r<N>.png. If none pass unanimously,
we report back for a round of generation under the panel gate.

Per Nirit: the three directors must be DIFFERENT from each other, and every
artifact must pass all three + QA before reaching her desk.
"""
import base64
import json
import re
from pathlib import Path

from debate_runner import call_engine, call_gemini, load_project_context
from generate_scenery_props import SCENERY_DIR, REVIEW_DIR, LOG_PATH, _brief

PROJECT = Path(__file__).resolve().parent.parent
PROPS_PATH = PROJECT / "pipeline" / "debates" / "scenery" / "_props_structured.json"

STUCK = [
    "rival_team_disappearing",
    "escape_boat_distant",
    "main_boat_at_shore",
    "finish_line",
    "distant_celebration_lights",
]

ENGINES = ["claude", "gemini", "openai"]


def _parse_json(resp):
    m = re.search(r"\{.*\}", resp, re.S)
    if not m:
        return {"verdict": "redo", "notes": resp[:200]}
    try:
        return json.loads(m.group(0))
    except Exception:
        return {"verdict": "redo", "notes": resp[:200]}


def qa_panel_check(img_b64, prop):
    """Gemini QA gate — lenient sanity check."""
    instr = (
        f"{_brief()}\n\n"
        f"QA sanity check for scenery prop '{prop['slug']}' (mission {prop['mission']}). "
        f"Intended subject: {prop.get('en_prompt')}. "
        f"LENIENT: neutral/gray/sky/gradient bg OK; distant/small humans OK when subject calls for them. "
        f"Fail ONLY if: (a) subject clearly wrong, (b) prominent text/logos, (c) cartoon/illustration style. "
        f"Return STRICT JSON: {{\"verdict\":\"pass|fail\",\"notes\":\"...\"}}."
    )
    resp = call_gemini(instr, "Review this generated prop image.",
                       image_b64=img_b64, max_tokens=350)
    return _parse_json(resp)


def director_vote(engine, img_b64, prop, qa_verdict):
    """Single director-role vote from one engine."""
    system = (
        f"{_brief()}\n\n"
        f"You are the Director of Studio Emerald. You are ONE of THREE independent directors "
        f"reviewing a SCENERY PROP compositor asset for mission {prop['mission']}. "
        f"The other two directors (other AI engines) judge separately; your vote stands on its own. "
        f"Prop slug: '{prop['slug']}' | Hebrew: {prop.get('he')} | Intent: {prop.get('en_prompt')}. "
        f"QA pre-check verdict: {qa_verdict}. "
        f"\n\n**This is a compositor PNG — one isolated layer** to be positioned via CSS over a bg video. "
        f"Judge it as a prop asset:\n"
        f"- Is the SUBJECT the right thing for this mission's narrative?\n"
        f"- Is it isolated enough on a clean/neutral bg for compositor keying?\n"
        f"- Cinematic photorealistic tropical style, no cartoon, no text/logos?\n"
        f"- Would a player instantly recognize it at small size in the mission context?\n"
        f"DO NOT demand full-scene context or motion — the bg video handles those.\n"
        f"Be decisive; do not flip on minor nitpicks if the subject reads correctly.\n\n"
        f"Return STRICT JSON: {{\"verdict\":\"pass|fix|redo\",\"notes\":\"one sentence why\"}}. "
        f"pass=ship as-is; fix=tiny tweak would help; redo=wrong subject/concept."
    )
    resp = call_engine(engine, system, "Review this prop image.",
                       image_b64=img_b64, max_tokens=350)
    return _parse_json(resp)


def evaluate_candidate(img_path, prop):
    """Run QA + 3-director panel on one PNG. Return structured result."""
    img_bytes = Path(img_path).read_bytes()
    img_b64 = base64.b64encode(img_bytes).decode("ascii")

    qa = qa_panel_check(img_b64, prop)
    qa_ok = qa.get("verdict") == "pass"

    panel = {}
    for eng in ENGINES:
        try:
            v = director_vote(eng, img_b64, prop, qa.get("verdict"))
        except Exception as e:
            v = {"verdict": "redo", "notes": f"engine error: {e}"}
        panel[eng] = v

    pass_count = sum(1 for v in panel.values() if v.get("verdict") == "pass")
    unanimous_pass = pass_count == 3
    gate_ok = qa_ok and unanimous_pass

    return {
        "path": str(img_path),
        "qa": qa,
        "panel": panel,
        "pass_count": pass_count,
        "gate_ok": gate_ok,
    }


def candidate_paths(slug):
    paths = sorted(REVIEW_DIR.glob(f"{slug}_r*.png"))
    return paths


def resolve_one(prop):
    slug = prop["slug"]
    candidates = candidate_paths(slug)
    print(f"\n[{slug}] {len(candidates)} tmp candidates on disk")
    if not candidates:
        return {"slug": slug, "status": "no_candidates"}

    results = []
    winner = None
    for p in candidates:
        res = evaluate_candidate(p, prop)
        c_votes = res["panel"]["claude"].get("verdict")
        g_votes = res["panel"]["gemini"].get("verdict")
        o_votes = res["panel"]["openai"].get("verdict")
        print(f"  {p.name}: qa={res['qa'].get('verdict')} "
              f"claude={c_votes} gemini={g_votes} openai={o_votes} "
              f"{'** GATE OK **' if res['gate_ok'] else ''}")
        results.append(res)
        if res["gate_ok"] and winner is None:
            winner = res

    if winner:
        final = SCENERY_DIR / f"{slug}.png"
        final.write_bytes(Path(winner["path"]).read_bytes())
        print(f"  [{slug}] PROMOTED {Path(winner['path']).name} -> {final.name}")
        return {
            "slug": slug,
            "status": "delivered",
            "final_path": str(final),
            "resolved_via": "panel_vote",
            "winner_tmp": winner["path"],
            "panel": winner["panel"],
            "qa": winner["qa"],
            "candidates_evaluated": len(results),
            "all_results": results,
        }

    # No unanimous pass — report the best effort
    ranked = sorted(results, key=lambda r: r["pass_count"], reverse=True)
    best = ranked[0] if ranked else None
    return {
        "slug": slug,
        "status": "panel_no_unanimous",
        "best_pass_count": best["pass_count"] if best else 0,
        "best_path": best["path"] if best else None,
        "all_results": results,
    }


def main():
    props = json.loads(PROPS_PATH.read_text("utf-8"))
    by_slug = {p["slug"]: p for p in props}
    log = json.loads(LOG_PATH.read_text("utf-8")) if LOG_PATH.exists() else {}

    summary = {}
    for slug in STUCK:
        prop = by_slug.get(slug)
        if not prop:
            print(f"[{slug}] not in props file -- skip")
            continue
        result = resolve_one(prop)
        summary[slug] = result
        # Merge into protocol log (preserve old attempts)
        entry = log.get(slug, {})
        entry.update({
            "slug": slug,
            "mission": prop.get("mission"),
            "status": result["status"] if result["status"] == "delivered" else entry.get("status", "needs_panel_generation"),
            "panel_review": {
                "status": result["status"],
                "best_pass_count": result.get("best_pass_count"),
                "winner_tmp": result.get("winner_tmp"),
                "panel": result.get("panel"),
                "qa": result.get("qa"),
                "resolved_via": result.get("resolved_via"),
            },
        })
        if result["status"] == "delivered":
            entry["final_path"] = result["final_path"]
            entry.pop("error", None)
        log[slug] = entry
        LOG_PATH.write_text(json.dumps(log, indent=2, ensure_ascii=False), "utf-8")

    # Summary report
    out = REVIEW_DIR / "_panel_review_summary.json"
    out.write_text(json.dumps(summary, indent=2, ensure_ascii=False), "utf-8")
    print(f"\n=== PANEL REVIEW SUMMARY ===")
    for slug, r in summary.items():
        if r["status"] == "delivered":
            print(f"  [{slug}] DELIVERED via {Path(r['winner_tmp']).name}")
        else:
            print(f"  [{slug}] {r['status']} (best={r.get('best_pass_count')}/3)")
    print(f"\nfull report -> {out}")
    return summary


if __name__ == "__main__":
    main()
