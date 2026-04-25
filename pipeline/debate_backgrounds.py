"""Director debate on 9 existing backgrounds — Phase 0D completion.

Per Nirit 2026-04-21: הבמאיים חייבים להכיר את כל הסרט והמשימות ולאחר מכן
לעבור על הרקעים ולראות מה טוב, מה צריך שיפור, ומה עושים.

Uses debate_runner.load_project_context() so voices see content_lock + pose_map
+ camera_bible + asset_manifest. Each voice decides:
  1. Which mission(s) does this background serve?
  2. Does it read instantly as that location?
  3. Does it meet bg camera spec (ground POV, depth, 3 layers, cinematic photorealistic,
     tropical, muted saturation)?
  4. If fail — what must change for regeneration?
"""
import json
import time
from pathlib import Path
from debate_runner import run_debate, DEBATES_DIR

PROJECT = Path(__file__).resolve().parent.parent
BG_DIR = PROJECT / "assets" / "backgrounds"
KEY_DIR = PROJECT / "pipeline" / "bg_keyframes"
OUT_DIR = DEBATES_DIR / "backgrounds"
OUT_DIR.mkdir(parents=True, exist_ok=True)


QUESTION = (
    "דיון במאים על רקע וידאו קיים בפרויקט. לפניך תמונת 2x2 של 4 פריימים מסרטון הרקע. "
    "1) לאיזו משימה (M1-M15) הרקע הזה מתאים — ולמה? "
    "2) האם הרקע נקרא מיד כמיקום של אותה משימה? "
    "3) האם הוא עומד ב-backgrounds camera spec (ground-POV, depth עם 3 שכבות, "
    "תאורה עקבית לזמן-היום, סגנון cinematic photorealistic, רוויה מאופקת)? "
    "4) החלטה: pass / fix (מה לתקן) / redo (ליצור מחדש — מה הבריף החדש)?"
)


def run_one(slug, grid_path):
    t0 = time.time()
    ctx = (
        f"פריט נבדק: {slug} (קובץ: assets/backgrounds/{slug}.mp4). "
        f"2x2 grid של 4 keyframes ב-t=0.5/1.8/3.1/4.5 שניות. "
        f"משך כולל של הסרטון ~5.1 שניות."
    )
    result = run_debate(
        role="director",
        scene_id=f"bg_{slug}",
        question=QUESTION,
        context=ctx,
        image_path=grid_path,
        rounds=8,
        save=True,
        output_dir=OUT_DIR,
        mode="evaluate",
    )
    elapsed = time.time() - t0
    final = result.get("final_decision", {})
    print(f"  [{slug}] decision={final.get('decision')} flag={final.get('director_flag')} "
          f"({elapsed:.0f}s)")
    return result


def main():
    grids = sorted(KEY_DIR.glob("bg_*_grid.png"))
    print(f"running director debate on {len(grids)} backgrounds")
    summary = []
    t_start = time.time()
    for g in grids:
        slug = g.stem.replace("_grid", "")
        try:
            r = run_one(slug, g)
            final = r.get("final_decision", {})
            syn = final.get("synthesis") or ""
            fix = final.get("fix_notes") or ""
            if not isinstance(syn, str):
                syn = json.dumps(syn, ensure_ascii=False)
            if not isinstance(fix, str):
                fix = json.dumps(fix, ensure_ascii=False)
            summary.append({
                "slug": slug,
                "decision": final.get("decision"),
                "director_flag": final.get("director_flag"),
                "synthesis": syn[:220],
                "fix_notes": fix[:220],
            })
        except Exception as e:
            print(f"  [{slug}] ERROR: {e}")
            summary.append({"slug": slug, "error": str(e)})
    total = time.time() - t_start
    out = OUT_DIR / "_summary.json"
    out.write_text(
        json.dumps({"total_sec": int(total), "items": summary},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"done. total={int(total)}s. summary saved: {out}")


if __name__ == "__main__":
    main()
