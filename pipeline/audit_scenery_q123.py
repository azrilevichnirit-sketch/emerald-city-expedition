"""Retroactive Q1/Q2/Q3 audit of every existing scenery prop.

For each PNG in assets/scenery/:
 1. Find its mission(s) via _props_structured.json
 2. Single Gemini-Vision call asking the 3 reuse-veto questions
    + visual checks (frame visible? mini-bg vs. focused prop?)
 3. Verdict per prop: keep / merge_to_bg / move_to_sound / reuse_other / delete

Output: pipeline/review/scenery_audit_q123.json — for Nirit to approve
before any actual file is moved or deleted. NO files are deleted by this
script. It only produces a report.

Per Nirit 2026-04-25 demo priorities:
 - Looks professional > exact text content
 - Existing prop placed correctly with NO frame around it
 - Tools must show NO chroma green leak
 - Player must visibly receive + use selected tool
"""
import sys
import json
import base64
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "pipeline"))

from debate_runner import call_gemini

PROPS_STRUCTURED = PROJECT / "pipeline" / "debates" / "scenery" / "_props_structured.json"
BG_MAP_PATH      = PROJECT / "pipeline" / "bg_mission_map.json"
SCENERY_DIR      = PROJECT / "assets" / "scenery"
LOCK_PATH        = PROJECT / "content_lock.json"
OUT_PATH         = PROJECT / "pipeline" / "review" / "scenery_audit_q123.json"
OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

LOCK = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
BGMAP = json.loads(BG_MAP_PATH.read_text(encoding="utf-8")).get("map", {})
PROPS_PLAN = json.loads(PROPS_STRUCTURED.read_text(encoding="utf-8"))

# slug -> mission (from structured plan)
SLUG_TO_MISSION = {p["slug"]: p["mission"] for p in PROPS_PLAN}

# mission -> bg slug
MISSION_TO_BG = {}
for bg_slug, mid in BGMAP.items():
    MISSION_TO_BG.setdefault(mid, []).append(bg_slug)


def list_scenery_files():
    """All actual PNG files in assets/scenery/, excluding underscored/backup files."""
    if not SCENERY_DIR.exists():
        return []
    return sorted(p for p in SCENERY_DIR.glob("*.png") if not p.name.startswith("_"))


def build_prompt_for_prop(prop_path: Path, all_slugs: list[str]) -> str:
    slug = prop_path.stem
    mid = SLUG_TO_MISSION.get(slug, "unknown")
    mission = LOCK["missions"].get(mid, {})
    mission_text = mission.get("mission_text", "")
    checkpoint   = mission.get("checkpoint_text", "")
    bgs = MISSION_TO_BG.get(mid, [])
    other_props = sorted(s for s in all_slugs if s != slug)

    return (
        "אתה auditor של אביזרי סצנה. עליך לסווג את ה-prop הזה לפי 3 שאלות "
        "(Q1/Q2/Q3 reuse-veto framework) + 2 בדיקות ויזואליות.\n"
        f"\nPROP: {slug}.png\n"
        f"שויך למשימה: {mid}\n"
        f"mission_text: {mission_text}\n"
        f"checkpoint_text: {checkpoint}\n"
        f"bg של המשימה: {', '.join(bgs) if bgs else 'אין bg ייעודי'}\n"
        f"\nרשימת כל ה-scenery הקיים (לבדיקת Q3 reuse — האם פריט קיים אחר יכול לשרת במקום זה):\n"
        f"{', '.join(other_props)}\n"
        "\n"
        "ענה על:\n"
        "Q1 (bg_coverage): האם ה-bg של המשימה (לפי השם והקונטקסט הסביבתי) מכיל את "
        "האלמנט הזה באופן טבעי? (למשל ג'ונגל מכיל שיחים/עצים/עלווה כברירת מחדל). yes/no + משפט.\n"
        "\n"
        "Q2 (sound_carry): האם מה שה-prop אמור לבטא הוא ביט דינמי שסאונד יכול לשאת לבדו "
        "(תנועה/קול/זמן — 'רועד', 'נשבר', 'נשמע מכיוון אחר', 'הולך ומתקרב')? yes/no + משפט.\n"
        "\n"
        "Q3 (reuse_other): האם מבין רשימת ה-scenery האחרים יש פריט שיכול לשרת זאת בשינוי "
        "transform/scale/position? אם כן ציין אותו. yes/no + שם הפריט אם yes.\n"
        "\n"
        "בדיקות ויזואליות (לפי התמונה):\n"
        "frame_visible: האם יש מסגרת/border/box ויזואלי סביב הסובייקט (קווי גבול לבנים/"
        "כחולים/אחר)? true/false + תיאור קצר אם true.\n"
        "is_mini_bg: האם התמונה למעשה bg-מיני שמכיל סצנה שלמה (עצים+שמיים+קרקע) במקום "
        "סובייקט אחד מבודד על ירוק? true/false + תיאור קצר.\n"
        "\n"
        "**verdict** — בחר אחד מהבאים:\n"
        " - 'keep' = ה-prop ייחודי, ממוקד, לא כפול עם bg/sound, אין מסגרת.\n"
        " - 'merge_to_bg' = הוא תוכן bg-מיני או חלק טבעי של ה-bg, צריך לאפות לתוך ה-bg.\n"
        " - 'move_to_sound' = הביט שלו בעצם אודיו (תנועה/קול), לא צריך PNG.\n"
        " - 'reuse_other' = פריט אחר ברשימה יכול לשרת. ציין שם הפריט.\n"
        " - 'fix_frame' = ה-prop בסדר מהותית אבל יש לו מסגרת/border שצריך לנקות.\n"
        " - 'delete' = פשוט מיותר/לא קשור למשימה.\n"
        "\n"
        "**rationale** — משפט אחד עד שניים שמסביר את הוורדיקט.\n"
        "\n"
        "החזר JSON בלבד בפורמט:\n"
        '{"slug":"...","mission":"...","q1_bg_coverage":{"answer":"yes|no","note":"..."},'
        '"q2_sound_carry":{"answer":"yes|no","note":"..."},'
        '"q3_reuse_other":{"answer":"yes|no","note":"...","reuse_target":null|"<slug>"},'
        '"frame_visible":{"answer":true|false,"note":"..."},'
        '"is_mini_bg":{"answer":true|false,"note":"..."},'
        '"verdict":"keep|merge_to_bg|move_to_sound|reuse_other|fix_frame|delete",'
        '"rationale":"..."}'
    )


def parse_json(text: str) -> dict:
    import re
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return {"_parse_error": "no json found", "_raw": text[:300]}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError as e:
        return {"_parse_error": str(e), "_raw": text[:300]}


def audit_one(prop_path: Path, all_slugs: list[str]) -> dict:
    b64 = base64.b64encode(prop_path.read_bytes()).decode("ascii")
    prompt = build_prompt_for_prop(prop_path, all_slugs)
    try:
        resp = call_gemini(
            system="אתה auditor של scenery props. החזר JSON תקין בלבד.",
            user_text=prompt,
            image_b64=b64,
            max_tokens=1000,
        )
    except Exception as e:
        return {"slug": prop_path.stem, "_error": str(e)[:300]}
    parsed = parse_json(resp)
    parsed.setdefault("slug", prop_path.stem)
    parsed["_image_path"] = str(prop_path)
    return parsed


def load_existing_log() -> dict:
    if OUT_PATH.exists():
        try:
            return json.loads(OUT_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"items": {}}
    return {"items": {}}


def save_log(log: dict):
    log["_updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    OUT_PATH.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")


def main():
    files = list_scenery_files()
    all_slugs = [f.stem for f in files]
    print(f"scanning {len(files)} scenery PNGs ...")

    log = load_existing_log()
    log.setdefault("items", {})
    log.setdefault("_priorities_from_nirit", [
        "looks professional",
        "no frame around prop",
        "tools clean (no green leak) — no regen",
        "tool handoff + use animation when player chooses",
    ])

    for i, f in enumerate(files, 1):
        slug = f.stem
        if slug in log["items"] and "verdict" in log["items"][slug]:
            print(f"  [{i}/{len(files)}] {slug}: cached, skip")
            continue
        print(f"  [{i}/{len(files)}] {slug} ... ", end="", flush=True)
        result = audit_one(f, all_slugs)
        log["items"][slug] = result
        verdict = result.get("verdict", "_error")
        print(verdict)
        save_log(log)  # incremental

    # summary
    counts = {}
    for v in log["items"].values():
        counts[v.get("verdict", "_error")] = counts.get(v.get("verdict", "_error"), 0) + 1
    print("\nSUMMARY:")
    for k, n in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"  {k}: {n}")
    save_log(log)
    print(f"\n=== DONE -> {OUT_PATH} ===")


if __name__ == "__main__":
    main()
