"""Scenery enumeration debate — per-mission 'what props go on the background?'

Role: set_manager (gemini-lead / claude-challenge / openai-mod).
Mode: design (no image — this is pre-generation brief work).

For each of 15 missions, the voices look at mission_text (narrative cue for what's
in the location) + checkpoint_text (what's seen next) + bg camera spec + what
already exists in assets/scenery/ (currently nothing), and propose the prop list
with CSS zones per set_manager.md spec.

Output per mission: pipeline/debates/scenery/set_manager_scenery_M{n}.json
Output summary:     pipeline/debates/scenery/_scenery_plan.json  (merged list)
"""
import json
import time
from pathlib import Path
from debate_runner import run_debate, DEBATES_DIR

PROJECT = Path(__file__).resolve().parent.parent
LOCK_PATH = PROJECT / "content_lock.json"
OUT_DIR = DEBATES_DIR / "scenery"
OUT_DIR.mkdir(parents=True, exist_ok=True)


QUESTION = (
    "דיון מנהל-סט (set_manager) בשלב design: "
    "אילו אביזרים (props / scenery) **על הרקע** דרושים לסצנה הזו כדי שהיא תעבוד ויזואלית "
    "וקריינית כפי ש-mission_text מתאר? (לדוגמה: גשר חבלים, מזבח אבן, לוח מקשים, ג'יפ מעשן, "
    "מכשיר קשר, דגלים של מתחרים, עקבות צמיגים וכו' — כל מה שמופיע בטקסט או נדרש ויזואלית "
    "כדי להבין את הסיטואציה.) "
    "לכל prop קבע: (1) שם הקובץ המוצע תחת assets/scenery/<name>.png, (2) CSS zone מדויק לפי "
    "design_system (bottom/left/width/z-index), (3) האם קיים כבר באסט מנפסט או צריך ליצור. "
    "אסור להמציא props שלא קשורים למשימה. אסור להציע כלים מ-content_lock (אלה כלי-יד, לא scenery). "
    "החזר ב-synthesis את הרשימה בצורה מסודרת, ב-fix_notes הסבר כל בחירה במשפט. "
    "decision=pass כשהרשימה מלאה ומתאימה; fix כשחסר משהו חיוני; redo אם הסצנה לא מובנת."
)


def run_mission(mission_id, mission, lock):
    t0 = time.time()
    ctx = (
        f"משימה {mission_id}.\n"
        f"mission_text (verbatim): {mission['mission_text']}\n"
        f"checkpoint_text (רגע אחרי): {mission.get('checkpoint_text','')}\n"
        f"checkpoint_label: {mission.get('checkpoint_label','')}\n"
        f"כלי-יד של הסצנה (לא scenery — רק קונטקסט): "
        f"{', '.join(t['label'] for t in mission['tools'])}.\n"
        f"מצב assets/scenery/ כרגע: ריק. כל prop שדרוש — צריך ליצור.\n"
        f"design_system zones: 'bottom:X%; left:Y%; width:Z%; z-index:N' — "
        f"z-index:1=שמיים/רחוק, 2=קרקע-רחוקה, 3=mid-ground, 4=foreground."
    )
    result = run_debate(
        role="set_manager",
        scene_id=f"scenery_{mission_id}",
        question=QUESTION,
        context=ctx,
        image_path=None,
        rounds=8,
        save=True,
        output_dir=OUT_DIR,
        mode="design",
    )
    elapsed = time.time() - t0
    final = result.get("final_decision", {})
    print(f"  [{mission_id}] decision={final.get('decision')} flag={final.get('director_flag')} "
          f"({elapsed:.0f}s)")
    return result


def main():
    lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    missions = lock["missions"]
    print(f"scenery enumeration debate on {len(missions)} missions")
    plan = {}
    t_start = time.time()
    for mid, m in missions.items():
        try:
            r = run_mission(mid, m, lock)
            final = r.get("final_decision", {})
            plan[mid] = {
                "decision": final.get("decision"),
                "director_flag": final.get("director_flag"),
                "synthesis": final.get("synthesis", ""),
                "fix_notes": final.get("fix_notes", ""),
            }
        except Exception as e:
            print(f"  [{mid}] ERROR: {e}")
            plan[mid] = {"error": str(e)}
    total = time.time() - t_start
    out = OUT_DIR / "_scenery_plan.json"
    out.write_text(
        json.dumps({"total_sec": int(total), "plan_by_mission": plan},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"done. total={int(total)}s. plan saved: {out}")


if __name__ == "__main__":
    main()
