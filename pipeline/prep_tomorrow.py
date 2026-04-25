"""Prepare tomorrow's 6 Veo items — briefs + prompts + pre-vet, no Veo calls.

When tomorrow's Veo quota resets we fire the Veo step only; everything below
the Veo line is already locked in today.

Items:
  3 transitions: T_M7 (rock_climb_prep), T_M13 + T_M14 (temple_hall_sprint)
  3 backgrounds: bg_M9, bg_M11, bg_M12

Output: pipeline/review/_tomorrow_prep.json with per-item prompt + pre-vet.
"""
import sys
import json
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "pipeline"))

from generate_transitions import (
    step2_write_prompt as trans_write_prompt,
    step2b_review_prompt as trans_prevet,
    rewrite_prompt_with_feedback as trans_rewrite,
    PLAN_PATH as TRANS_PLAN_PATH,
)
from generate_backgrounds import (
    step1_brief as bg_brief,
    step2_write_prompt as bg_write_prompt,
)
from debate_runner import call_engine, call_gemini
from resolve_via_panel import _parse_json, ENGINES

OUT_PATH = PROJECT / "pipeline" / "review" / "_tomorrow_prep.json"
LOCK = json.loads((PROJECT / "content_lock.json").read_text("utf-8"))

# ---------- bg-specific pre-vet (parallel to trans_prevet) ----------
def _bg_qa_prompt(prompt_text, slug, mission_id):
    m = LOCK["missions"][mission_id]
    instr = (
        "QA gate on a Veo-3 text-to-video prompt BEFORE it is sent to Veo. "
        "This is for a BACKGROUND video (long ambient loop, player layer on top).\n"
        f"Slug: {slug}  Mission: {mission_id}\n"
        f"Mission text: {m['mission_text']}\n\n"
        "Fail on any of:\n"
        " (a) prompt does NOT describe the mission's location/mood,\n"
        " (b) prompt <60 or >200 words,\n"
        " (c) prompt describes prominent humans/characters,\n"
        " (d) prompt describes text/logos/subtitles,\n"
        " (e) prompt describes cartoon/illustration/anime style.\n"
        'Return STRICT JSON: {"verdict":"pass|fail","notes":"..."}.\n\n'
        f"PROMPT:\n{prompt_text}"
    )
    resp = call_gemini(instr, "QA this Veo bg prompt.", max_tokens=350)
    return _parse_json(resp)


def _bg_director_prompt_vote(engine, prompt_text, slug, mission_id):
    m = LOCK["missions"][mission_id]
    system = (
        "You are the Director of Studio Emerald, one of 3 independent directors "
        "reviewing a Veo-3 text-to-video prompt BEFORE sending. This pre-vet saves quota.\n\n"
        f"Slug: {slug}  Mission: {mission_id}\n"
        f"Mission text: {m['mission_text']}\n"
        f"Checkpoint: {m.get('checkpoint_text','')}\n\n"
        "Judge the prompt on:\n"
        " - Does it set the mission's location and mood clearly?\n"
        " - Is it concrete (specific lighting, colors, textures)?\n"
        " - 3-layer depth (foreground/midground/background)?\n"
        " - Ground-POV camera angle?\n"
        " - Gentle ambient motion (this is a long loop)?\n"
        " - No humans, no text, no cartoon?\n\n"
        'Return STRICT JSON: {"verdict":"pass|fix|redo","notes":"one sentence"}.\n'
        "pass=send to Veo; fix=small tweak; redo=rewrite."
    )
    resp = call_engine(engine, system, f"PROMPT UNDER REVIEW:\n{prompt_text}", max_tokens=350)
    return _parse_json(resp)


def bg_prevet(prompt_text, slug, mission_id):
    qa = _bg_qa_prompt(prompt_text, slug, mission_id)
    panel = {}
    for eng in ENGINES:
        try:
            panel[eng] = _bg_director_prompt_vote(eng, prompt_text, slug, mission_id)
        except Exception as e:
            panel[eng] = {"verdict": "redo", "notes": f"engine error: {e}"}
    pass_count = sum(1 for v in panel.values() if v.get("verdict") == "pass")
    return {
        "qa": qa,
        "panel": panel,
        "pass_count": pass_count,
        "unanimous": pass_count == 3 and qa.get("verdict") == "pass",
    }


def bg_rewrite(slug, mission_id, prev_prompt, review):
    objections = [
        f"{eng}: {v.get('notes','')}"
        for eng, v in review["panel"].items()
        if v.get("verdict") != "pass"
    ]
    if review.get("qa", {}).get("verdict") == "fail":
        objections.insert(0, f"QA: {review['qa'].get('notes','')}")
    feedback = "\n".join(objections)
    tgt = {"slug": slug, "mission": mission_id, "kind": "new"}
    brief = {"synthesis": prev_prompt, "fix_notes": feedback}
    return bg_write_prompt(tgt, brief).strip()


# ---------- orchestration ----------
def prep_transitions(out):
    plan = json.loads(TRANS_PLAN_PATH.read_text("utf-8"))
    # T_M7 needs rock_climb_prep; T_M13/T_M14 both need temple_hall_sprint.
    # So we only pre-vet 2 masters.
    masters_needed = ["rock_climb_prep", "temple_hall_sprint"]
    for name in masters_needed:
        print(f"\n[transition master: {name}]")
        master = next(m for m in plan["master_clips"] if m["name"] == name)
        prompt = trans_write_prompt(master, plan)
        reviews = []
        for attempt in range(1, 4):
            r = trans_prevet(prompt, master, plan)
            c = r["panel"]["claude"].get("verdict")
            g = r["panel"]["gemini"].get("verdict")
            o = r["panel"]["openai"].get("verdict")
            print(f"  pre-vet a{attempt}: qa={r['qa'].get('verdict')} "
                  f"claude={c} gemini={g} openai={o}"
                  f"{'  ** UNANIMOUS **' if r['unanimous'] else ''}")
            reviews.append({"attempt": attempt, "prompt": prompt, "review": r})
            if r["unanimous"]:
                break
            prompt = trans_rewrite(master, plan, prompt, r)
        out["transitions"][name] = {
            "final_prompt": prompt,
            "unanimous": r["unanimous"],
            "reviews": reviews,
        }
        # incremental save
        OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), "utf-8")


def prep_backgrounds(out):
    for mid in ["M9", "M11", "M12"]:
        slug = f"bg_{mid}"
        print(f"\n[bg: {slug} for {mid}]")
        tgt = {"slug": slug, "mission": mid, "kind": "new",
               "prior_fix_notes": "", "prior_synthesis": ""}
        brief = bg_brief(tgt)
        print(f"  brief synthesized.")
        prompt = bg_write_prompt(tgt, brief)
        reviews = []
        for attempt in range(1, 4):
            r = bg_prevet(prompt, slug, mid)
            c = r["panel"]["claude"].get("verdict")
            g = r["panel"]["gemini"].get("verdict")
            o = r["panel"]["openai"].get("verdict")
            print(f"  pre-vet a{attempt}: qa={r['qa'].get('verdict')} "
                  f"claude={c} gemini={g} openai={o}"
                  f"{'  ** UNANIMOUS **' if r['unanimous'] else ''}")
            reviews.append({"attempt": attempt, "prompt": prompt, "review": r})
            if r["unanimous"]:
                break
            prompt = bg_rewrite(slug, mid, prompt, r)
        out["backgrounds"][slug] = {
            "mission": mid,
            "brief_synthesis": brief.get("synthesis", ""),
            "final_prompt": prompt,
            "unanimous": r["unanimous"],
            "reviews": reviews,
        }
        OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), "utf-8")


def main():
    out = {"transitions": {}, "backgrounds": {}}
    if OUT_PATH.exists():
        try:
            out = json.loads(OUT_PATH.read_text("utf-8"))
            print(f"[resume] loaded prior prep: "
                  f"{len(out.get('transitions',{}))} trans + "
                  f"{len(out.get('backgrounds',{}))} bgs")
        except Exception:
            pass
        out.setdefault("transitions", {})
        out.setdefault("backgrounds", {})

    print("=" * 60)
    print("TRANSITIONS")
    print("=" * 60)
    prep_transitions(out)

    print("\n" + "=" * 60)
    print("BACKGROUNDS")
    print("=" * 60)
    prep_backgrounds(out)

    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), "utf-8")
    print(f"\n=== PREP DONE -> {OUT_PATH.name} ===")
    print("SUMMARY:")
    for name, d in out["transitions"].items():
        status = "UNANIMOUS" if d.get("unanimous") else "NEEDS REVIEW"
        print(f"  transition/{name}: {status}")
    for slug, d in out["backgrounds"].items():
        status = "UNANIMOUS" if d.get("unanimous") else "NEEDS REVIEW"
        print(f"  bg/{slug}: {status}")


if __name__ == "__main__":
    main()
