"""Smoke test: one debate on גלשן_מ01 (production_designer role, 8 rounds)."""
import time
from pathlib import Path
from debate_runner import run_debate

PROJECT = Path(__file__).resolve().parent.parent
IMG = PROJECT / "assets" / "tools_final" / "גלשן_מ01.png"

question = (
    "האם אייקון הכלי 'גלשן רחיפה' (M1, slot B, 2 נקודות, מדד סיכון) אינטואיטיבי לשחקן? "
    "האם עומד בלוגיקת המשחק (בחירת כלי לקפיצה מטוס — wear/use)? האם ויזואלית ברור "
    "ומובחן משתי האפשרויות האחרות בשלישייה (מצנח עגול / חליפת כנפיים)?"
)
context = (
    "משימה M1: 'דלת המטוס נפרצה והרוח שואבת הכל החוצה... איך אני מזנקת מכאן?'. "
    "שלישייה: A=מצנח עגול רחב (1pt, הבטוח) / B=גלשן רחיפה (2pt, הביניים) / "
    "C=חליפת כנפיים (3pt, הנועז). מדד=סיכון. consequence_type=wear. "
    "האייקון שלפנינו הוא לוח-גלשן מכונף עם רצועות כפות רגליים, "
    "צבעים crimson/gold/cobalt, זווית 3/4 נמוכה, רקע studio לבן, ללא רוכב."
)

print(f"image: {IMG} (exists={IMG.exists()})")
t0 = time.time()
result = run_debate(
    role="production_designer",
    scene_id="גלשן_מ01",
    question=question,
    context=context,
    image_path=str(IMG),
    rounds=8
)
print(f"\ndone in {time.time()-t0:.1f}s")
print(f"decision: {result['final_decision'].get('decision')}")
print(f"director_flag: {result['final_decision'].get('director_flag')}")
print(f"synthesis: {result['final_decision'].get('synthesis', '')[:300]}")
