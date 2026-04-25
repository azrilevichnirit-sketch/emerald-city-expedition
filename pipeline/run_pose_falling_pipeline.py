"""Full pipeline for pose_07.mp4 / anim_falling — Phase 0C completion.

Stages (per protocol):
  1. actor_director debate (design mode) — validate brief from camera_bible matches
     narrative needs of M1 (parachute opening) and M11 (cliff jump into water).
  2. visual_prompt_writer — produce Veo video prompt per debate synthesis.
  3. Veo 3 fast — image-to-video with master_player image as character reference.
  4. ffmpeg — extract 4 keyframes for QA.
  5. QA (Gemini vision on keyframe grid) — does it show falling? character match?
     no background elements? green screen?
  6. Director review (Claude vision) — final gate.
  7. If both pass — move to assets/player/pose_07.mp4 + update pose_map.json.

Per Nirit 2026-04-21: only the final polished pose_07 reaches her.
"""
import base64
import json
import subprocess
import time
import urllib.request
import urllib.error
from pathlib import Path
from PIL import Image

from debate_runner import (
    run_debate, call_claude, call_gemini, DEBATES_DIR, GEMINI_KEY,
)

PROJECT = Path(__file__).resolve().parent.parent
MASTER_IMG = PROJECT / "master_player" / (
    "niritazr_female_tropical_expedition_researcher_age_30_athleti_"
    "d44318aa-1ac0-43df-aa05-4411aaa85c98_0.png"
)
BIBLE = json.loads((PROJECT / "pipeline" / "camera_bible.json").read_text("utf-8"))
ANIM_BRIEF = BIBLE["player_animations"]["missing_anims"]["anim_falling"]
REVIEW_DIR = PROJECT / "pipeline" / "review" / "pose_falling"
QA_DIR = REVIEW_DIR
DEBATE_OUT = DEBATES_DIR / "pose_falling"
FINAL_POSE = PROJECT / "assets" / "player" / "pose_07.mp4"

VEO_MODEL = "veo-3.0-fast-generate-001"


# ───────── step 1 ─────────
def step1_debate():
    print("[1/7] actor_director debate on anim_falling brief")
    question = (
        "דיון actor_director לפני יצירת pose_07.mp4 (anim_falling). "
        "ה-brief מה-camera_bible הוא: " + json.dumps(ANIM_BRIEF, ensure_ascii=False) + ". "
        "1) האם ה-brief משרת נכונה את M1 (קפיצה מהמטוס) וגם M11 (קפיצה מעל מפל)? "
        "2) האם ה-hold_frame לתפיסת כלי (yad neta'it) עובד גם לתיק של M1 (deploy מצנח/גלשן/כנפיים) וגם למ-M11 (deploy בנג'י/סנפלינג/מצנח-בסיס)? "
        "3) האם צריך לתקן את ה-brief (fix_notes) לפני שנעביר ל-Visual Prompt Writer ול-Veo? "
        "חובה: אותו green screen #00B140, אותה חוקרת (master_player), 8s, 720p+, אין רקע, אין צעקה רמה. "
        "synthesis יכיל את ה-brief המעודכן במלואו, לשימוש הישיר של visual_prompt_writer."
    )
    ctx = (
        "pose_07.mp4 דרוש בדחיפות — חוסם את M1 ו-M11. "
        "הוא יוחלף/יושלם בסדר של הרצת הסרטון (8s) או one_shot עם hold_frame. "
        "בחרנו Veo 3 fast (image-to-video עם master_player לעקביות). "
        "הדיון רק על נכונות ה-brief — לא על המודל."
    )
    r = run_debate(
        role="actor_director",
        scene_id="pose_07_anim_falling",
        question=question,
        context=ctx,
        image_path=None,
        rounds=8,
        save=True,
        output_dir=DEBATE_OUT,
        mode="design",
    )
    return r["final_decision"]


# ───────── step 2 ─────────
def step2_write_prompt(brief_synthesis):
    print("[2/7] visual_prompt_writer → Veo prompt")
    system = (
        "אתה Visual Prompt Writer. המשימה: לנסח prompt באנגלית ל-Veo 3 image-to-video "
        "(image-to-video — הדמות תישלח כתמונת ייחוס). "
        "8 שניות, 1:1 or 16:9, green screen #00B140 בלבד, אין רקע. "
        "הדמות: חוקרת 30 אתלטית, שיער כהה בקוקו, חולצת יין כהה, מכנסי חאקי אפורים, תיק גב חאקי. "
        "תנועה: נפילה חופשית, גוף אלכסוני-אופקי, X-position, שיער ובגדים מתנפנפים כלפי מעלה (רוח חזקה), "
        "הבעה של ריכוז אדרנלין. "
        "לא להוסיף עננים/מטוס/אפקטים חיצוניים — Builder יוסיף רקע. "
        "פלט: prompt באנגלית בלבד, 120-200 מילים, אין טקסט מסביב, אין JSON."
    )
    user = (
        "ה-brief המאושר מ-actor_director:\n\n" + (brief_synthesis or "") +
        "\n\nנסח את ה-Veo prompt עכשיו."
    )
    prompt = call_claude(system, user, max_tokens=700)
    return prompt.strip()


# ───────── step 3 ─────────
def _submit_and_poll(body):
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{VEO_MODEL}:predictLongRunning?key={GEMINI_KEY}"
    )
    req = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Veo submit HTTP {e.code}: {err_body[:800]}") from None
    op_name = data["name"]
    print(f"    operation: {op_name}")
    poll_url = f"https://generativelanguage.googleapis.com/v1beta/{op_name}?key={GEMINI_KEY}"
    for i in range(60):
        time.sleep(15)
        op = json.loads(urllib.request.urlopen(poll_url, timeout=60).read().decode("utf-8"))
        if op.get("done"):
            return op
        print(f"    poll {i+1}/60 — still running")
    raise TimeoutError("Veo operation did not finish within 15 min")


def step3_veo_generate(prompt_text):
    print(f"[3/7] Veo {VEO_MODEL} — submitting image-to-video")
    img_b64 = base64.b64encode(MASTER_IMG.read_bytes()).decode("ascii")
    body_img = {
        "instances": [{
            "prompt": prompt_text,
            "image": {"bytesBase64Encoded": img_b64, "mimeType": "image/png"},
        }],
        "parameters": {"aspectRatio": "16:9", "personGeneration": "allow_adult"},
    }
    op = _submit_and_poll(body_img)
    resp_body = op.get("response", {})
    filtered = resp_body.get("generateVideoResponse", {}).get("raiMediaFilteredCount", 0)
    videos = (
        resp_body.get("generateVideoResponse", {}).get("generatedSamples")
        or resp_body.get("videos")
        or resp_body.get("generatedVideos", [])
    )
    if not videos and filtered:
        reasons = resp_body.get("generateVideoResponse", {}).get("raiMediaFilteredReasons", [])
        print(f"    image-to-video blocked by RAI ({reasons}); falling back to text-to-video")
        body_txt = {
            "instances": [{"prompt": prompt_text}],
            "parameters": {"aspectRatio": "16:9"},
        }
        op = _submit_and_poll(body_txt)
        resp_body = op.get("response", {})
        videos = (
            resp_body.get("generateVideoResponse", {}).get("generatedSamples")
            or resp_body.get("videos")
            or resp_body.get("generatedVideos", [])
        )
    if not videos:
        raise RuntimeError(f"no videos in response: {json.dumps(op)[:500]}")
    v0 = videos[0]
    # Try common shapes
    vid_bytes = None
    if "video" in v0 and "uri" in v0["video"]:
        uri = v0["video"]["uri"]
        vid_bytes = urllib.request.urlopen(
            f"{uri}&key={GEMINI_KEY}" if "key=" not in uri else uri, timeout=300
        ).read()
    elif "bytesBase64Encoded" in v0:
        vid_bytes = base64.b64decode(v0["bytesBase64Encoded"])
    elif "video" in v0 and "encodedVideo" in v0["video"]:
        vid_bytes = base64.b64decode(v0["video"]["encodedVideo"])
    else:
        raise RuntimeError(f"unknown video shape: {json.dumps(v0)[:400]}")
    out = REVIEW_DIR / "pose_07_rA_raw.mp4"
    out.write_bytes(vid_bytes)
    print(f"    wrote: {out} ({len(vid_bytes)} bytes)")
    return out


# ───────── step 4 ─────────
def step4_keyframes(video_path):
    print("[4/7] ffmpeg keyframes for QA")
    times = [0.5, 2.0, 4.0, 6.0]
    imgs = []
    for t in times:
        f = REVIEW_DIR / f"pose_07_kf_t{t}.png"
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-ss", str(t),
             "-i", str(video_path), "-vframes", "1", "-q:v", "2", str(f)],
            check=True,
        )
        imgs.append(Image.open(f))
    w, h = imgs[0].size
    s = 640 / max(w, h)
    tw, th = int(w * s), int(h * s)
    imgs = [i.resize((tw, th)) for i in imgs]
    grid = Image.new("RGB", (tw * 2, th * 2))
    grid.paste(imgs[0], (0, 0)); grid.paste(imgs[1], (tw, 0))
    grid.paste(imgs[2], (0, th)); grid.paste(imgs[3], (tw, th))
    g = REVIEW_DIR / "pose_07_kf_grid.png"
    grid.save(g)
    return g


# ───────── step 5 ─────────
def step5_qa(grid_path, prompt_text):
    print("[5/7] Gemini vision QA")
    system = (
        "אתה QA של תנועות שחקן. בדוק את ה-grid (4 keyframes מ-pose_07.mp4). "
        "החזר JSON בלבד: {\"match_brief\": bool, \"character_consistent\": bool, "
        "\"green_screen_pure\": bool, \"shows_falling\": bool, \"wind_effect_visible\": bool, "
        "\"notes\": \"...\", \"verdict\": \"pass|fail\"}."
    )
    user = (
        f"ה-prompt של הגנרטור:\n{prompt_text[:1000]}\n\n"
        "שפוט לפי הפריימים."
    )
    img_b64 = base64.b64encode(Path(grid_path).read_bytes()).decode("ascii")
    raw = call_gemini(system, user, image_b64=img_b64, max_tokens=800)
    (QA_DIR / "pose_07_qa.json").write_text(raw, encoding="utf-8")
    try:
        import re
        m = re.search(r"\{.*\}", raw, re.S)
        return json.loads(m.group(0) if m else raw)
    except Exception:
        return {"verdict": "fail", "raw": raw[:500]}


# ───────── step 6 ─────────
def step6_director(grid_path, qa, prompt_text):
    print("[6/7] Claude vision director review")
    system = (
        "אתה Director בסוף pipeline של תנועת שחקן. "
        "החזר JSON בלבד: {\"verdict\": \"pass|fail\", \"reason\": \"...\", "
        "\"narrative_fit_M1\": \"...\", \"narrative_fit_M11\": \"...\", "
        "\"character_consistent\": bool, \"technical_quality\": \"...\", "
        "\"notes\": \"...\"}."
    )
    user = (
        f"prompt שהופעל: {prompt_text[:800]}\n\n"
        f"QA verdict: {json.dumps(qa, ensure_ascii=False)[:800]}\n\n"
        "שפוט את ה-4 keyframes — הכל עובר? אם לא — מה חסר?"
    )
    img_b64 = base64.b64encode(Path(grid_path).read_bytes()).decode("ascii")
    raw = call_claude(system, user, image_b64=img_b64, max_tokens=1200)
    (REVIEW_DIR / "pose_07_director.json").write_text(raw, encoding="utf-8")
    try:
        import re
        m = re.search(r"\{.*\}", raw, re.S)
        return json.loads(m.group(0) if m else raw)
    except Exception:
        return {"verdict": "fail", "raw": raw[:500]}


# ───────── step 7 ─────────
def step7_finalize(video_path, qa, director, prompt_text):
    print("[7/7] finalize")
    qa_ok = qa.get("verdict") == "pass"
    dir_ok = director.get("verdict") == "pass"
    result = {
        "qa": qa, "director": director,
        "prompt": prompt_text[:500],
        "qa_pass": qa_ok, "director_pass": dir_ok,
        "delivered": False,
    }
    if qa_ok and dir_ok:
        FINAL_POSE.write_bytes(Path(video_path).read_bytes())
        result["delivered"] = True
        result["final_path"] = str(FINAL_POSE)
        # update pose_map.json
        pmap = json.loads((PROJECT / "pipeline" / "pose_map.json").read_text("utf-8"))
        pmap["poses"]["pose_07.mp4"] = {
            "semantic_name": "anim_falling",
            "confidence": "high",
            "evidence": "Veo-generated per camera_bible brief, QA+director passed",
            "duration_sec": 8.0,
            "loop_segment": None,
            "hold_frame": 0.5,
            "one_shot": True,
            "catch_pose": False,
            "catch_note": "hold 0.5s as M1/M11 deploy candidate",
            "use_in": ["M1", "M11"],
        }
        pmap["_missing_anims"] = []
        pmap["_delivered_at"] = "2026-04-21"
        (PROJECT / "pipeline" / "pose_map.json").write_text(
            json.dumps(pmap, ensure_ascii=False, indent=2), encoding="utf-8",
        )
    (REVIEW_DIR / "pose_07_summary.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def main():
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    DEBATE_OUT.mkdir(parents=True, exist_ok=True)
    cached = DEBATE_OUT / "actor_director_pose_07_anim_falling.json"
    if cached.exists():
        print("[1/7] reusing cached actor_director debate")
        debate_final = json.loads(cached.read_text(encoding="utf-8")).get("final_decision") or {}
    else:
        debate_final = step1_debate()
    syn = debate_final.get("synthesis") or ""
    notes = debate_final.get("fix_notes") or ""
    if isinstance(syn, (list, dict)):
        syn = json.dumps(syn, ensure_ascii=False)
    if isinstance(notes, (list, dict)):
        notes = json.dumps(notes, ensure_ascii=False)
    brief = syn + "\n\n" + notes
    prompt_text = step2_write_prompt(brief)
    print(f"    prompt length: {len(prompt_text)} chars")
    (REVIEW_DIR / "pose_07_prompt.txt").write_text(prompt_text, encoding="utf-8")
    video = step3_veo_generate(prompt_text)
    grid = step4_keyframes(video)
    qa = step5_qa(grid, prompt_text)
    director = step6_director(grid, qa, prompt_text)
    step7_finalize(video, qa, director, prompt_text)


if __name__ == "__main__":
    main()
