"""debate_runner.py — 3-engine / 8-round creative debate per agents/debate_protocol.md

Engines:
  - Claude Sonnet 4.6  (Anthropic REST)
  - Gemini 2.5 Flash   (Google AI Studio REST)
  - GPT-4o-mini        (OpenAI REST)

Roles and voice assignments are loaded from the protocol's ASSIGNMENTS table.

Each debate runs 8 rounds. In rounds 1-7 voice_a and voice_b argue, moderator
summarises the gap. Round 8: voice_a + voice_b give final positions, moderator
synthesises and emits the final_decision JSON (with director_flag).

Output per debate: pipeline/debates/{role}_{scene_id}.json
"""
import json
import base64
import urllib.request
import urllib.error
import re
import sys
import time
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
KEYS = PROJECT / "keys"
DEBATES_DIR = PROJECT / "pipeline" / "debates"
DEBATES_DIR.mkdir(parents=True, exist_ok=True)

CONTENT_LOCK_PATH   = PROJECT / "content_lock.json"
POSE_MAP_PATH       = PROJECT / "pipeline" / "pose_map.json"
CAMERA_BIBLE_PATH   = PROJECT / "pipeline" / "camera_bible.json"
ASSET_MANIFEST_PATH = PROJECT / "pipeline" / "asset_manifest.json"
BG_MISSION_MAP_PATH = PROJECT / "pipeline" / "bg_mission_map.json"
SCENERY_DIR         = PROJECT / "assets" / "scenery"
TOOLS_DIR           = PROJECT / "assets" / "tools"
BACKGROUNDS_DIR     = PROJECT / "assets" / "backgrounds"

CLAUDE_KEY = (KEYS / "claude" / "key.txt").read_text(encoding="utf-8").strip()
OPENAI_KEY = (KEYS / "openai" / "openai_KEY.txt").read_text(encoding="utf-8").strip()


def _load_gemini_keys():
    """Load all available Gemini keys (primary + any alternates).

    key.txt = KEY_A (primary). key_2.txt = KEY_B (second project for parallel quota).
    Returns list of non-empty strings.
    """
    folder = KEYS / "gimini_key - Copy"
    keys = []
    for fname in ("key.txt", "key_2.txt"):
        p = folder / fname
        if p.exists():
            raw = p.read_text(encoding="utf-8").strip()
            # key_2.txt has more than just a key on line 1
            first_line = raw.splitlines()[0].strip() if raw else ""
            if first_line.startswith("AIza"):
                keys.append(first_line)
    return keys


GEMINI_KEYS = _load_gemini_keys()
GEMINI_KEY = GEMINI_KEYS[0] if GEMINI_KEYS else ""


def get_gemini_key(idx_env="GEMINI_KEY_IDX"):
    """Pick a Gemini key at call time so callers can set os.environ[idx_env] to swap pools.

    Default idx=0 (primary). Set os.environ['GEMINI_KEY_IDX']='1' to use KEY_B.
    On index out of range, wraps to 0.
    """
    import os
    try:
        idx = int(os.environ.get(idx_env, "0"))
    except ValueError:
        idx = 0
    if not GEMINI_KEYS:
        return ""
    return GEMINI_KEYS[idx % len(GEMINI_KEYS)]

CLAUDE_MODEL = "claude-sonnet-4-5"
OPENAI_MODEL = "gpt-4o-mini"
GEMINI_MODEL = "gemini-2.5-flash"

ASSIGNMENTS = {
    "director":            ("claude", "gemini", "openai"),
    "production_designer": ("gemini", "claude", "openai"),
    "set_manager":         ("gemini", "claude", "openai"),
    "sound_designer":      ("claude", "gemini", "openai"),
    "actor_director":      ("gemini", "claude", "openai"),
    "editor":              ("claude", "gemini", "openai"),
}


_PROJECT_CONTEXT_CACHE = None


def load_existing_inventory():
    """Live (un-cached) listing of every reusable asset in the project.

    Set_manager + production_designer voices receive this so they can answer
    'is what we already have enough?' before proposing a new prop.

    Per Nirit 2026-04-25: 'הבמאים מסתכלים בקטן ולא רואים מה כבר יש' —
    inventory is rebuilt every call so newly-created assets are visible
    immediately to the next debate.
    """
    lines = []
    lines.append("═══ INVENTORY חי — נכסים שכבר נוצרו (לבדוק שימוש חוזר לפני יצירה) ═══")
    lines.append("")

    # 1. Backgrounds (full 8s videos — each one is the *entire* on-screen frame for its mission)
    if BG_MISSION_MAP_PATH.exists():
        try:
            bgmap = json.loads(BG_MISSION_MAP_PATH.read_text(encoding="utf-8"))
            lines.append("📺 **Backgrounds במאגר (כל אחד וידאו 8s שמכיל את כל הפריים — שיחים/עצים/שמיים/קרקע):**")
            delivered = []
            for slug, mid in bgmap.get("map", {}).items():
                bg_path = BACKGROUNDS_DIR / f"{slug}.mp4"
                marker = "✓" if bg_path.exists() else "✗ (חסר)"
                delivered.append(f"  {marker} {slug}.mp4 → {mid}")
            lines.extend(delivered)
            notes = bgmap.get("notes", {})
            if notes:
                lines.append("  הערות bg:")
                for slug, note in notes.items():
                    lines.append(f"    {slug}: {note}")
        except (json.JSONDecodeError, OSError):
            lines.append("  (bg_mission_map.json לא נטען)")
    lines.append("")

    # 2. Scenery PNGs already in assets/scenery/ — actual files (case-sensitive truth)
    if SCENERY_DIR.exists():
        files = sorted(p.name for p in SCENERY_DIR.glob("*.png") if not p.name.startswith("_"))
        lines.append(f"🌿 **Scenery PNG כבר במאגר ({len(files)} פריטים — לבדוק שימוש חוזר/transform/scale לפני CREATE):**")
        for f in files:
            lines.append(f"  {f}")
    else:
        lines.append("🌿 **Scenery PNG כבר במאגר: אין (תיקייה ריקה).**")
    lines.append("")

    # 3. Tool icons — count only (כלים נעולים, לא לדיון, רק לידיעה)
    if TOOLS_DIR.exists():
        n_tools = sum(1 for _ in TOOLS_DIR.glob("*.png"))
        lines.append(f"🔧 **Tool icons במאגר: {n_tools} (נעולים, לא לדיון set_manager).**")
    lines.append("")

    lines.append("═══ סוף INVENTORY ═══")
    return "\n".join(lines)


def load_project_context():
    """Load + format the full project state as a single briefing block.

    Every debate voice receives this so voices judge artifacts with full
    awareness of the film (missions, poses, camera rules, existing assets).
    Per Nirit 2026-04-21: 'כל חברי ההפקה חייבים להכיר את כל הנתונים'.
    """
    global _PROJECT_CONTEXT_CACHE
    if _PROJECT_CONTEXT_CACHE is not None:
        return _PROJECT_CONTEXT_CACHE

    lock = json.loads(CONTENT_LOCK_PATH.read_text(encoding="utf-8"))
    poses = json.loads(POSE_MAP_PATH.read_text(encoding="utf-8"))
    bible = json.loads(CAMERA_BIBLE_PATH.read_text(encoding="utf-8"))
    manifest = json.loads(ASSET_MANIFEST_PATH.read_text(encoding="utf-8"))

    # Nirit's audit brief — psychological-metric bias check.
    # Always visible so every Director/QA vote remembers the hidden-assessment rule.
    audit_brief_path = PROJECT / "pipeline" / "final_audit_brief.md"
    audit_brief = (
        audit_brief_path.read_text(encoding="utf-8")
        if audit_brief_path.exists() else ""
    )

    lines = []
    lines.append("═══ STUDIO EMERALD — PROJECT BRIEFING (מעודכן בכל דיון) ═══")
    lines.append("")
    lines.append("📖 **נרטיב פתיחה:**")
    lines.append(lock.get("opening_narrative", ""))
    lines.append("")
    lines.append("🎬 **15 משימות (verbatim — נעול):**")
    for mid, m in lock["missions"].items():
        tools = m.get("tools", [])
        tool_line = " / ".join(
            f"{t['slot']}={t['label']} ({t['points']}p)" for t in tools
        )
        lines.append(f"  {mid}: {m['mission_text']}")
        lines.append(f"       כלים: {tool_line}")
        lines.append(f"       צ'ק-פוינט: {m.get('checkpoint_text','')}")
    lines.append("")
    lines.append("📊 **Scoring dimensions (לא נראים לשחקן):**")
    for dim, spec in lock.get("scoring", {}).get("dimensions", {}).items():
        lines.append(f"  {dim}: {spec['missions']} (range {spec['range']})")
    lines.append("")
    lines.append("🎭 **Profiles (תוצאה סופית לשחקן):**")
    for key, p in lock.get("profiles", {}).items():
        lines.append(f"  {key}: {p['title']} — {p['description']}")
    lines.append("")
    lines.append("🕴️ **Player animations (pose_map.json):**")
    for pose_file, p in poses.get("poses", {}).items():
        lines.append(
            f"  {pose_file}: {p.get('semantic_name','?')} — "
            f"משך {p.get('duration_sec','?')}s, use_in={p.get('use_in',[])}"
        )
    missing = poses.get("_missing_anims", [])
    if missing:
        lines.append("  ❌ חסרים:")
        for m in missing:
            lines.append(
                f"     {m.get('semantic_name')} → {m.get('target_filename')} "
                f"({m.get('severity','?')}) — {m.get('expected_use',[])}"
            )
    lines.append("")
    lines.append("🎨 **Camera Bible — tools camera:**")
    t = bible.get("tools", {})
    lines.append(
        f"  רקע={t.get('background','?')} | זווית={t.get('angle','?')} | "
        f"תאורה={t.get('lighting','?')} | סגנון={t.get('style','?')}"
    )
    b = bible.get("backgrounds", {})
    lines.append(
        f"  רקעים: זווית={b.get('angle','?')} | עומק={b.get('depth','?')} | "
        f"סגנון={b.get('style','?')}"
    )
    lines.append("")
    lines.append("📦 **Asset manifest (מה קיים):**")
    summary = manifest.get("summary", {})
    lines.append(
        f"  backgrounds={summary.get('backgrounds','?')}, "
        f"player={summary.get('player','?')}, "
        f"tools={summary.get('tools','?')}, "
        f"scenery={summary.get('scenery','?')}, "
        f"effects={summary.get('effects','?')}, "
        f"rivals={summary.get('rivals','?')}"
    )
    lines.append("")
    lines.append("🔒 **consequence_type לכל כלי (איך הכלי מתנהג אחרי תפיסה):**")
    for label, ct in lock.get("tool_consequence_types", {}).get("per_tool", {}).items():
        lines.append(f"  {label}: {ct}")
    lines.append("")
    if audit_brief:
        lines.append("📋 **FINAL AUDIT BRIEF — read before voting on any asset:**")
        lines.append(audit_brief)
    lines.append("═══ סוף BRIEFING ═══")

    _PROJECT_CONTEXT_CACHE = "\n".join(lines)
    return _PROJECT_CONTEXT_CACHE


def _post_json(url, body, headers, timeout=180):
    req = urllib.request.Request(
        url, data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers}, method="POST"
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < 2:
                time.sleep(2 ** attempt * 3)
                continue
            raise
        except urllib.error.URLError:
            if attempt < 2:
                time.sleep(2 ** attempt * 3)
                continue
            raise


def call_claude(system, user_text, image_b64=None, max_tokens=500):
    parts = []
    if image_b64:
        parts.append({"type": "image",
                      "source": {"type": "base64", "media_type": "image/png", "data": image_b64}})
    parts.append({"type": "text", "text": user_text})
    body = {
        "model": CLAUDE_MODEL,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": parts}]
    }
    data = _post_json(
        "https://api.anthropic.com/v1/messages", body,
        {"x-api-key": CLAUDE_KEY, "anthropic-version": "2023-06-01"}
    )
    return "".join(b.get("text", "") for b in data.get("content", []))


def call_openai(system, user_text, image_b64=None, max_tokens=500):
    content = []
    if image_b64:
        content.append({"type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{image_b64}"}})
    content.append({"type": "text", "text": user_text})
    body = {
        "model": OPENAI_MODEL,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": content}
        ]
    }
    data = _post_json(
        "https://api.openai.com/v1/chat/completions", body,
        {"Authorization": f"Bearer {OPENAI_KEY}"}
    )
    return data["choices"][0]["message"]["content"]


def call_gemini(system, user_text, image_b64=None, max_tokens=500):
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{GEMINI_MODEL}:generateContent?key={get_gemini_key()}")
    parts = []
    if image_b64:
        parts.append({"inlineData": {"mimeType": "image/png", "data": image_b64}})
    parts.append({"text": user_text})
    body = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {
            "maxOutputTokens": max_tokens,
            "temperature": 0.7,
            "thinkingConfig": {"thinkingBudget": 0}
        }
    }
    data = _post_json(url, body, {})
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        return f"[gemini_no_content] {json.dumps(data)[:300]}"


def call_engine(engine, system, user_text, image_b64=None, max_tokens=500):
    if engine == "claude":
        return call_claude(system, user_text, image_b64, max_tokens)
    if engine == "openai":
        return call_openai(system, user_text, image_b64, max_tokens)
    if engine == "gemini":
        return call_gemini(system, user_text, image_b64, max_tokens)
    raise ValueError(engine)


_ROLE_SCOPES = {
    "production_designer": {
        "design": (
            "הדיון עוסק **אך ורק** בשאלה: **מה צריך אייקון הכלי להראות כדי שייקרא "
            "מיד כשם הכלי?** צורה, חומר, צבע, זווית, אלמנט-חתימה. "
            "אסור לדון בשם הכלי (נעול), התאמה למשימה, מכניקה, scoring, דירוג."
        ),
        "evaluate": (
            "הדיון עוסק **אך ורק** בשאלה: **האם אייקון הכלי נקרא מיד בעברית כשמו?** "
            "כן=pass / לא=fail. אסור לדון בשם, התאמה, מכניקה, scoring."
        ),
    },
    "director": {
        "design": (
            "הדיון הוא על **עיצוב סצנה/רקע/רצף** לפני ייצור. שפוט אם הבריף תומך "
            "באווירה, קריאות המיקום, ותנאי המצלמה. אסור לשנות שמות כלים/משימות/scoring."
        ),
        "evaluate": (
            "הדיון הוא על **רקע וידאו (background video)** או סצנה/רצף מוכן. "
            "השאלות: (1) למשימה איזו? (2) האם נקרא מיד כאותה משימה? "
            "(3) תאימות camera spec? (4) pass/fix/redo + מה לתקן? "
            "אסור לסרב לנתח. אסור לעבור לדיון על כלים — זה לא הנושא."
        ),
    },
    "set_manager": {
        "design": (
            "הדיון עוסק **אך ורק** ב-scenery props על **הרקע** לסצנה הזו. "
            "תפקידך: לענות על 'מה אביזרים/רכיבי תפאורה על הרקע של המשימה?' — "
            "לא על כלי השחקנית, לא על אייקון, לא על שימוש מכני. "
            "**אסור להתייחס לאייקוני כלי-יד (tools) בכלל.** הכלים נעולים וכבר קיימים.\n"
            "\n"
            "🛑 **חוק ברזל (2026-04-25): ברירת המחדל היא לא ליצור prop חדש.**\n"
            "ב-INVENTORY שלמעלה מופיעים כל ה-bgs המתוכננים/מסופקים וכל ה-scenery הקיים. "
            "לפני שאתה מציע prop חדש כלשהו, חובה לענות בכתב על 3 שאלות לכל אלמנט שמופיע "
            "ב-mission_text, ולנמק התשובה במשפט:\n"
            "\n"
            "**(Q1) Bg-coverage:** האם ה-bg של המשימה הזו (לפי bg_mission_map ב-INVENTORY "
            "שלמעלה, או בריף ה-bg המתוכנן) כבר מכיל את האלמנט באופן טבעי? "
            "(M5=ג'ונגל ⇒ שיחים/ענפים/עלווה כבר ברקע; M15=קו סיום ⇒ אם הסצנה כולה "
            "היא קרחת סיום ריקה ב-bg, אין צורך ב-prop נפרד של 'קו סיום' — עדיף שה-bg "
            "כולו יציג את הסיום).\n"
            "\n"
            "**(Q2) Sound-can-carry:** האם זה ביט דינמי (תנועה/קול/זמן) שסאונד יכול לשאת "
            "לבדו? (PNG סטטי לא 'רועד' ולא 'נשבר' ולא 'נשמע מכיוון אחר' — אלה צלילים בלבד). "
            "אם הביט הוא תנועה/אודיו → אין prop, רק cue ל-sound_designer.\n"
            "\n"
            "**(Q3) Reuse:** האם פריט מ-`assets/scenery/` הקיים (ראה רשימה ב-INVENTORY) "
            "יכול לשרת זאת בשינוי transform/scale/position בלבד, בלי יצירה מחדש?\n"
            "\n"
            "**כלל הכרעה:**\n"
            "- אם Q1='כן' או Q2='כן' או Q3='כן' → **אסור** להציע prop חדש. רשום שורה אחת:\n"
            "  '<אלמנט>: covered_by_bg' / 'covered_by_sound' / 'reuse=<filename> at <transform>'.\n"
            "- רק אם **כל שלוש** התשובות 'לא' → מותר להציע CREATE, וחובה לכתוב משפט יחיד "
            "המסביר *מה בדיוק* ה-prop מוסיף שאי אפשר להשיג בשילוב bg+sound+פריט קיים.\n"
            "\n"
            "**🛑 דגל אזהרה — כפילות bg-prop:** אם prop שאתה מציע יכול 'לבלוע' את כל הפריים "
            "(למשל 'אורות חגיגה' שכוללים בתוכם עצים/שמיים, או 'קו סיום' עם רקע ג'ונגל אפוי "
            "בתוכו) — זה איתות שמדובר למעשה ב-bg, לא ב-prop. הצע bg חדש במקום זאת, או הוסף "
            "את האלמנט ל-bg הקיים של המשימה.\n"
            "\n"
            "פורמט הפלט הסופי בסבב 8 — synthesis חייב לכלול:\n"
            "  • לכל אלמנט מ-mission_text: שורה אחת ('<אלמנט>: covered_by_bg/sound/reuse/CREATE').\n"
            "  • לפריטי CREATE בלבד: שם קובץ מוצע + CSS zone + משפט הצדקה (מה הוא מוסיף).\n"
            "  • סך הכול pass כשהרשימה מלאה (גם רשימה ריקה היא pass לגיטימי אם הכל covered)."
        ),
        "evaluate": (
            "הדיון הוא על prop סצני מוכן (PNG). שפוט: נקרא מיד כ-prop שלשמו יועד? "
            "מתאים לסצנה? רזולוציה? **בנוסף: האם התמונה למעשה bg-מיני שמכיל סצנה שלמה "
            "(עצים/שמיים/קרקע) במקום prop ממוקד? אם כן — fix עם הערה שה-prop כפול עם bg.** "
            "pass/fix/redo. אסור לדון בכלי-יד."
        ),
    },
    "actor_director": {
        "design": (
            "הדיון עוסק ב-**תנועה/pose של השחקנית** לפני ייצור הסרטון. "
            "שפוט: האם הבריף (תנועה, hold_frame, תאורה, wardrobe, green-screen) "
            "משרת את המשימות המיועדות? האם יש פערים שחייבים תיקון לפני Veo? "
            "אסור לדון באייקוני כלי-יד. הכלים נעולים."
        ),
        "evaluate": (
            "הדיון על סרטון pose מוכן. שפוט: התנועה קריאה? הדמות עקבית? "
            "green-screen נקי? חלק hold_frame עובד? pass/fix/redo."
        ),
    },
    "editor": {
        "design": "דיון על עריכה/מעבר — שפוט קצב, חיתוכים, מעברים. לא כלי.",
        "evaluate": "דיון על רצף ערוך. שפוט קצב, המשכיות, pass/fix/redo. לא כלי.",
    },
    "sound_designer": {
        "design": "דיון על פסקול — SFX, אווירה, מוזיקה. לא כלי, לא ויזואל.",
        "evaluate": "דיון על פסקול מוכן. pass/fix/redo. לא כלי.",
    },
}


def _role_system(role, voice_label, is_final, mode="evaluate"):
    final_note = " זה סבב 8 — עמדה סופית מגובשת." if is_final else ""
    role_scope = _ROLE_SCOPES.get(role, {}).get(mode)
    if role_scope is None:
        role_scope = (
            "הדיון נתון ל-scope של התפקיד שלך ולשאלה הקונקרטית. "
            "אסור לדון ב-content_lock (שמות כלים, מיפוי משימות, scoring — נעולים)."
        )
    scope = (
        "\n\n🚫 **SCOPE נוקשה — חובה לכבד:**\n"
        + role_scope +
        "\n\n**אסור לך לגעת ב-content_lock:** שמות כלים, מיפוי כלי→משימה, "
        "ממדים פסיכולוגיים, scoring, slot ranking — כולם נעולים ב-content_lock.json.\n"
    )
    common = (
        f"אתה {voice_label} של סוכן {role} בחברת הפקה Studio Emerald.\n"
        f"עברית בלבד. תשובה קצרה (עד 3 משפטים).{final_note}"
    ) + scope

    is_voice_b = ("מאתגר" in voice_label) or voice_label.startswith("קול ב")
    is_voice_a = not is_voice_b

    # Special-case: set_manager / production_designer in DESIGN mode need an
    # active prop-cutter, not a default-approve voice_b. The general project
    # bias toward "מאושר" was added to stop over-rejection on tool icons,
    # but it caused echo-chamber set_manager debates that approved every prop.
    # In design mode we explicitly invert voice_b to a redundancy hunter.
    if is_voice_b and role in ("set_manager", "production_designer") and mode == "design":
        return common + (
            "\nהתפקיד שלך: קול ב (קוצץ פרופים) — תפקידך אקטיבי לא פסיבי.\n"
            "ברירת המחדל שלך היא **לא** ליצור prop חדש. עבור על כל פריט שקול א מציע, "
            "ובדוק לפי 3 השאלות (Q1 bg-coverage / Q2 sound-can-carry / Q3 reuse-existing). "
            "אם **כל אחת** מהשאלות עונה 'כן' — אתה חייב להתנגד ולסמן את הפריט "
            "covered_by_bg / covered_by_sound / reuse=<filename>.\n"
            "**אסור** לאמר 'מאושר' רק כי הפריט מופיע ב-mission_text. הופעה בטקסט = רעיון, "
            "לא = הצדקה ל-PNG. הופעה בטקסט נופלת ל-Q1 או Q2 ברוב המקרים.\n"
            "מאשר רק אם קול א הוכיח שהפריט עבר את כל 3 השאלות במצב 'לא'."
        )

    if is_voice_b:
        return common + (
            "\nהתפקיד שלך: קול ב (מאתגר) — מכויל.\n"
            "אם הפריט/הבריף עובד לפי ה-scope שלך — **אמור 'מאושר' וסיים**. "
            "מאתגר רק אם יש בעיה אמיתית בתוך ה-scope של התפקיד."
        )

    # voice_a — also tighten for set_manager design so it leads with the
    # 3-question discipline rather than just listing props.
    if is_voice_a and role == "set_manager" and mode == "design":
        return common + (
            "\nהתפקיד שלך: קול א (מוביל). אסור לקפוץ ישר לרשימת PNG-ים.\n"
            "השלב הראשון שלך: עבור על כל אלמנט שמופיע ב-mission_text, וענה בכתב על "
            "Q1/Q2/Q3 לכל אחד. רק אחרי שכל פריט סווג כ-covered_by_bg / covered_by_sound / "
            "reuse / CREATE — תרכיב את רשימת ה-CREATE עם CSS zones והצדקה.\n"
            "תשובה ראויה כוללת לפחות 3 שורות סיווג לפני כל הצעת קובץ חדש."
        )

    return common + (
        "\nהתפקיד שלך: קול א (מוביל). שפוט לפי ה-scope של התפקיד שלך. "
        "אם תקין — אמור זאת ברור וסיים. אם לא — תאר מה חסר."
    )


def _moderator_system(is_final):
    if is_final:
        return (
            "אתה מנחה דיון creative בסבב 8 האחרון. סנתז את הטוב משתי העמדות.\n"
            "החזר JSON בלבד (ללא טקסט סביב):\n"
            '{"synthesis": "...", "decision": "pass"|"fix"|"redo", '
            '"director_flag": true|false, "flag_reason": null|"..." , '
            '"fix_notes": "..."} \n\n'
            "**כללי הכרעה מכוילים:**\n"
            "- **pass** = ברירת המחדל כאשר שני הקולות הסכימו שהכלי עובד. אל תכריח "
            "fix אם אין בעיה ממשית. 'אפשר תמיד לשפר משהו' הוא לא סיבה ל-fix.\n"
            "- **fix** = רק כשזוהתה בעיה אמיתית ב-1+ מ-6 השאלות (אינסטיקנט/הבחנה/"
            "לוגיקה/טון/מלכודת/דירוג). חובה לתאר איזו שאלה נכשלה.\n"
            "- **redo** = רק כשהכלי נכשל באופן יסודי והוא פשוט לא עובד.\n"
            "- **director_flag=true** = רק אם יש מחלוקת לא פתורה בין הקולות, או "
            "חשש ייסודי. אם שניהם הסכימו — false."
        )
    return (
        "אתה מנחה דיון creative. סכם במשפט אחד-שניים את הפער שנותר בין שני הקולות. "
        "אם שניהם מסכימים — אמור זאת. בלי להכריע. עברית."
    )


def _round_user(role, question, context, history, voice, voice_label, project_brief):
    h_text = ""
    if history:
        h_text = "\n\nהיסטוריית הדיון עד כה:\n"
        for r in history[-3:]:
            h_text += f"\n[סבב {r['round']}]\nקול א: {r['voice_a']}\nקול ב: {r['voice_b']}\nמנחה: {r['moderator_summary']}\n"
    opp = "קול ב" if voice == "voice_a" else "קול א"
    instr = f"ענה כ{voice_label}. התייחס לעמדת {opp} מהסבב הקודם אם יש."
    return (
        f"{project_brief}\n\n"
        f"───── הדיון הנוכחי ─────\n"
        f"דיון של {role}.\n"
        f"שאלה: {question}\n"
        f"הקשר הספציפי לפריט שנבדק: {context}\n"
        f"{h_text}\n"
        f"{instr}"
    )


def _moderator_user(round_num, voice_a, voice_b, is_final, question, context, project_brief):
    if is_final:
        return (
            f"{project_brief}\n\n"
            f"───── הדיון הנוכחי ─────\n"
            f"שאלה: {question}\n"
            f"הקשר הספציפי: {context}\n\n"
            f"עמדה א (סבב 8): {voice_a}\n"
            f"עמדה ב (סבב 8): {voice_b}\n\n"
            "סנתז והחזר JSON בלבד."
        )
    return (
        f"סבב {round_num}.\n"
        f"עמדה א: {voice_a}\n"
        f"עמדה ב: {voice_b}\n\n"
        "סכם את הפער במשפט-שניים."
    )


def _parse_final(text):
    m = re.search(r"\{.*\}", text, re.S)
    raw = m.group(0) if m else text
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {
            "synthesis": text[:400],
            "decision": "redo",
            "director_flag": True,
            "flag_reason": "moderator output not valid JSON",
            "fix_notes": "manual review required"
        }


def run_debate(role, scene_id, question, context, image_path=None, rounds=8, save=True, output_dir=None, mode="evaluate"):
    if role not in ASSIGNMENTS:
        raise ValueError(f"unknown role: {role}")
    voice_a_eng, voice_b_eng, mod_eng = ASSIGNMENTS[role]

    image_b64 = None
    if image_path and Path(image_path).exists():
        image_b64 = base64.b64encode(Path(image_path).read_bytes()).decode("ascii")

    project_brief = load_project_context()
    # Append a *live* inventory listing every time so newly-created assets
    # show up to the next debate. Roles that decide whether to create new
    # assets (set_manager/production_designer/director) need this most;
    # we attach for everyone since it's also useful evaluation context.
    project_brief = project_brief + "\n\n" + load_existing_inventory()

    history = []
    rounds_out = []

    for n in range(1, rounds + 1):
        is_final = (n == rounds)
        max_tok = 1400 if is_final else 400

        va = call_engine(
            voice_a_eng,
            _role_system(role, "קול א (מוביל)", is_final, mode),
            _round_user(role, question, context, history, "voice_a", "קול א", project_brief),
            image_b64 if n <= 2 else None,
            max_tokens=max_tok
        )
        vb = call_engine(
            voice_b_eng,
            _role_system(role, "קול ב (מאתגר)", is_final, mode),
            _round_user(role, question, context, history + [{"round": n, "voice_a": va, "voice_b": "", "moderator_summary": ""}], "voice_b", "קול ב", project_brief),
            image_b64 if n <= 2 else None,
            max_tokens=max_tok
        )
        mod = call_engine(
            mod_eng,
            _moderator_system(is_final),
            _moderator_user(n, va, vb, is_final, question, context, project_brief),
            None,
            max_tokens=1400 if is_final else 250
        )

        rd = {"round": n, "voice_a": va, "voice_b": vb, "moderator_summary": mod}
        rounds_out.append(rd)
        history.append(rd)
        print(f"    round {n}/{rounds} ok  (va={len(va)}c vb={len(vb)}c mod={len(mod)}c)")

    final = _parse_final(rounds_out[-1]["moderator_summary"])

    result = {
        "role": role,
        "scene_id": scene_id,
        "question": question,
        "context": context,
        "image_path": str(image_path) if image_path else None,
        "rounds": rounds_out,
        "final_decision": final
    }

    if save:
        target = Path(output_dir) if output_dir else DEBATES_DIR
        target.mkdir(parents=True, exist_ok=True)
        out = target / f"{role}_{scene_id}.json"
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"    saved: {out}")

    return result


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--role", required=True, choices=list(ASSIGNMENTS.keys()))
    ap.add_argument("--scene", required=True)
    ap.add_argument("--question", required=True)
    ap.add_argument("--context", default="")
    ap.add_argument("--image", default=None)
    ap.add_argument("--rounds", type=int, default=8)
    a = ap.parse_args()
    run_debate(a.role, a.scene, a.question, a.context, a.image, a.rounds)
