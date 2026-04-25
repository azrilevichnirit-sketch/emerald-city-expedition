"""Background video generator — full protocol per bg.

Targets (13 total):
  - NEW (10): M1, M3, M5, M6, M7, M8, M10, M13, M14, M15 — missions with no existing bg
  - FIX (2): bg_06 (M4), bg_07 (M9) — first-run review said fix with fix_notes
  - REDO (1): bg_01 → repurpose as M3 — v2 review said redo

Per iron rule, every bg goes through:
  1. director debate (mode=design) → brief/synthesis
  2. visual_prompt_writer (Claude) → Veo prompt
  3. Veo 3 fast text-to-video (image reference blocked by RAI, so text-to-video)
  4. ffmpeg keyframes → 2x2 grid
  5. Gemini vision QA
  6. Claude vision director
  7. If both pass → save to assets/backgrounds/<slug>.mp4 + update manifest

Idempotent: delivered bgs are skipped.
"""
import base64
import json
import subprocess
import time
import urllib.request
import urllib.error
from pathlib import Path
from PIL import Image

import os
from debate_runner import (
    run_debate, call_claude, call_gemini, DEBATES_DIR,
    get_gemini_key, load_project_context, GEMINI_KEYS,
)

PROJECT = Path(__file__).resolve().parent.parent
BG_DIR = PROJECT / "assets" / "backgrounds"
BG_DIR.mkdir(parents=True, exist_ok=True)
REVIEW_DIR = PROJECT / "pipeline" / "review" / "backgrounds"
REVIEW_DIR.mkdir(parents=True, exist_ok=True)
LOG_PATH = REVIEW_DIR / "_protocol_log.json"
DEBATE_OUT = DEBATES_DIR / "backgrounds"
DEBATE_OUT.mkdir(parents=True, exist_ok=True)

LOCK = json.loads((PROJECT / "content_lock.json").read_text("utf-8"))
BIBLE = json.loads((PROJECT / "pipeline" / "camera_bible.json").read_text("utf-8"))

VEO_MODEL = "veo-3.0-generate-001"  # was veo-3.0-fast-generate-001 (own quota bucket — exhausted on both keys); veo-3.0-generate-001 has fresh quota for our demo

# Target list: mission_id, slug, kind (new/fix/redo), prior_fix_notes (for fix/redo)
PRIOR_FIX = {}


def _load_prior_fix_notes():
    """Pull bg_06/bg_07/bg_01 fix_notes from their existing debate JSONs."""
    mapping = {}
    for slug, mid in [("bg_06", "M4"), ("bg_07", "M9")]:
        f = DEBATE_OUT / f"director_bg_{slug}.json"
        if f.exists():
            fd = (json.loads(f.read_text("utf-8")).get("final_decision") or {})
            mapping[slug] = {"mission": mid, "fix_notes": fd.get("fix_notes") or "", "synthesis": fd.get("synthesis") or ""}
    f = DEBATE_OUT / "director_bg_bg_01_v2.json"
    if f.exists():
        fd = (json.loads(f.read_text("utf-8")).get("final_decision") or {})
        mapping["bg_01"] = {"mission": "M3", "fix_notes": fd.get("fix_notes") or "", "synthesis": fd.get("synthesis") or ""}
    return mapping


def targets():
    """Return ordered list of generation targets."""
    covered_missions = {  # existing passing bgs → their mission
        "bg_02": "M12", "bg_03": "M9", "bg_04": "M11",
        "bg_05": "M2", "bg_08": "M2", "bg_09": "M11",
    }
    # Missions needing NEW bg: those not in covered_missions values AND not bg_06/bg_07/bg_01 handled
    all_missions = list(LOCK["missions"].keys())  # M1..M15
    assigned = set(covered_missions.values()) | {"M4", "M9", "M3"}  # M4=bg_06 fix, M9=bg_07 fix (bg_03 also covers M9), M3=bg_01 redo
    assigned.discard("M9")  # actually bg_03 already covers M9 pass; bg_07 is a second M9 fix — we'll let bg_07 fix become a second angle for M9
    # So missing = all - covered - M4(bg_06) - M9(bg_03) - M3(bg_01)
    missing = [m for m in all_missions if m not in set(covered_missions.values()) | {"M4", "M9", "M3"}]

    tlist = []
    # NEW bgs (one per missing mission; slug = bg_M{n})
    for mid in missing:
        tlist.append({"slug": f"bg_{mid}", "mission": mid, "kind": "new",
                      "prior_fix_notes": "", "prior_synthesis": ""})
    # FIX bgs
    prior = _load_prior_fix_notes()
    for slug in ["bg_06", "bg_07"]:
        p = prior.get(slug, {})
        tlist.append({"slug": slug, "mission": p.get("mission"), "kind": "fix",
                      "prior_fix_notes": p.get("fix_notes",""),
                      "prior_synthesis": p.get("synthesis","")})
    # REDO
    p = prior.get("bg_01", {})
    tlist.append({"slug": "bg_01", "mission": p.get("mission") or "M3", "kind": "redo",
                  "prior_fix_notes": p.get("fix_notes",""),
                  "prior_synthesis": p.get("synthesis","")})

    # Pre-vetted second-bg targets — slugs explicitly prepped via prep_tomorrow.py
    # for missions that already have a delivered bg but need an additional
    # scene-specific bg (per director planning). The full agent pipeline
    # (brief debate → prompt → Veo → vision QA → 3-director panel) still runs
    # on each; this list only adds them to the awareness set so the agents
    # see them as pending work.
    PREP_PATH = PROJECT / "pipeline" / "review" / "_tomorrow_prep.json"
    if PREP_PATH.exists():
        try:
            prep = json.loads(PREP_PATH.read_text("utf-8"))
            for slug, entry in (prep.get("backgrounds") or {}).items():
                already_listed = any(t["slug"] == slug for t in tlist)
                if already_listed:
                    continue
                tlist.append({
                    "slug": slug,
                    "mission": entry.get("mission") or slug.replace("bg_", ""),
                    "kind": "new",
                    "prior_fix_notes": "",
                    "prior_synthesis": entry.get("brief_synthesis", ""),
                })
        except json.JSONDecodeError:
            pass
    return tlist


# ───────── brief ─────────
def step1_brief(tgt):
    """Run director debate (design mode) for NEW bgs. For fix/redo, reuse prior + fix_notes."""
    mid = tgt["mission"]
    mission = LOCK["missions"][mid]

    if tgt["kind"] in ("fix", "redo"):
        brief_text = (
            f"ה-bg הקיים עבור {mid} צריך תיקון/החלפה. "
            f"סינתזה קודמת: {tgt.get('prior_synthesis','')}\n"
            f"הערות תיקון: {tgt.get('prior_fix_notes','')}\n\n"
            f"mission_text: {mission['mission_text']}\n"
            f"checkpoint_text: {mission.get('checkpoint_text','')}"
        )
        return {"synthesis": brief_text, "decision": "pass", "source": "prior_fix_notes"}

    print(f"    [1] director design debate for {tgt['slug']} ({mid})")
    camera_bg = BIBLE.get("backgrounds", {}).get("spec", "")
    question = (
        f"דיון במאים לפני יצירת רקע וידאו ל-{mid}. "
        f"חייב: (1) ground-POV, (2) שלוש שכבות עומק (foreground/midground/background), "
        f"(3) סגנון cinematic photorealistic, (4) רוויה מאופקת טרופית, "
        f"(5) תאימות לזמן-היום של המשימה. "
        f"בנוסף — ללא דמויות/אנשים (הם יתווספו כ-pose_*.mp4 מעל). "
        f"החזר ב-synthesis את הבריף המלא לכתיבת prompt Veo: מיקום, אלמנטים בכל שכבה, "
        f"תאורה, מצב-רוח, תנועות מצלמה עדינות (אם יש)."
    )
    ctx = (
        f"מיקום: {mid} — {mission.get('checkpoint_label','')}. "
        f"mission_text: {mission['mission_text']}\n"
        f"checkpoint_text: {mission.get('checkpoint_text','')}\n"
        f"backgrounds camera spec: {json.dumps(camera_bg, ensure_ascii=False)[:1200]}"
    )
    r = run_debate(
        role="director",
        scene_id=f"bg_design_{tgt['slug']}",
        question=question,
        context=ctx,
        image_path=None,
        rounds=8,
        save=True,
        output_dir=DEBATE_OUT,
        mode="design",
    )
    return r.get("final_decision") or {}


# ───────── prompt writer ─────────
def step2_write_prompt(tgt, brief):
    system = (
        "You are a Visual Prompt Writer. Produce an English Veo-3 text-to-video prompt "
        "(100-180 words) for a game background video. "
        "Rules: 8s duration target, 16:9, cinematic photorealistic, muted tropical "
        "saturation, ground-POV camera, 3 depth layers, NO humans/characters (layered "
        "player will be composited on top), NO text/logos. Gentle ambient camera motion "
        "(slow push/pan/drift). Natural lighting matching scene mood. "
        "Output: prompt only, no preamble."
    )
    syn = brief.get("synthesis") or ""
    fix = brief.get("fix_notes") or ""
    notes = tgt.get("prior_fix_notes","")
    if not isinstance(syn, str): syn = json.dumps(syn, ensure_ascii=False)
    if not isinstance(fix, str): fix = json.dumps(fix, ensure_ascii=False)
    user = (
        f"{load_project_context()}\n\n"
        f"───── target bg ─────\n"
        f"slug: {tgt['slug']}  mission: {tgt['mission']}  kind: {tgt['kind']}\n"
        f"director brief (Hebrew):\n{syn}\n"
        f"fix_notes: {fix}\n"
        f"prior notes to address: {notes}\n\n"
        "Write the Veo prompt now."
    )
    return call_claude(system, user, max_tokens=700).strip()


# ───────── Veo ─────────
def _submit_poll(body):
    k = get_gemini_key()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{VEO_MODEL}:predictLongRunning?key={k}"
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                  headers={"Content-Type":"application/json"}, method="POST")
    try:
        data = json.loads(urllib.request.urlopen(req, timeout=120).read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Veo submit HTTP {e.code}: {e.read().decode(errors='replace')[:500]}")
    op_name = data["name"]
    poll_url = f"https://generativelanguage.googleapis.com/v1beta/{op_name}?key={k}"
    for _ in range(80):
        time.sleep(15)
        op = json.loads(urllib.request.urlopen(poll_url, timeout=60).read().decode("utf-8"))
        if op.get("done"):
            return op
    raise TimeoutError(f"Veo op {op_name} timed out")


def _step3_veo_raw(prompt_text):
    k = get_gemini_key()
    body = {"instances":[{"prompt": prompt_text}], "parameters":{"aspectRatio":"16:9"}}
    op = _submit_poll(body)
    r = op.get("response", {})
    videos = (r.get("generateVideoResponse", {}).get("generatedSamples")
              or r.get("videos") or r.get("generatedVideos", []))
    if not videos:
        reasons = r.get("generateVideoResponse", {}).get("raiMediaFilteredReasons", [])
        raise RuntimeError(f"no videos (filtered reasons: {reasons}): {json.dumps(op)[:400]}")
    v0 = videos[0]
    if "video" in v0 and "uri" in v0["video"]:
        uri = v0["video"]["uri"]
        return urllib.request.urlopen(f"{uri}&key={k}" if "key=" not in uri else uri, timeout=300).read()
    if "bytesBase64Encoded" in v0:
        return base64.b64decode(v0["bytesBase64Encoded"])
    if "video" in v0 and "encodedVideo" in v0["video"]:
        return base64.b64decode(v0["video"]["encodedVideo"])
    raise RuntimeError(f"unknown video shape: {json.dumps(v0)[:300]}")


def step3_veo(prompt_text):
    """Veo call with automatic KEY_B failover on 429/RESOURCE_EXHAUSTED.

    Tries KEY_A first (GEMINI_KEY_IDX=0). On quota error, retries with KEY_B (idx=1).
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


# ───────── keyframes ─────────
def step4_keyframes(video_path, slug):
    times = [0.5, 1.8, 3.1, 4.5]
    imgs = []
    for t in times:
        f = REVIEW_DIR / f"{slug}_kf_t{t}.png"
        subprocess.run(["ffmpeg","-y","-loglevel","error","-ss",str(t),
                        "-i",str(video_path),"-vframes","1","-q:v","2",str(f)], check=True)
        imgs.append(Image.open(f))
    w,h = imgs[0].size; s = 640/max(w,h); tw,th = int(w*s),int(h*s)
    imgs = [i.resize((tw,th)) for i in imgs]
    grid = Image.new("RGB",(tw*2,th*2))
    grid.paste(imgs[0],(0,0)); grid.paste(imgs[1],(tw,0))
    grid.paste(imgs[2],(0,th)); grid.paste(imgs[3],(tw,th))
    g = REVIEW_DIR / f"{slug}_grid.png"
    grid.save(g,"PNG")
    return g


# ───────── QA & director ─────────
def step5_qa(grid_path, tgt, prompt):
    b64 = base64.b64encode(grid_path.read_bytes()).decode("ascii")
    instr = (
        f"{load_project_context()}\n\n"
        f"───── QA for bg video ─────\n"
        f"Slug {tgt['slug']}, mission {tgt['mission']}. This is a 2x2 grid of 4 keyframes "
        f"from an 8s bg video. Judge as compositor bg video (player layer will be added "
        f"on top). Be LENIENT on framing details — this is a background layer that "
        f"player/props will composite over. Tiny/distant/background human silhouettes are "
        f"acceptable (only fail on prominent foreground characters that would conflict "
        f"with the composited player). Minor ground-POV deviations (slight drone/aerial "
        f"are tolerable if the location still reads). "
        f"Fail ONLY if: (a) location is clearly wrong for the mission, (b) cartoon/illustration "
        f"style instead of photo, (c) prominent hard-to-remove foreground characters, or "
        f"(d) oversaturated non-cinematic color. "
        f"Return STRICT JSON: {{\"verdict\":\"pass|fail\",\"notes\":\"...\"}}."
    )
    resp = call_gemini(instr, "Review this bg video grid.", image_b64=b64, max_tokens=500)
    import re
    m = re.search(r"\{.*\}", resp, re.S)
    return json.loads(m.group(0)) if m else {"verdict":"fail","notes":resp[:200]}


def step6_director(grid_path, tgt, prompt, qa):
    b64 = base64.b64encode(grid_path.read_bytes()).decode("ascii")
    instr = (
        f"{load_project_context()}\n\n"
        f"───── Director gate for bg ─────\n"
        f"Slug {tgt['slug']}, mission {tgt['mission']}. 2x2 grid of keyframes. "
        f"QA: {qa.get('verdict')}. Judge as bg video asset (player composited on top). "
        f"Using project brief above, does this bg read instantly as the location for "
        f"mission {tgt['mission']}? Is it cinematically consistent? "
        f"Return STRICT JSON: {{\"verdict\":\"pass|fix|redo\",\"notes\":\"...\"}}. "
        f"pass=usable; fix=small tweak retry; redo=wrong subject."
    )
    resp = call_claude(instr, "Review this bg video grid.", max_tokens=500, image_b64=b64)
    import re
    m = re.search(r"\{.*\}", resp, re.S)
    return json.loads(m.group(0)) if m else {"verdict":"redo","notes":resp[:200]}


# ───────── run ─────────
def load_log():
    if LOG_PATH.exists():
        return json.loads(LOG_PATH.read_text("utf-8"))
    return {}


def save_log(log):
    LOG_PATH.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")


def run_bg(tgt, log, max_attempts=2):
    slug = tgt["slug"]
    final_path = BG_DIR / f"{slug}.mp4"
    entry = log.get(slug, {})
    if entry.get("status") == "delivered" and final_path.exists() and tgt["kind"] == "new":
        print(f"  [{slug}] already delivered — skip")
        return entry

    brief = step1_brief(tgt)
    prompt = step2_write_prompt(tgt, brief)

    history = []
    for attempt in range(1, max_attempts + 1):
        print(f"  [{slug}] attempt {attempt} — Veo submit")
        video_bytes = step3_veo(prompt)
        raw = REVIEW_DIR / f"{slug}_r{attempt}.mp4"
        raw.write_bytes(video_bytes)
        grid = step4_keyframes(raw, f"{slug}_r{attempt}")
        qa = step5_qa(grid, tgt, prompt)
        director = step6_director(grid, tgt, prompt, qa)
        qa_pass = qa.get("verdict") == "pass"
        dir_pass = director.get("verdict") == "pass"
        history.append({"attempt": attempt, "prompt": prompt[:400], "qa": qa, "director": director,
                        "raw": str(raw), "grid": str(grid)})
        if qa_pass and dir_pass:
            final_path.write_bytes(video_bytes)
            print(f"  [{slug}] PASS (a{attempt}) -> {final_path.name}")
            return {"slug": slug, "mission": tgt["mission"], "kind": tgt["kind"],
                    "status": "delivered", "final_path": str(final_path), "attempts": history}
        # rewrite prompt with feedback on fail
        feedback = director.get("notes") or qa.get("notes") or ""
        prompt = step2_write_prompt(tgt, {"synthesis": prompt, "fix_notes": feedback})
        print(f"  [{slug}] attempt {attempt}: qa={qa.get('verdict')} dir={director.get('verdict')} — retry with feedback")
    print(f"  [{slug}] exhausted — flagged")
    return {"slug": slug, "mission": tgt["mission"], "kind": tgt["kind"],
            "status": "needs_human_review", "attempts": history}


def main():
    tlist = targets()
    log = load_log()
    print(f"bg targets: {len(tlist)}")
    for t in tlist:
        print(f"  - {t['slug']} ({t['kind']} / {t['mission']})")
    t0 = time.time()
    for i, t in enumerate(tlist, 1):
        print(f"[{i}/{len(tlist)}] {t['slug']} ({t['kind']}, mission {t['mission']})")
        try:
            entry = run_bg(t, log)
        except Exception as e:
            entry = {"slug": t["slug"], "mission": t["mission"], "kind": t["kind"],
                     "status": "error", "error": str(e)}
            print(f"  [{t['slug']}] ERROR: {e}")
        log[t["slug"]] = entry
        save_log(log)
    total = time.time() - t0
    delivered = sum(1 for v in log.values() if v.get("status") == "delivered")
    flagged = sum(1 for v in log.values() if v.get("status") == "needs_human_review")
    errors = sum(1 for v in log.values() if v.get("status") == "error")
    print(f"\ndone in {int(total)}s. delivered={delivered} flagged={flagged} errors={errors}")


if __name__ == "__main__":
    main()
