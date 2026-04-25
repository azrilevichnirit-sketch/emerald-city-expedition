"""Scenery prop generator — per iron rule, every prop goes through full protocol.

For each approved prop in _props_structured.json:
  1. Claude writes detailed Imagen prompt (isolated prop, clean bg for keying)
  2. Imagen 4 fast generates PNG
  3. Gemini vision QA verdict
  4. Claude vision director verdict
  5. If both pass → save to assets/scenery/<slug>.png + log protocol

Idempotent: already-delivered PASS props are skipped.
"""
import base64
import json
import time
import urllib.request
import urllib.error
from pathlib import Path

from debate_runner import call_claude, call_gemini, get_gemini_key, load_project_context

PROJECT = Path(__file__).resolve().parent.parent
PROPS = PROJECT / "pipeline" / "debates" / "scenery" / "_props_structured.json"
SCENERY_DIR = PROJECT / "assets" / "scenery"
SCENERY_DIR.mkdir(parents=True, exist_ok=True)
REVIEW_DIR = PROJECT / "pipeline" / "review" / "scenery"
REVIEW_DIR.mkdir(parents=True, exist_ok=True)
LOG_PATH = REVIEW_DIR / "_protocol_log.json"

IMG_MODEL = "imagen-4.0-fast-generate-001"


def imagen_generate(prompt_text):
    body = {
        "instances": [{"prompt": prompt_text}],
        "parameters": {"sampleCount": 1, "aspectRatio": "1:1"},
    }
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{IMG_MODEL}:predict?key={get_gemini_key()}"
    req = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        data = json.loads(urllib.request.urlopen(req, timeout=120).read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Imagen HTTP {e.code}: {err[:400]}")
    preds = data.get("predictions", [])
    if not preds or "bytesBase64Encoded" not in preds[0]:
        raise RuntimeError(f"no image in imagen response: {json.dumps(data)[:400]}")
    return base64.b64decode(preds[0]["bytesBase64Encoded"])


_BRIEF_CACHE = None
def _brief():
    global _BRIEF_CACHE
    if _BRIEF_CACHE is None:
        _BRIEF_CACHE = load_project_context()
    return _BRIEF_CACHE


def write_prompt(prop):
    system = (
        "You are a Visual Prompt Writer for Studio Emerald's tropical-expedition game. "
        "Task: produce ONE English Imagen-4 prompt (80-140 words) for a single scenery prop. "
        "The full project brief (all 15 missions + what each mission depicts) is included "
        "below — use it to disambiguate the prop's intended meaning in context. "
        "Style: cinematic photorealistic, muted tropical saturation, soft natural light, "
        "prop centered. "
        "\n\n**CRITICAL BACKGROUND RULE (per camera_bible.json → scenery):** "
        "The prop MUST be on a SOLID FLAT PURE GREEN SCREEN BACKGROUND, hex #00B140 "
        "(same chroma as tools/ and player_animations/). "
        "NO scene-matching ambient. NO baked floor/ground/rock/soil under the prop. "
        "NO environmental fog/haze. NO walls. NO shadows on ground. "
        "Just the prop isolated on flat #00B140 green. The Builder will chroma-key "
        "the green out in the compositor. "
        "Your prompt MUST end verbatim with the clause: "
        "'solid flat pure green screen background hex #00B140, no environment, "
        "no floor, no ground plane, no shadow, no scene context.'\n"
        "NO characters, NO humans, NO faces, NO text, NO logos. Single subject focus. "
        "The prop must be instantly readable as what it is in the mission's context. "
        "Output: prompt text only, no preamble, no JSON."
    )
    user = (
        f"{_brief()}\n\n"
        f"───── prop to prompt ─────\n"
        f"Mission: {prop.get('mission')}\n"
        f"Slug: {prop.get('slug')}\n"
        f"Hebrew label: {prop.get('he')}\n"
        f"Base description: {prop.get('en_prompt')}\n"
        f"CSS zone (context only): {prop.get('css','')}\n\n"
        "Write the Imagen-4 prompt now — in English, 80-140 words, mission-aware."
    )
    return call_claude(system, user, max_tokens=500).strip()


def qa_vision(img_bytes, prop, prompt):
    instr = (
        f"{_brief()}\n\n"
        f"───── QA sanity check ─────\n"
        f"Mission {prop.get('mission')}, prop slug '{prop.get('slug')}', "
        f"intended subject: '{prop.get('en_prompt')}'. "
        f"QA a single compositor-layer scenery prop PNG. "
        f"**STRICT on bg:** the image MUST be the prop on a solid flat green "
        f"#00B140 screen with no environment/floor/shadow. Fail if there is ANY "
        f"baked scene (ground, grass, floor, walls, fog). Be LENIENT on humans (some props ARE "
        f"humans, e.g., 'competitors_in_air' — allow silhouettes/distant figures when "
        f"called for). Fail if: (a) subject is clearly wrong, or (b) prominent "
        f"hard-to-remove text/logos, or (c) cartoon/illustration style, or (d) bg is not green. "
        f"Return STRICT JSON: {{\"verdict\":\"pass|fail\",\"notes\":\"...\"}}."
    )
    b64 = base64.b64encode(img_bytes).decode("ascii")
    try:
        resp = call_gemini(instr, "Review this generated prop image.", image_b64=b64, max_tokens=400)
        import re
        m = re.search(r"\{.*\}", resp, re.S)
        return json.loads(m.group(0)) if m else {"verdict": "fail", "notes": resp[:200]}
    except Exception as e:
        return {"verdict": "fail", "notes": f"qa error: {e}"}


def director_vision(img_bytes, prop, prompt, qa):
    instr = (
        f"{_brief()}\n\n"
        f"───── Director review ─────\n"
        f"You are the Director. Final gate for a SCENERY PROP ASSET (not a full scene). "
        f"Prop: '{prop.get('slug')}' (mission {prop.get('mission')}). QA verdict: {qa.get('verdict')}. "
        f"\n\n**CRITICAL understanding:** This is a compositor layer — one PNG that will be "
        f"positioned over a bg video via CSS. Judge it as a prop asset:\n"
        f"- Is the SUBJECT correct for the mission context (use project brief above)?\n"
        f"- Is it ISOLATED on clean/neutral background so the compositor can key/layer it?\n"
        f"- Is the style cinematic photorealistic, muted tropical saturation, no cartoon, no text?\n"
        f"- At small size, would a player instantly recognize what it is?\n"
        f"DO NOT require 'full scene context' — props are meant to be isolated for compositing.\n"
        f"DO NOT require action/motion — those are bg video's job.\n"
        f"\nReturn STRICT JSON: {{\"verdict\":\"pass|fix|redo\",\"notes\":\"...\"}}. "
        f"pass=usable prop asset; fix=small tweak (color/framing); redo=wrong subject."
    )
    b64 = base64.b64encode(img_bytes).decode("ascii")
    resp = call_claude(instr, "Review this image.", max_tokens=400, image_b64=b64)
    import re
    m = re.search(r"\{.*\}", resp, re.S)
    return json.loads(m.group(0)) if m else {"verdict": "redo", "notes": resp[:200]}


def load_log():
    if LOG_PATH.exists():
        return json.loads(LOG_PATH.read_text("utf-8"))
    return {}


def save_log(log):
    LOG_PATH.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")


def directors_debate(prop, history):
    """Run a director + production-designer + set-manager consultation to analyze
    why prior attempts failed and agree on a new visual strategy.

    Returns a Hebrew strategy paragraph that the prompt writer then converts to an
    Imagen prompt. Uses ALL prior attempts, not just the most recent.
    """
    hist_text = ""
    for h in history:
        hist_text += (
            f"\n--- attempt {h['attempt']} ---\n"
            f"prompt: {h['prompt'][:500]}\n"
            f"qa verdict: {h['qa'].get('verdict')} | notes: {(h['qa'].get('notes') or '')[:250]}\n"
            f"director verdict: {h['director'].get('verdict')} | notes: {(h['director'].get('notes') or '')[:350]}\n"
        )
    system = (
        "אתם צוות במאי + Production Designer + Set Manager של Studio Emerald. "
        "prop של rekuzi'a (scenery) נדחה מספר פעמים על ידי הדירקטור. "
        "התפקיד שלכם: לנתח למה כשל, ולהגדיר אסטרטגיה ויזואלית חדשה שתעבוד. "
        "שקלו: (1) האם ההבנה של האובייקט הייתה נכונה? (2) האם הרכיבים שהבימאי דרש נמצאים "
        "בפרומפטים? (3) האם Imagen מתקשה עם פריימינג/זווית/הרכב? (4) האם צריך לפצל ל-2 props? "
        "(5) האם צריך גישה פרשנית אחרת (למשל detail shot במקום wide shot)? "
        "הפלט: פסקה אחת בעברית, 80-160 מילים, המתארת את האסטרטגיה הוויזואלית החדשה: "
        "האובייקט המדויק (כאילו מתאר למצלם), זווית, תאורה, composition, ומה בבירור לא-לכלול."
    )
    user = (
        f"{_brief()}\n\n"
        f"Prop: {prop.get('slug')} (mission {prop.get('mission')})\n"
        f"Hebrew label: {prop.get('he')}\n"
        f"Original intent: {prop.get('en_prompt')}\n\n"
        f"Prior attempts + verdicts:{hist_text}\n\n"
        "כתבו את האסטרטגיה החדשה עכשיו."
    )
    return call_claude(system, user, max_tokens=700).strip()


def rewrite_prompt_with_feedback(prop, prev_prompt, director_notes, history=None):
    """Rewrite Imagen prompt. If history provided, first runs directors_debate to
    analyze all prior failures, then converts the strategy into a prompt."""
    strategy = ""
    if history:
        try:
            strategy = directors_debate(prop, history)
        except Exception as e:
            strategy = f"(directors_debate error: {e})"
    system = (
        "You are a Visual Prompt Writer. Prior prompts were rejected. "
        "The directors have agreed on a new visual strategy (Hebrew, below). "
        "Convert it faithfully into an Imagen-4 prompt (80-140 words, English). "
        "Rules: photorealistic, muted tropical saturation, no humans/faces, no text, "
        "isolated prop on clean bg for compositor keying. Follow the strategy exactly. "
        "Output: prompt text only."
    )
    user = (
        f"{_brief()}\n\n"
        f"Prop: {prop.get('slug')} (mission {prop.get('mission')}, {prop.get('he')})\n"
        f"Previous prompt:\n{prev_prompt}\n\n"
        f"Last director feedback: {director_notes}\n\n"
        f"Directors' new strategy (Hebrew):\n{strategy}\n\n"
        "Write the revised Imagen-4 prompt now, faithful to the strategy."
    )
    return call_claude(system, user, max_tokens=600).strip()


def run_prop(prop, log, max_attempts=8):
    slug = prop["slug"]
    final_path = SCENERY_DIR / f"{slug}.png"
    entry = log.get(slug, {})
    if entry.get("status") == "delivered" and final_path.exists():
        print(f"  [{slug}] already delivered — skip")
        return entry

    prompt = write_prompt(prop)
    history = []

    for attempt in range(1, max_attempts + 1):
        img_bytes = imagen_generate(prompt)
        tmp = REVIEW_DIR / f"{slug}_r{attempt}.png"
        tmp.write_bytes(img_bytes)

        qa = qa_vision(img_bytes, prop, prompt)
        director = director_vision(img_bytes, prop, prompt, qa)

        qa_pass = qa.get("verdict") == "pass"
        dir_pass = director.get("verdict") == "pass"

        history.append({
            "attempt": attempt,
            "prompt": prompt,
            "qa": qa,
            "director": director,
            "tmp_path": str(tmp),
        })

        if qa_pass and dir_pass:
            final_path.write_bytes(img_bytes)
            print(f"  [{slug}] pass (a{attempt}) -> {final_path.name}")
            return {
                "slug": slug,
                "mission": prop.get("mission"),
                "status": "delivered",
                "final_path": str(final_path),
                "attempts": history,
            }

        if attempt < max_attempts:
            feedback = director.get("notes") or qa.get("notes") or "generic retry"
            # From attempt 2 onward, run directors_debate using full history to pick a new visual strategy
            prompt = rewrite_prompt_with_feedback(prop, prompt, feedback, history=history if attempt >= 2 else None)
            print(f"  [{slug}] attempt {attempt}: qa={qa.get('verdict')} dir={director.get('verdict')} - rewriting (debate={attempt>=2})")
        else:
            print(f"  [{slug}] attempt {attempt}: qa={qa.get('verdict')} dir={director.get('verdict')} - exhausted")

    return {
        "slug": slug,
        "mission": prop.get("mission"),
        "status": "needs_human_review",
        "attempts": history,
    }


def main():
    props = json.loads(PROPS.read_text("utf-8"))
    log = load_log()
    print(f"props to process: {len(props)}")
    t0 = time.time()
    for i, prop in enumerate(props, 1):
        slug = prop["slug"]
        print(f"[{i}/{len(props)}] {slug} (mission {prop.get('mission')})")
        try:
            entry = run_prop(prop, log)
        except Exception as e:
            entry = {"slug": slug, "status": "error", "error": str(e)}
            print(f"  [{slug}] ERROR: {e}")
        log[slug] = entry
        save_log(log)
    total = time.time() - t0
    delivered = sum(1 for v in log.values() if v.get("status") == "delivered")
    flagged = sum(1 for v in log.values() if v.get("status") == "needs_human_review")
    errors = sum(1 for v in log.values() if v.get("status") == "error")
    print(f"\ndone in {int(total)}s. delivered={delivered} flagged={flagged} errors={errors}")


if __name__ == "__main__":
    main()
