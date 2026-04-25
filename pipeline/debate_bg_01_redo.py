"""Re-debate bg_01 — first run the directors refused to judge, thinking their
mandate was tool-icon validation. This question is bluntly framed around bg only.
"""
import json
import time
from pathlib import Path
from debate_runner import run_debate, DEBATES_DIR

PROJECT = Path(__file__).resolve().parent.parent
GRID = PROJECT / "pipeline" / "bg_keyframes" / "bg_01_grid.png"
OUT = DEBATES_DIR / "backgrounds"

QUESTION = (
    "שים לב: הדיון הזה הוא על **רקע וידאו** (video background) של המשחק — "
    "לא על אייקון כלי. לפניך תמונת 2x2 של 4 פריימים מ-bg_01.mp4. "
    "עליך לענות ישירות על 4 השאלות האלה, אסור לסרב ואסור להעביר לדיון על כלים: "
    "1) לאיזו משימה (M1-M15) הרקע הזה מתאים ביותר — ולמה? "
    "2) האם הרקע נקרא מיד כמיקום של אותה משימה? "
    "3) האם הוא עומד ב-backgrounds camera spec (ground-POV, depth עם 3 שכבות, "
    "תאורה עקבית לזמן-היום, סגנון cinematic photorealistic, רוויה מאופקת)? "
    "4) החלטה: pass / fix (מה לתקן) / redo (ליצור מחדש — מה הבריף החדש)? "
    "זה רקע, לא כלי — חובה לנתח את הווידאו ולא לסרב."
)


def main():
    t0 = time.time()
    ctx = (
        "פריט נבדק: bg_01 (קובץ: assets/backgrounds/bg_01.mp4). "
        "2x2 grid של 4 keyframes ב-t=0.5/1.8/3.1/4.5 שניות. "
        "הדיון הקודם (רוזר 1) סירב לענות מתוך בלבול תפקיד. "
        "הפעם: נושא הדיון = background video בלבד."
    )
    r = run_debate(
        role="director",
        scene_id="bg_bg_01_v2",
        question=QUESTION,
        context=ctx,
        image_path=GRID,
        rounds=8,
        save=True,
        output_dir=OUT,
        mode="evaluate",
    )
    elapsed = time.time() - t0
    final = r.get("final_decision", {}) or {}
    print(f"[bg_01_v2] decision={final.get('decision')} flag={final.get('director_flag')} ({elapsed:.0f}s)")
    print(f"  synthesis: {str(final.get('synthesis') or '')[:200]}")
    print(f"  fix_notes: {str(final.get('fix_notes') or '')[:200]}")


if __name__ == "__main__":
    main()
