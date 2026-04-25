"""Regenerate one or more scenery props under the 3-director panel gate.

The fix for judge-noise we identified during the stuck-props episode:
single-director vision produced inconsistent verdicts on visually-equivalent
images. This regenerator uses the full 3-engine Director panel (Claude +
Gemini + GPT) + Gemini QA. A candidate is promoted only when all 4 agree.

Usage:
    python regen_prop_with_panel.py <slug> [<slug> ...]

On success: writes assets/scenery/<slug>.png, updates review/scenery/_protocol_log.json.
"""
import base64
import json
import sys
import time
from pathlib import Path

from generate_scenery_props import (
    imagen_generate, write_prompt, rewrite_prompt_with_feedback,
    SCENERY_DIR, REVIEW_DIR, LOG_PATH, load_log, save_log, PROPS,
)
from resolve_via_panel import qa_panel_check, director_vote, ENGINES

MAX_ATTEMPTS = 10


def regen_one(prop, log):
    slug = prop["slug"]
    final_path = SCENERY_DIR / f"{slug}.png"
    entry = log.get(slug, {"slug": slug, "mission": prop.get("mission")})
    history = list(entry.get("attempts", []))

    last_prompt = None
    last_notes = None

    for i in range(MAX_ATTEMPTS):
        attempt_n = len(history) + 1
        print(f"\n  [{slug}] attempt {attempt_n}")

        # Write prompt (first attempt fresh; later attempts use feedback)
        try:
            if last_prompt is None:
                prompt = write_prompt(prop)
            else:
                prompt = rewrite_prompt_with_feedback(
                    prop, last_prompt, last_notes,
                    history=history if attempt_n >= 2 else None,
                )
        except Exception as e:
            print(f"  [{slug}] prompt error: {e}")
            continue

        # Generate image
        try:
            img = imagen_generate(prompt)
        except Exception as e:
            print(f"  [{slug}] imagen error: {e}")
            continue

        tmp = REVIEW_DIR / "_candidates" / f"{slug}_r{attempt_n}.png"
        tmp.parent.mkdir(exist_ok=True)
        tmp.write_bytes(img)

        # Evaluate via panel
        img_b64 = base64.b64encode(img).decode("ascii")
        qa = qa_panel_check(img_b64, prop)
        panel = {}
        for eng in ENGINES:
            try:
                panel[eng] = director_vote(eng, img_b64, prop, qa.get("verdict"))
            except Exception as e:
                panel[eng] = {"verdict": "redo", "notes": f"engine error: {e}"}

        qa_ok = qa.get("verdict") == "pass"
        pass_count = sum(1 for v in panel.values() if v.get("verdict") == "pass")
        unanimous = pass_count == 3

        c_v = panel["claude"].get("verdict")
        g_v = panel["gemini"].get("verdict")
        o_v = panel["openai"].get("verdict")
        print(f"  [{slug}] qa={qa.get('verdict')} claude={c_v} gemini={g_v} openai={o_v} "
              f"{'** UNANIMOUS **' if unanimous else ''}")

        history.append({
            "attempt": attempt_n,
            "prompt": prompt,
            "qa": qa,
            "panel": panel,
            "pass_count": pass_count,
            "tmp_path": str(tmp),
        })

        if qa_ok and unanimous:
            final_path.write_bytes(img)
            print(f"  [{slug}] PROMOTED -> {final_path.name}")
            return {
                "slug": slug,
                "mission": prop.get("mission"),
                "status": "delivered",
                "final_path": str(final_path),
                "resolved_via": "panel_gate_regeneration",
                "attempts": history,
            }

        # Feed the dominant objection back as notes
        dominant = panel["claude"] if panel["claude"].get("verdict") != "pass" else \
                   panel["gemini"] if panel["gemini"].get("verdict") != "pass" else \
                   panel["openai"]
        last_prompt = prompt
        last_notes = (
            f"qa={qa.get('notes','')[:200]} | "
            f"director objection: {dominant.get('notes','')[:300]}"
        )

    return {
        "slug": slug,
        "mission": prop.get("mission"),
        "status": "needs_human_review",
        "attempts": history,
        "note": f"exhausted {MAX_ATTEMPTS} attempts under panel gate",
    }


def main(slugs):
    props_all = json.loads(PROPS.read_text("utf-8"))
    by_slug = {p["slug"]: p for p in props_all}
    log = load_log()
    t0 = time.time()

    for slug in slugs:
        prop = by_slug.get(slug)
        if not prop:
            print(f"[{slug}] not found in _props_structured.json")
            continue
        print(f"\n[{slug}] mission={prop.get('mission')} — regen under panel gate")
        result = regen_one(prop, log)
        log[slug] = result
        save_log(log)

    print(f"\ndone in {int(time.time()-t0)}s")
    delivered = sum(1 for s in slugs if log.get(s, {}).get("status") == "delivered")
    print(f"delivered: {delivered}/{len(slugs)}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: python regen_prop_with_panel.py <slug> [<slug> ...]")
        sys.exit(1)
    main(sys.argv[1:])
