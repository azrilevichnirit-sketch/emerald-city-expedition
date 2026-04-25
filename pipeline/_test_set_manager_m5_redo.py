"""Live test: re-run set_manager design debate for M5 with new Q1/Q2/Q3 logic.
2 rounds to limit API cost. Saves to pipeline/debates/scenery/_TEST_set_manager_scenery_M5.json.
"""
import sys
import json
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "pipeline"))

from debate_runner import run_debate, DEBATES_DIR

LOCK = json.loads((PROJECT / "content_lock.json").read_text(encoding="utf-8"))
m = LOCK["missions"]["M5"]

question = (
    "דיון מנהל-סט (set_manager) בשלב design: אילו אביזרים (props / scenery) על הרקע "
    "דרושים לסצנה הזו? עבור על כל אלמנט שמופיע ב-mission_text, סווג אותו לפי Q1/Q2/Q3 "
    "(covered_by_bg / covered_by_sound / reuse / CREATE), ונמק. ה-bg של M5 "
    "(bg_M5.mp4) הוא ג'ונגל סבוך — לקח את זה בחשבון ב-Q1."
)
context = (
    f"משימה M5.\n"
    f"mission_text (verbatim): {m['mission_text']}\n"
    f"checkpoint_text: {m.get('checkpoint_text','')}\n"
    f"checkpoint_label: {m.get('checkpoint_label','')}\n"
    f"כלי-יד (לא scenery — רק קונטקסט): {' / '.join(t['label'] for t in m.get('tools', []))}\n"
    f"design_system zones: 'bottom:X%; left:Y%; width:Z%; z-index:N' — "
    f"z-index:1=שמיים/רחוק, 2=קרקע-רחוקה, 3=mid-ground, 4=foreground."
)

OUT_DIR = DEBATES_DIR / "scenery"
OUT_DIR.mkdir(parents=True, exist_ok=True)

print("=" * 60)
print("TEST: set_manager design M5 with new Q1/Q2/Q3 logic (2 rounds)")
print("=" * 60)

result = run_debate(
    role="set_manager",
    scene_id="_TEST_M5_with_3Q_logic",
    question=question,
    context=context,
    image_path=None,
    rounds=2,        # short for cost
    save=True,
    output_dir=OUT_DIR,
    mode="design",
)

print("\n" + "=" * 60)
print("ROUND 1 voice_a (first 1500 chars):")
print("=" * 60)
print(result["rounds"][0]["voice_a"][:1500])
print("\n" + "=" * 60)
print("ROUND 1 voice_b (first 1500 chars):")
print("=" * 60)
print(result["rounds"][0]["voice_b"][:1500])
print("\n" + "=" * 60)
print("FINAL DECISION (synthesis):")
print("=" * 60)
print(json.dumps(result["final_decision"], ensure_ascii=False, indent=2))
