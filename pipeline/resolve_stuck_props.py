"""Last-resort resolver for props the generator couldn't close through the
Visual Prompt Writer layer. Here the Director writes the Imagen prompt DIRECTLY,
having seen every prior failed attempt + its own rejection notes. One attempt
per iteration; the Director evaluates; loop until Director passes.

Per Nirit's iron rule — keep iterating until the Director approves.
"""
import base64
import json
import time
from pathlib import Path

from debate_runner import call_claude, call_gemini, load_project_context
from generate_scenery_props import (
    imagen_generate, qa_vision, director_vision, load_log, save_log,
    SCENERY_DIR, REVIEW_DIR,
)

PROJECT = Path(__file__).resolve().parent.parent
PROPS = PROJECT / "pipeline" / "debates" / "scenery" / "_props_structured.json"


def director_writes_prompt(prop, history):
    """Director writes the Imagen prompt DIRECTLY, with full view of the current
    failure pattern. No mediator. Can see last rejected image via vision."""
    hist = ""
    for h in history[-6:]:  # last 6 attempts' prompts + director notes
        hist += (
            f"\n--- attempt {h.get('attempt')} ---\n"
            f"prompt: {h.get('prompt','')[:400]}\n"
            f"director verdict: {h.get('director',{}).get('verdict')} | "
            f"notes: {(h.get('director',{}).get('notes') or '')[:300]}\n"
        )
    # vision reference: the last failed image
    last_tmp = history[-1].get("tmp_path") if history else None
    image_b64 = None
    if last_tmp and Path(last_tmp).exists():
        image_b64 = base64.b64encode(Path(last_tmp).read_bytes()).decode("ascii")

    system = (
        "You are the Director of Studio Emerald. A scenery PROP (compositor layer) has been "
        "rejected by you 8+ times. Visual Prompt Writers kept missing your intent. "
        "NOW YOU WRITE THE IMAGEN PROMPT YOURSELF — directly, no mediator. "
        "You have the power and accountability. The prompt you emit will be sent straight to "
        "Imagen-4. Then YOU evaluate the output. You iterate until you approve. "
        "Rules for the prompt: English, 80-160 words, photorealistic, muted tropical saturation, "
        "no text/logos, isolated subject on neutral bg (plain sky/soft gradient/simple ambient) "
        "for compositor keying. Describe SUBJECT, FRAMING, LIGHTING, STYLE explicitly. "
        "If prior attempts failed because subject was misinterpreted, pick a FRAMING that "
        "eliminates ambiguity (e.g., 'medium shot from eye level' vs 'aerial wide'). "
        "If the concept can't be rendered cleanly by Imagen — decompose: pick the single "
        "most instantly-recognizable sub-element. "
        "Output: prompt text only, no preamble."
    )
    user = (
        f"{load_project_context()}\n\n"
        f"Prop you are directing: {prop.get('slug')} (mission {prop.get('mission')}, "
        f"Hebrew: {prop.get('he')})\n"
        f"Original intent: {prop.get('en_prompt')}\n\n"
        f"Prior attempts + your own rejection reasons:{hist}\n\n"
        "Write the Imagen-4 prompt now — as the Director, in your own voice. "
        "Be prescriptive. Decompose if needed to something Imagen can actually render."
    )
    return call_claude(system, user, max_tokens=800, image_b64=image_b64).strip()


def resolve_prop(prop, log, max_extra=10):
    slug = prop["slug"]
    final_path = SCENERY_DIR / f"{slug}.png"
    entry = log.get(slug, {})
    if entry.get("status") == "delivered" and final_path.exists():
        print(f"  [{slug}] already delivered -- skip")
        return entry
    history = list(entry.get("attempts", []))
    start_attempt = len(history) + 1

    for i in range(max_extra):
        attempt_n = start_attempt + i
        print(f"  [{slug}] director-driven attempt {attempt_n}")
        try:
            prompt = director_writes_prompt(prop, history)
        except Exception as e:
            print(f"  [{slug}] director prompt error: {e}")
            continue
        try:
            img = imagen_generate(prompt)
        except Exception as e:
            print(f"  [{slug}] imagen error: {e}")
            entry["status"] = "error"
            entry["error"] = str(e)
            return entry
        tmp = REVIEW_DIR / f"{slug}_director_a{attempt_n}.png"
        tmp.write_bytes(img)
        qa = qa_vision(img, prop, prompt)
        director = director_vision(img, prop, prompt, qa)
        history.append({
            "attempt": attempt_n,
            "prompt": prompt,
            "qa": qa,
            "director": director,
            "tmp_path": str(tmp),
            "source": "director_writes",
        })
        qa_ok = qa.get("verdict") == "pass"
        dir_ok = director.get("verdict") == "pass"
        print(f"  [{slug}] a{attempt_n}: qa={qa.get('verdict')} dir={director.get('verdict')}")
        if qa_ok and dir_ok:
            final_path.write_bytes(img)
            print(f"  [{slug}] PASS -> {final_path.name}")
            return {
                "slug": slug,
                "mission": prop.get("mission"),
                "status": "delivered",
                "final_path": str(final_path),
                "attempts": history,
                "resolved_via": "director_writes_prompt",
            }
    return {
        "slug": slug,
        "mission": prop.get("mission"),
        "status": "needs_human_review",
        "attempts": history,
        "resolver_note": f"director-driven strategy also exhausted after {max_extra} attempts",
    }


def main(targets=None):
    all_props = json.loads(PROPS.read_text("utf-8"))
    by_slug = {p["slug"]: p for p in all_props}
    if not targets:
        log = load_log()
        targets = [slug for slug, e in log.items()
                   if e.get("status") != "delivered"
                   and slug in by_slug]
    print(f"resolver targets: {targets}")
    log = load_log()
    t0 = time.time()
    for i, slug in enumerate(targets, 1):
        prop = by_slug.get(slug)
        if not prop:
            print(f"  [{slug}] not in _props_structured.json -- skip")
            continue
        print(f"[{i}/{len(targets)}] {slug} (mission {prop.get('mission')})")
        try:
            entry = resolve_prop(prop, log)
        except Exception as e:
            entry = log.get(slug, {"slug": slug})
            entry["status"] = "error"
            entry["error"] = str(e)
            print(f"  [{slug}] ERROR: {e}")
        log[slug] = entry
        save_log(log)
    total = time.time() - t0
    delivered = sum(1 for v in log.values() if v.get("status") == "delivered")
    print(f"\ndone in {int(total)}s. total delivered={delivered}/{len(log)}")


if __name__ == "__main__":
    import sys
    tgts = sys.argv[1:] if len(sys.argv) > 1 else None
    main(tgts)
