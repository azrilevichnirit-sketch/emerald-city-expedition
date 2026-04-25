"""Transition video generator — 2-second clips connecting mission N to mission N+1.

Per Nirit's direction:
  - Transitions ARE part of the film (not text checkpoints)
  - Duration: 2 seconds each (short, snappy — it's still a game)
  - Director-authored (brief + continuity)
  - Smart budget: reuse master clips across similar motifs; pack 2-per-5s when possible

Protocol (7 steps):
  [1] Director group-planning debate (all 10 transitions, 3 engines x 8 rounds)
      → output: master_clips plan + mapping transition_id -> (clip, cut_range)
  [2] Visual Prompt Writer (Claude) writes Veo prompt per master clip
  [3] Veo 3 fast text-to-video (~5s masters)
  [4] ffmpeg cuts each master into 2s transition mp4s per the director's mapping
  [5] Gemini QA on 2x2 keyframe grid of each 2s cut
  [6] 3-director panel (Claude + Gemini + GPT) on each 2s cut
  [7] Unanimous pass required -> assets/transitions/T_<mission>.mp4

Idempotent: delivered transitions are skipped.
"""
import base64
import json
import re
import subprocess
import time
from pathlib import Path
from PIL import Image

import os
from debate_runner import (
    run_debate, call_claude, call_gemini, call_engine,
    DEBATES_DIR, load_project_context, GEMINI_KEYS,
)
from generate_backgrounds import step3_veo as _step3_veo_raw  # reuse Veo submit+poll+download
from resolve_via_panel import ENGINES, _parse_json  # NOTE: we do NOT reuse qa_panel_check/director_vote — those are scenery-prop specific (expect isolated layer on neutral bg). Transitions are full-screen bg videos; we use transition-specific checks below.


def step3_veo(prompt_text):
    """Veo call with automatic KEY_B failover on 429/RESOURCE_EXHAUSTED.

    Tries KEY_A first (GEMINI_KEY_IDX=0). On 429, retries with KEY_B (idx=1).
    If both exhausted, raises the second error.
    """
    orig = os.environ.get("GEMINI_KEY_IDX", "0")
    try:
        os.environ["GEMINI_KEY_IDX"] = "0"
        return _step3_veo_raw(prompt_text)
    except Exception as e:
        msg = str(e)
        is_quota = "429" in msg or "RESOURCE_EXHAUSTED" in msg or "quota" in msg.lower()
        if not is_quota or len(GEMINI_KEYS) < 2:
            raise
        print(f"  Veo 429 on KEY_A — failover to KEY_B")
        os.environ["GEMINI_KEY_IDX"] = "1"
        try:
            return _step3_veo_raw(prompt_text)
        finally:
            os.environ["GEMINI_KEY_IDX"] = orig
    finally:
        os.environ["GEMINI_KEY_IDX"] = orig

PROJECT = Path(__file__).resolve().parent.parent
TRANS_DIR = PROJECT / "assets" / "transitions"
TRANS_DIR.mkdir(parents=True, exist_ok=True)
REVIEW_DIR = PROJECT / "pipeline" / "review" / "transitions"
REVIEW_DIR.mkdir(parents=True, exist_ok=True)
CANDIDATES_DIR = REVIEW_DIR / "_candidates"
CANDIDATES_DIR.mkdir(parents=True, exist_ok=True)
LOG_PATH = REVIEW_DIR / "_protocol_log.json"
DEBATE_OUT = DEBATES_DIR / "transitions"
DEBATE_OUT.mkdir(parents=True, exist_ok=True)
PLAN_PATH = REVIEW_DIR / "_master_plan.json"

LOCK = json.loads((PROJECT / "content_lock.json").read_text("utf-8"))


TRANSITIONS = [
    {"id": "T_M1",  "after": "M1",  "before": "M2",
     "description": "אנימציית נחיתה מהירה אל תוך סבך הג'ונגל. השמיים מתקדרים"},
    {"id": "T_M3",  "after": "M3",  "before": "M4",
     "description": "התקדמות בנתיב שנבחר עד להגעה לצוק שבו השביל נגמר"},
    {"id": "T_M4",  "after": "M4",  "before": "M5",
     "description": "כניסה לצמחייה סבוכה וחשוכה יותר. המצלמה מתקרבת אל פני הדמות"},
    {"id": "T_M6",  "after": "M6",  "before": "M7",
     "description": "נסיעה מהירה. בדרך עוברים ליד מבנה עתיק מרשים"},
    {"id": "T_M7",  "after": "M7",  "before": "M8",
     "description": "הגעה לקיר סלע ענק שחוסם את המעבר לעמק הנסתר"},
    {"id": "T_M9",  "after": "M9",  "before": "M10",
     "description": "הליכה במנהרה חשוכה עם הדים של מים זורמים. על הרצפה חפץ מוזר"},
    {"id": "T_M10", "after": "M10", "before": "M11",
     "description": "אור בקצה המנהרה. יציאה למרפסת סלע מעל מפל אדיר"},
    {"id": "T_M12", "after": "M12", "before": "M13",
     "description": "הגעה לשערי העיר המוזהבת. הכל נראה כמבוך סבוך"},
    {"id": "T_M13", "after": "M13", "before": "M14",
     "description": "כניסה להיכל המזבח המרכזי. דממה. השומרים נשמעים ברקע"},
    {"id": "T_M14", "after": "M14", "before": "M15",
     "description": "ריצה מטורפת לעבר היציאה מהעיר. קו הסיום נראה באופק"},
]


def load_log():
    return json.loads(LOG_PATH.read_text("utf-8")) if LOG_PATH.exists() else {}


def save_log(log):
    LOG_PATH.write_text(json.dumps(log, indent=2, ensure_ascii=False), "utf-8")


# ───────── step 1: group-planning debate ─────────
def step1_group_planning():
    """3-engine director debate decides master_clips + mapping. Idempotent."""
    if PLAN_PATH.exists():
        print(f"[1] using cached plan from {PLAN_PATH.name}")
        return json.loads(PLAN_PATH.read_text("utf-8"))

    ctx_lines = []
    for t in TRANSITIONS:
        after_text = LOCK["missions"].get(t["after"], {}).get("mission_text", "")[:200]
        before_text = LOCK["missions"].get(t["before"], {}).get("mission_text", "")[:200]
        ctx_lines.append(
            f"  {t['id']}: after {t['after']} -> before {t['before']}\n"
            f"    transition_desc: {t['description']}\n"
            f"    M{t['after']} ends: ...{after_text[-120:]}\n"
            f"    M{t['before']} opens: {before_text[:120]}..."
        )
    ctx = "10 TRANSITIONS TO DESIGN:\n" + "\n".join(ctx_lines)

    question = (
        "אתם (3 במאים) מתכננים סט מעברים קולנועיים למשחק. "
        "כל מעבר הוא 2 שניות בלבד. Veo 3 fast מייצר ~5 שניות בחיתוך אחד. "
        "**המטרה: חיסכון חכם ב-Veo quota + שליטה במאית על continuity.** "
        "החלטות שאתם צריכים לקבל:\n"
        "1) אילו מ-10 המעברים חולקים motif ויזואלי זהה (אותו clip, אותו cut, שימוש חוזר)?\n"
        "2) אילו זוגות של מעברים ניתן לארוז בתוך master_clip אחד של 5 שניות "
        "   (חיתוך 0-2s לאחד, 3-5s לשני — שונים זה מזה אבל באותו motif)?\n"
        "3) אילו דורשים master_clip ייחודי?\n"
        "4) לכל master_clip — בריף ויזואלי קצר (מיקום, תנועת מצלמה, אווירה, רצף) "
        "   שיהיה הבסיס לפרומפט Veo.\n\n"
        "החזר ב-final_decision.synthesis **JSON מובנה בלבד** בפורמט:\n"
        "```json\n"
        "{\n"
        "  \"master_clips\": [\n"
        "    {\"name\": \"jungle_forward\", "
        "\"brief\": \"<Hebrew 2-3 sentences: location+camera+mood>\", "
        "\"camera\": \"<en: slow dolly forward / low push / etc>\", "
        "\"duration_sec\": 5}\n"
        "  ],\n"
        "  \"mapping\": [\n"
        "    {\"transition_id\": \"T_M3\", \"master_clip\": \"jungle_forward\", "
        "\"cut_start\": 0.0, \"cut_end\": 2.0, "
        "\"continuity_note\": \"<how this cut bridges M3 end to M4 start>\"}\n"
        "  ]\n"
        "}\n"
        "```\n"
        "חובה: כל 10 ה-transition_ids חייבים להופיע ב-mapping."
    )

    # Reuse existing debate output if present (idempotent)
    debate_file = DEBATE_OUT / "director_transitions_group_planning.json"
    if debate_file.exists():
        print("[1] reusing existing debate output")
        r = json.loads(debate_file.read_text("utf-8"))
    else:
        r = run_debate(
            role="director",
            scene_id="transitions_group_planning",
            question=question,
            context=ctx,
            image_path=None,
            rounds=8,
            save=True,
            output_dir=DEBATE_OUT,
            mode="design",
        )

    # The full plan lives in the final moderator_summary (synthesis is truncated to 400c).
    rounds = r.get("rounds") or []
    if not rounds:
        raise RuntimeError("debate produced no rounds")
    blob = rounds[-1].get("moderator_summary") or ""
    fd = r.get("final_decision") or {}
    if not blob:
        blob = fd.get("synthesis") or ""

    # Extract JSON block (inside ```json ... ``` or bare {})
    m = re.search(r"\{\s*\"master_clips\"[\s\S]*?\n\}\s*(?:```|$)", blob, re.S)
    if not m:
        m = re.search(r"\{[\s\S]*\"master_clips\"[\s\S]*\}", blob, re.S)
    if not m:
        raise RuntimeError(f"director planning debate did not return structured JSON.\nblob head:\n{blob[:1500]}")
    raw_json = m.group(0)
    # Strip trailing ``` if captured
    raw_json = re.sub(r"```\s*$", "", raw_json).strip()
    plan = json.loads(raw_json)

    # Sanity check: all 10 transitions mapped
    mapped = {x["transition_id"] for x in plan["mapping"]}
    missing = [t["id"] for t in TRANSITIONS if t["id"] not in mapped]
    if missing:
        raise RuntimeError(f"plan missing transitions: {missing}")

    PLAN_PATH.write_text(json.dumps(plan, indent=2, ensure_ascii=False), "utf-8")
    print(f"[1] plan saved to {PLAN_PATH.name}: "
          f"{len(plan['master_clips'])} masters -> {len(plan['mapping'])} transitions")
    return plan


# ───────── step 2: write prompt per master ─────────
def step2_write_prompt(master, plan):
    uses = [m for m in plan["mapping"] if m["master_clip"] == master["name"]]
    use_summary = "; ".join(
        f"{u['transition_id']} ({u['cut_start']}-{u['cut_end']}s)" for u in uses
    )
    system = (
        "You are a Visual Prompt Writer. Produce an English Veo-3 text-to-video prompt "
        "(100-180 words) for a short transition clip between game missions. "
        "Rules: ~5s duration, 16:9, cinematic photorealistic, muted tropical saturation, "
        "ground-POV camera, NO humans/characters (player is layered on top separately), "
        "NO text/logos. The clip will be trimmed into 2-second segments, each reused "
        "as a separate mission transition. Design for density and continuity: the first "
        "2 seconds and the final 2 seconds should BOTH look cinematic in isolation. "
        "Output: prompt text only, no preamble."
    )
    user = (
        f"{load_project_context()}\n\n"
        f"───── master clip spec ─────\n"
        f"name: {master['name']}\n"
        f"director brief: {master.get('brief','')}\n"
        f"camera direction: {master.get('camera','')}\n"
        f"cuts it serves: {use_summary}\n\n"
        "Write the Veo-3 prompt now."
    )
    return call_claude(system, user, max_tokens=700).strip()


# ───────── step 2b: pre-Veo prompt review (TEXT ONLY — saves Veo quota) ─────────
def _qa_prompt_review(prompt_text, master, plan):
    """QA gate for the prompt TEXT (before spending Veo). Gemini, lenient."""
    uses = [m for m in plan["mapping"] if m["master_clip"] == master["name"]]
    use_summary = "; ".join(
        f"{u['transition_id']} ({u['cut_start']}-{u['cut_end']}s): {u.get('continuity_note','')}"
        for u in uses
    )
    instr = (
        "QA gate on a Veo-3 text-to-video prompt BEFORE it is sent to Veo. "
        "You are reviewing the PROMPT TEXT ONLY (no video exists yet). "
        f"Master clip: '{master['name']}'\n"
        f"Director brief: {master.get('brief','')}\n"
        f"Camera direction: {master.get('camera','')}\n"
        f"Cuts it serves: {use_summary}\n\n"
        "Checks (fail on any):\n"
        " (a) prompt does NOT mention the master's location/subject,\n"
        " (b) prompt is <60 or >220 words,\n"
        " (c) prompt describes humans/characters (player is layered separately),\n"
        " (d) prompt describes text/logos/subtitles,\n"
        " (e) prompt contradicts the camera direction,\n"
        " (f) prompt describes cartoon/illustration/anime style.\n"
        "Return STRICT JSON: {\"verdict\":\"pass|fail\",\"notes\":\"...\"}.\n\n"
        f"PROMPT:\n{prompt_text}"
    )
    resp = call_gemini(instr, "QA this Veo prompt.", max_tokens=350)
    return _parse_json(resp)


def _director_prompt_vote(engine, prompt_text, master, plan):
    """Single director vote on a Veo-3 prompt (text-only review)."""
    uses = [m for m in plan["mapping"] if m["master_clip"] == master["name"]]
    use_summary = "; ".join(
        f"{u['transition_id']} (cut {u['cut_start']}-{u['cut_end']}s): {u.get('continuity_note','')}"
        for u in uses
    )
    system = (
        "You are the Director of Studio Emerald, one of 3 independent directors "
        "reviewing a Veo-3 text-to-video prompt BEFORE it is sent to Veo. "
        "This pre-vet saves quota by catching weak prompts early.\n\n"
        f"Master clip: '{master['name']}'\n"
        f"Director brief (the intent): {master.get('brief','')}\n"
        f"Camera direction: {master.get('camera','')}\n"
        f"Cuts it must serve: {use_summary}\n\n"
        "Judge the prompt on cinematic/directorial merit:\n"
        " - Does it set location and mood clearly?\n"
        " - Does it describe specific camera motion matching the brief?\n"
        " - Does it create DENSITY so BOTH first 2s AND final 2s can stand alone as transitions?\n"
        " - Is it concrete (specific lighting, colors, textures) vs vague?\n"
        " - Does it avoid humans/characters/text/cartoon?\n\n"
        "Return STRICT JSON: {\"verdict\":\"pass|fix|redo\",\"notes\":\"one sentence why\"}.\n"
        "pass=send to Veo; fix=small tweak; redo=rewrite."
    )
    resp = call_engine(engine, system, f"PROMPT UNDER REVIEW:\n{prompt_text}", max_tokens=350)
    return _parse_json(resp)


def step2b_review_prompt(prompt_text, master, plan):
    """Run QA + 3-director panel on a prompt TEXT. Return {qa, panel, pass_count, unanimous}."""
    qa = _qa_prompt_review(prompt_text, master, plan)
    panel = {}
    for eng in ENGINES:
        try:
            panel[eng] = _director_prompt_vote(eng, prompt_text, master, plan)
        except Exception as e:
            panel[eng] = {"verdict": "redo", "notes": f"engine error: {e}"}
    pass_count = sum(1 for v in panel.values() if v.get("verdict") == "pass")
    return {
        "qa": qa,
        "panel": panel,
        "pass_count": pass_count,
        "unanimous": pass_count == 3 and qa.get("verdict") == "pass",
    }


def rewrite_prompt_with_feedback(master, plan, prev_prompt, review):
    """Second-pass prompt writer that ingests panel feedback."""
    objections = []
    if review["qa"].get("verdict") != "pass":
        objections.append(f"QA: {review['qa'].get('notes','')[:250]}")
    for eng, v in review["panel"].items():
        if v.get("verdict") != "pass":
            objections.append(f"{eng}: {v.get('notes','')[:250]}")
    feedback = " || ".join(objections) or "general tightening"

    uses = [m for m in plan["mapping"] if m["master_clip"] == master["name"]]
    use_summary = "; ".join(
        f"{u['transition_id']} ({u['cut_start']}-{u['cut_end']}s)" for u in uses
    )
    system = (
        "You are a Visual Prompt Writer. Rewrite an English Veo-3 text-to-video prompt "
        "(100-180 words) addressing the panel's objections. "
        "Rules: ~5s duration, 16:9, cinematic photorealistic, muted tropical saturation, "
        "ground-POV camera, NO humans/characters, NO text/logos. "
        "The clip will be trimmed into 2-second segments; first 2s AND final 2s must both "
        "look cinematic in isolation. Output: prompt text only, no preamble."
    )
    user = (
        f"{load_project_context()}\n\n"
        f"───── master clip spec ─────\n"
        f"name: {master['name']}\n"
        f"director brief: {master.get('brief','')}\n"
        f"camera direction: {master.get('camera','')}\n"
        f"cuts it serves: {use_summary}\n\n"
        f"───── previous prompt ─────\n{prev_prompt}\n\n"
        f"───── panel objections ─────\n{feedback}\n\n"
        "Rewrite the Veo-3 prompt now, addressing every objection."
    )
    return call_claude(system, user, max_tokens=700).strip()


# ───────── step 4: cut master into transitions ─────────
def step4_cut(master_path, start, end, out_path):
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-ss", str(start), "-i", str(master_path),
        "-t", str(end - start),
        "-c", "copy", str(out_path),
    ], check=True)


# ───────── step 5: keyframe grid per 2s cut ─────────
def step5_keyframes_grid(cut_path, slug):
    # 4 keyframes across the 2 seconds: t = 0.2, 0.8, 1.3, 1.8
    times = [0.2, 0.8, 1.3, 1.8]
    imgs = []
    for t in times:
        f = CANDIDATES_DIR / f"{slug}_kf_t{t}.png"
        subprocess.run([
            "ffmpeg", "-y", "-loglevel", "error", "-ss", str(t),
            "-i", str(cut_path), "-vframes", "1", "-q:v", "2", str(f)
        ], check=True)
        imgs.append(Image.open(f))
    w, h = imgs[0].size
    s = 640 / max(w, h)
    tw, th = int(w * s), int(h * s)
    imgs = [i.resize((tw, th)) for i in imgs]
    grid = Image.new("RGB", (tw * 2, th * 2))
    grid.paste(imgs[0], (0, 0)); grid.paste(imgs[1], (tw, 0))
    grid.paste(imgs[2], (0, th)); grid.paste(imgs[3], (tw, th))
    g = CANDIDATES_DIR / f"{slug}_grid.png"
    grid.save(g, "PNG")
    return g


# ───────── step 6+7: QA + 3-director panel (TRANSITION-SPECIFIC rubric) ─────────
# Critical distinction from scenery/poses:
#   - Scenery props are isolated PNG layers on neutral bg, composited via CSS.
#   - Transitions are FULL-SCREEN background VIDEOS that play as the bg layer itself.
# The old director_vote() from resolve_via_panel said "this is a compositor PNG,
# isolated layer"; Claude correctly applied that rubric and rejected full-scene
# videos. We replace both QA and director vote with transition-aware versions.

def _qa_check_transition(img_b64, transition):
    """QA gate for a transition VIDEO keyframe grid. Lenient on style/subject.

    Reviews a 2x2 grid of 4 keyframes sampled from the 2-second clip.
    The clip IS the scene (jungle, tunnel, temple…) — it fills the frame as the
    background layer. NO transparent/neutral bg expected. The player sprite and
    UI are composited on top by the Builder in CSS later.
    """
    instr = (
        f"QA sanity check for a TRANSITION VIDEO (2-second cinematic clip bridging "
        f"game missions). You are reviewing a 2x2 grid of 4 keyframes sampled from "
        f"the video.\n\n"
        f"Transition: {transition['id']} (after {transition['after']} -> before {transition['before']})\n"
        f"Intended subject/action: {transition['description']}\n\n"
        f"**ASSET TYPE**: FULL-SCREEN BACKGROUND VIDEO. The clip fills the entire "
        f"frame as the background layer of the composition. There is NO transparent "
        f"or neutral bg expected — the clip IS the scene itself (jungle, tunnel, "
        f"temple, cliff, etc.). The player sprite, UI, and any overlay elements are "
        f"composited on top by the Builder in CSS. Do NOT expect or demand subject "
        f"isolation on a clean bg.\n\n"
        f"Fail ONLY if: "
        f"(a) the subject/action is clearly wrong for the transition description, "
        f"(b) prominent text/logos/subtitles burned into the frame, "
        f"(c) cartoon/illustration/anime style (must be cinematic photorealistic), "
        f"(d) visible humans/characters (the player is composited separately).\n"
        f"Return STRICT JSON: {{\"verdict\":\"pass|fail\",\"notes\":\"...\"}}."
    )
    resp = call_gemini(instr, "Review this transition video keyframe grid.",
                       image_b64=img_b64, max_tokens=350)
    return _parse_json(resp)


def _director_vote_transition(engine, img_b64, transition, qa_verdict):
    """Single director-role vote on a TRANSITION VIDEO keyframe grid."""
    system = (
        f"You are the Director of Studio Emerald, ONE of THREE independent directors "
        f"reviewing a TRANSITION VIDEO CLIP for mission transition "
        f"{transition['after']}->{transition['before']}. The other two directors "
        f"(other AI engines) judge separately; your vote stands on its own.\n\n"
        f"Transition: {transition['id']}\n"
        f"Intended subject/action: {transition['description']}\n"
        f"QA pre-check verdict: {qa_verdict}\n\n"
        f"**ASSET TYPE — READ CAREFULLY**: this is a FULL-SCREEN BACKGROUND VIDEO. "
        f"A 2-second cinematic clip that plays as the background layer of the "
        f"composition between missions. It fills the entire frame. There is NO "
        f"transparent bg, NO neutral bg, NO isolated subject. The clip IS the scene "
        f"itself (jungle, tunnel, temple, etc.).\n"
        f"**DO NOT reject because the video is a 'full scene' rather than an "
        f"'isolated compositor prop' — that rule applies to PNG props only, NOT to "
        f"transition videos.** The player sprite, UI, and any overlay effects are "
        f"layered on top by the Builder in CSS code; they do NOT need to appear in "
        f"the video.\n\n"
        f"You are looking at a 2x2 grid of 4 keyframes from the 2-second clip.\n\n"
        f"Judge on:\n"
        f" - Does the video depict the intended narrative (right subject/action)?\n"
        f" - Does the camera motion suit the transition's momentum?\n"
        f" - Cinematic photorealistic tropical style — no cartoon, no text/logos?\n"
        f" - NO visible humans/characters in frame (player is composited separately)?\n"
        f" - Does it read as a coherent 2-second cinematic beat in isolation?\n"
        f"Be decisive: if the subject is correct and the style is right, PASS. Do not "
        f"nitpick compositing concerns — this is a bg video, not a prop layer.\n\n"
        f"Return STRICT JSON: {{\"verdict\":\"pass|fix|redo\",\"notes\":\"one sentence why\"}}. "
        f"pass=ship as-is; fix=tiny tweak would help; redo=wrong subject/concept."
    )
    resp = call_engine(engine, system, "Review this transition video keyframe grid.",
                       image_b64=img_b64, max_tokens=350)
    return _parse_json(resp)


def eval_panel(grid_path, transition, prompt):
    img_b64 = base64.b64encode(grid_path.read_bytes()).decode("ascii")
    qa = _qa_check_transition(img_b64, transition)
    panel = {}
    for eng in ENGINES:
        try:
            panel[eng] = _director_vote_transition(eng, img_b64, transition, qa.get("verdict"))
        except Exception as e:
            panel[eng] = {"verdict": "redo", "notes": f"engine error: {e}"}
    pass_count = sum(1 for v in panel.values() if v.get("verdict") == "pass")
    return {
        "qa": qa,
        "panel": panel,
        "pass_count": pass_count,
        "unanimous": pass_count == 3 and qa.get("verdict") == "pass",
    }


# ───────── orchestration ─────────
def process_master(master, plan, log, max_regen=3):
    """Generate master clip, cut, QA+panel each cut. Regen if any cut fails."""
    uses = [m for m in plan["mapping"] if m["master_clip"] == master["name"]]
    # Skip if all cuts already delivered
    if all(log.get(u["transition_id"], {}).get("status") == "delivered" for u in uses):
        print(f"[master:{master['name']}] all cuts delivered -- skip")
        return

    for regen in range(1, max_regen + 1):
        print(f"\n[master:{master['name']}] attempt {regen}")

        # ── STEP 2+2b: write prompt, then pre-vet via panel on TEXT (cheap) ──
        prompt = step2_write_prompt(master, plan)
        prompt_ok = False
        prompt_reviews = []
        for pv in range(1, 4):  # up to 3 rewrites before escalating
            review = step2b_review_prompt(prompt, master, plan)
            c = review["panel"]["claude"].get("verdict")
            g = review["panel"]["gemini"].get("verdict")
            o = review["panel"]["openai"].get("verdict")
            print(f"  [prompt v{pv}] qa={review['qa'].get('verdict')} "
                  f"claude={c} gemini={g} openai={o} "
                  f"{'** APPROVED **' if review['unanimous'] else ''}")
            prompt_reviews.append({"version": pv, "prompt": prompt, "review": review})
            if review["unanimous"]:
                prompt_ok = True
                break
            prompt = rewrite_prompt_with_feedback(master, plan, prompt, review)

        if not prompt_ok:
            print(f"  [prompt] 3 versions failed panel pre-vet — skipping Veo to save quota")
            # Save prompt history to log for debugging
            log[f"{master['name']}_prompt_history"] = prompt_reviews
            save_log(log)
            continue

        # Save approved prompt
        prompt_path = CANDIDATES_DIR / f"{master['name']}_prompt_r{regen}.txt"
        prompt_path.write_text(prompt, "utf-8")
        print(f"  prompt saved: {prompt_path.name} ({len(prompt)} chars)")

        # ── STEP 3: Veo (with KEY_B failover) ──
        try:
            mp4_bytes = step3_veo(prompt)
        except Exception as e:
            print(f"  Veo error: {e}")
            continue
        master_path = CANDIDATES_DIR / f"{master['name']}_master_r{regen}.mp4"
        master_path.write_bytes(mp4_bytes)
        print(f"  master saved: {master_path.name} ({len(mp4_bytes)//1024}KB)")

        # Cut and evaluate each use
        all_ok = True
        for u in uses:
            tid = u["transition_id"]
            entry = log.get(tid, {})
            if entry.get("status") == "delivered":
                continue
            cut_path = CANDIDATES_DIR / f"{tid}_r{regen}.mp4"
            try:
                step4_cut(master_path, u["cut_start"], u["cut_end"], cut_path)
                grid = step5_keyframes_grid(cut_path, f"{tid}_r{regen}")
            except Exception as e:
                print(f"  [{tid}] ffmpeg error: {e}")
                all_ok = False
                continue

            transition_meta = next(t for t in TRANSITIONS if t["id"] == tid)
            result = eval_panel(grid, transition_meta, prompt)
            c = result["panel"]["claude"].get("verdict")
            g = result["panel"]["gemini"].get("verdict")
            o = result["panel"]["openai"].get("verdict")
            print(f"  [{tid}] qa={result['qa'].get('verdict')} claude={c} gemini={g} openai={o} "
                  f"{'** UNANIMOUS **' if result['unanimous'] else ''}")

            if result["unanimous"]:
                final = TRANS_DIR / f"{tid}.mp4"
                final.write_bytes(cut_path.read_bytes())
                log[tid] = {
                    "id": tid,
                    "after": transition_meta["after"],
                    "before": transition_meta["before"],
                    "master_clip": master["name"],
                    "cut_range": [u["cut_start"], u["cut_end"]],
                    "status": "delivered",
                    "final_path": str(final),
                    "prompt": prompt,
                    "qa": result["qa"],
                    "panel": result["panel"],
                    "continuity_note": u.get("continuity_note", ""),
                    "resolved_at_master_attempt": regen,
                }
                save_log(log)
                print(f"  [{tid}] PROMOTED -> {final.name}")
            else:
                all_ok = False
                log[tid] = {
                    "id": tid,
                    "after": transition_meta["after"],
                    "before": transition_meta["before"],
                    "master_clip": master["name"],
                    "status": "pending",
                    "last_attempt_panel": result["panel"],
                    "last_attempt_qa": result["qa"],
                }
                save_log(log)
        if all_ok:
            return
    print(f"[master:{master['name']}] exhausted {max_regen} regenerations; "
          f"some cuts may remain pending")


# ───────── rescore mode: re-evaluate existing candidates with corrected rubric ─────────
def rescore_existing(plan, log):
    """Re-run panel on existing candidate videos without calling Veo.

    Used after a rubric change (e.g. when Claude was incorrectly applying the
    'compositor prop layer' rule to full-screen transition videos and auto-
    rejecting cinematically-correct clips). For each pending transition whose
    master clip already has at least one candidate .mp4 on disk, we re-cut
    (if needed), re-sample keyframes, and re-vote with the transition-specific
    rubric. Promotes on unanimous pass. Zero Veo calls.
    """
    print("\n=== RESCORE MODE: no Veo calls, panel re-eval on existing masters ===")
    rescued = 0
    for mc in plan["master_clips"]:
        uses = [m for m in plan["mapping"] if m["master_clip"] == mc["name"]]
        if all(log.get(u["transition_id"], {}).get("status") == "delivered" for u in uses):
            continue
        existing = sorted(CANDIDATES_DIR.glob(f"{mc['name']}_master_r*.mp4"))
        if not existing:
            print(f"[rescore:{mc['name']}] no candidate video on disk — skip (needs Veo)")
            continue
        master_path = existing[-1]  # latest attempt
        print(f"\n[rescore:{mc['name']}] using {master_path.name}")

        for u in uses:
            tid = u["transition_id"]
            if log.get(tid, {}).get("status") == "delivered":
                continue
            # Reuse an existing cut if available, otherwise cut fresh.
            existing_cuts = sorted(CANDIDATES_DIR.glob(f"{tid}_r*.mp4"))
            if existing_cuts:
                cut_path = existing_cuts[-1]
            else:
                cut_path = CANDIDATES_DIR / f"{tid}_rescore.mp4"
                try:
                    step4_cut(master_path, u["cut_start"], u["cut_end"], cut_path)
                except Exception as e:
                    print(f"  [{tid}] ffmpeg error: {e}")
                    continue
            try:
                grid = step5_keyframes_grid(cut_path, f"{tid}_rescore")
            except Exception as e:
                print(f"  [{tid}] keyframe error: {e}")
                continue

            transition_meta = next(t for t in TRANSITIONS if t["id"] == tid)
            result = eval_panel(grid, transition_meta, "")
            c = result["panel"]["claude"].get("verdict")
            g = result["panel"]["gemini"].get("verdict")
            o = result["panel"]["openai"].get("verdict")
            print(f"  [{tid}] qa={result['qa'].get('verdict')} "
                  f"claude={c} gemini={g} openai={o} "
                  f"{'** UNANIMOUS **' if result['unanimous'] else ''}")

            if result["unanimous"]:
                final = TRANS_DIR / f"{tid}.mp4"
                final.write_bytes(cut_path.read_bytes())
                log[tid] = {
                    "id": tid,
                    "after": transition_meta["after"],
                    "before": transition_meta["before"],
                    "master_clip": mc["name"],
                    "cut_range": [u["cut_start"], u["cut_end"]],
                    "status": "delivered",
                    "final_path": str(final),
                    "qa": result["qa"],
                    "panel": result["panel"],
                    "continuity_note": u.get("continuity_note", ""),
                    "resolved_via": "rescore_after_rubric_fix",
                    "rescored_from": master_path.name,
                }
                save_log(log)
                rescued += 1
                print(f"  [{tid}] PROMOTED -> {final.name}")
            else:
                log[tid] = {
                    "id": tid,
                    "after": transition_meta["after"],
                    "before": transition_meta["before"],
                    "master_clip": mc["name"],
                    "status": "pending",
                    "last_attempt_panel": result["panel"],
                    "last_attempt_qa": result["qa"],
                    "rescored_from": master_path.name,
                }
                save_log(log)
    print(f"\n=== RESCORE DONE: {rescued} transition(s) rescued without Veo ===")
    return rescued


def main():
    print("=== TRANSITIONS PIPELINE ===")
    t0 = time.time()
    log = load_log()

    # STEP 1: planning
    plan = step1_group_planning()
    print(f"\nPLAN SUMMARY:")
    for mc in plan["master_clips"]:
        uses = [m for m in plan["mapping"] if m["master_clip"] == mc["name"]]
        print(f"  {mc['name']}: {len(uses)} cut(s) — {', '.join(u['transition_id'] for u in uses)}")

    # RESCORE mode: re-eval existing candidates only, no Veo.
    if os.environ.get("RESCORE_ONLY", "").strip():
        rescore_existing(plan, log)
        delivered = sum(
            1 for v in log.values()
            if isinstance(v, dict) and v.get("status") == "delivered"
        )
        total = len(TRANSITIONS)
        print(f"\ndone in {int(time.time()-t0)}s. delivered: {delivered}/{total}")
        pending = [
            t["id"] for t in TRANSITIONS
            if not isinstance(log.get(t["id"]), dict)
            or log[t["id"]].get("status") != "delivered"
        ]
        if pending:
            print(f"pending: {pending}")
        return

    # STEPS 2-7: per master
    # Allow restricting to specific masters via env var (CSV of names)
    # to focus quota on un-started masters.
    only = os.environ.get("MASTER_ONLY", "").strip()
    only_set = {s.strip() for s in only.split(",") if s.strip()} if only else None
    for mc in plan["master_clips"]:
        if only_set and mc["name"] not in only_set:
            print(f"\n[master:{mc['name']}] skipped (not in MASTER_ONLY filter)")
            continue
        process_master(mc, plan, log)

    delivered = sum(
        1 for v in log.values()
        if isinstance(v, dict) and v.get("status") == "delivered"
    )
    total = len(TRANSITIONS)
    print(f"\ndone in {int(time.time()-t0)}s. delivered: {delivered}/{total}")
    pending = [
        t["id"] for t in TRANSITIONS
        if not isinstance(log.get(t["id"]), dict)
        or log[t["id"]].get("status") != "delivered"
    ]
    if pending:
        print(f"pending: {pending}")


if __name__ == "__main__":
    main()
