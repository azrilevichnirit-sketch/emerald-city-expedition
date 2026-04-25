# debate_protocol.md
# פרוטוקול דיון יצירתי — כל סוכן creative קורא לפני כל החלטה

---

## עיקרון יסוד

כל החלטה creative בחברה מתקבלת דרך דיון בין שני מוחות ומנחה.
לא במאי אחד מחליט לבד. לא מעצב אחד מחליט לבד.
הדיון הוא חלק מהתפקיד — לא תוספת.

---

## שיבוץ מנועים לפי תפקיד

| תפקיד | קול א (מוביל) | קול ב (מאתגר) | מנחה |
|--------|--------------|---------------|------|
| director | Claude API | Gemini API | OpenAI API |
| production_designer | Gemini API | Claude API | OpenAI API |
| set_manager | Gemini API | Claude API | OpenAI API |
| sound_designer | Claude API | Gemini API | OpenAI API |
| actor_director | Gemini API | Claude API | OpenAI API |
| editor | Claude API | Gemini API | OpenAI API |

**מפתחות API:**
- Claude: `ANTHROPIC_API_KEY`
- Gemini: `GEMINI_API_KEY`
- OpenAI: `OPENAI_API_KEY`

---

## לפני כל דיון — קריאת חובה

כל סוכן שמפעיל את הפרוטוקול חייב לקרוא:
1. `design_system.md` — חוקי עיצוב, zones, צבעים, נגישות
2. `content_lock.json` — תוכן נעול, אסור לשנות
3. `spec_logic_only.md` — לוגיקת המשחק, מה כל כלי עושה
4. הקובץ הרלוונטי מ-pipeline/ — brief, asset_manifest, pose_map

---

## מבנה הדיון — 8 סבבים

### סבבים 1-7

**קול א:**
- מציג עמדה בימאית/עיצובית מנומקת
- מתייחס לעמדת קול ב מהסבב הקודם (מסבב 2 ואילך)
- מנמק לפי: לוגיקת המשחק, חוויית השחקן, design_system

**קול ב:**
- מאתגר את עמדת קול א **רק כשיש בעיה אמיתית**
- **כיול (חשוב):** קול ב לא מאתגר בשביל לאתגר. אם הכלי/ההחלטה עוברת את כל 6 השאלות (ראו "6 שאלות חובה" למטה) — קול ב אומר **"מאושר, אין בעיה"** ולא ממציא הערות.
- מאתגר רק כאשר אחת מ-6 השאלות נכשלת: אינסטיקנט שם, הבחנה בשלישייה, לוגיקת סצנה, כיוון רגשי, מלכודות מודל, דירוג במדד.
- כשמאתגר — מציע כיוון חלופי או שיפור, מנמק ויזואלית/נרטיבית.

**מנחה (OpenAI):**
- מסכם את הפער שנותר בין השניים
- מציין מה מוסכם ומה עדיין שנוי במחלוקת
- לא מכריע עדיין — רק מנחה

### סבב 8 — סיום

**קול א:** עמדה סופית מנומקת

**קול ב:** עמדה סופית מנומקת

**מנחה (OpenAI) — סינתזה:**
- לוקח את הטוב משני הקולות
- כותב החלטה מנומקת
- **pass היא הכרעה לגיטימית ומלאה.** אל תכריח fix כאשר אין בעיה ממשית — אם שני הקולות מסכימים שהכלי עובד, ההחלטה pass.
- fix רק כשיש בעיה זוטרה אמיתית שנמצאה. redo רק כשהכלי נכשל ביסוד.
- אם יש פרט שלא נפתר — מסמן `"director_flag": true` עם הסבר
- כותב את ההחלטה ל-pipeline

---

## פורמט הפלט — pipeline/debate_[תפקיד]_[scene_id].json

```json
{
  "role": "director",
  "scene_id": "M1",
  "rounds": [
    {
      "round": 1,
      "voice_a": "...",
      "voice_b": "...",
      "moderator_summary": "..."
    }
  ],
  "final_decision": {
    "synthesis": "...",
    "decision": { },
    "director_flag": false,
    "flag_reason": null
  }
}
```

---

## חוקי ברזל בדיון

1. **אסור לשנות תוכן** — טקסטי משימות, שמות כלים, סדר כלים — נעולים
2. **אסור לסטות מdesign_system** — צבעים, zones, נגישות — לא לדיון
3. **אסור להמציא נכסים** — רק נכסים שקיימים ב-asset_manifest
4. **director_flag לא עוצר את הpipeline** — ממשיכים, מסמנים לבדיקה מאוחרת
5. **8 סבבים בלבד** — אין סבב 9, אין המשך. המנחה מכריע בסבב 8

---

## איך סוכן מפעיל את הפרוטוקול

```python
import anthropic
import google.generativeai as genai
from openai import OpenAI

def run_debate(role, scene_id, question, context):
    """
    role: "director" / "production_designer" / etc.
    question: ההחלטה הcreative שצריך לקבל
    context: כל המידע הרלוונטי (brief, assets, spec)
    """
    
    # שיבוץ לפי תפקיד
    ASSIGNMENTS = {
        "director":            ("claude", "gemini", "openai"),
        "production_designer": ("gemini", "claude", "openai"),
        "set_manager":         ("gemini", "claude", "openai"),
        "sound_designer":      ("claude", "gemini", "openai"),
        "actor_director":      ("gemini", "claude", "openai"),
        "editor":              ("claude", "gemini", "openai"),
    }
    
    voice_a_engine, voice_b_engine, moderator_engine = ASSIGNMENTS[role]
    
    history = []
    rounds = []
    
    for round_num in range(1, 9):
        is_final = (round_num == 8)
        
        # קול א
        voice_a = call_engine(
            voice_a_engine,
            build_prompt("voice_a", role, question, context, history, is_final)
        )
        
        # קול ב
        voice_b = call_engine(
            voice_b_engine,
            build_prompt("voice_b", role, question, context, history + [voice_a], is_final)
        )
        
        # מנחה
        if is_final:
            moderator = call_engine(
                "openai",
                build_synthesis_prompt(role, question, context, history, voice_a, voice_b)
            )
        else:
            moderator = call_engine(
                "openai",
                build_summary_prompt(round_num, voice_a, voice_b, history)
            )
        
        round_data = {
            "round": round_num,
            "voice_a": voice_a,
            "voice_b": voice_b,
            "moderator_summary": moderator
        }
        rounds.append(round_data)
        history.append(round_data)
    
    # חילוץ ההחלטה הסופית מסבב 8
    final = parse_final_decision(rounds[-1]["moderator_summary"])
    
    # שמירה ל-pipeline
    result = {
        "role": role,
        "scene_id": scene_id,
        "rounds": rounds,
        "final_decision": final
    }
    
    save_to_pipeline(role, scene_id, result)
    return final


def build_synthesis_prompt(role, question, context, history, voice_a, voice_b):
    return f"""
אתה מנחה של דיון creative בין שני {role}ים.
זהו סבב 8 — הסבב האחרון.

ההחלטה הנדרשת: {question}
הקשר: {context}

עמדה א (סבב 8): {voice_a}
עמדה ב (סבב 8): {voice_b}

היסטוריית הדיון: {history}

כתוב סינתזה שלוקחת את הטוב משתי העמדות.
פורמט הפלט (JSON בלבד):
{{
  "synthesis": "הסבר הסינתזה",
  "decision": {{}},
  "director_flag": false,
  "flag_reason": null
}}

אם יש פרט שלא נפתר — שנה director_flag ל-true והסבר ב-flag_reason.
"""
```

---

## מתי מפעילים את הפרוטוקול

כל סוכן creative מפעיל את הפרוטוקול כשיש:
- החלטה על ויזואל שאינה מכוסה ב-design_system
- בחירה בין שתי אפשרויות לגיטימיות
- כלי שנכשל בהבנה אינטואיטיבית
- staging וmיקום במסך
- תזמון שמשפיע על רגש
- כל שאלה שהתשובה לה היא "תלוי"

---

## ⚡ חוק הפעלה — Tools / Phase 0E

**הבמאי מפעיל דיון לפני ש-visual_prompt_writer כותב prompt לכל נכס.**
אין prompt לנכס — tool, background, scenery — ללא דיון מקדים שהבמאי פתח ואישר.

זה תוקן אחרי סיבובי גלשן_מ01 (8 ניסיונות) ו-מצנח_בסיס_מ11 (6 ניסיונות) שנגרמו מכיוון ויזואלי שלא עבר דיון לפני prompt.

---

## 🚫 Scope — מה הדיון **לא** דן בו

תוקן 2026-04-21 אחרי ש-round 1+2 של ה-audit חרגו ל-content_lock.

**הדיון על כלי עוסק אך ורק בשאלה אחת:**
> **האם התמונה של האייקון נקראת מיד בעברית כשמו של הכלי?**
>
> שחקן בבית רואה את האייקון → תוך שבריר שנייה אומר "זה X"? אם X == שם הכלי ב-content_lock → pass. אם לא → fail.

**הדיון אסור לו לגעת ב:**
1. **שמות כלים** — נעולים ב-content_lock. "בנג'י" נשאר "בנג'י". אל תציע "חבל ספיגה".
2. **התאמת כלי למשימה** — ההחלטה של Nirit. אל תשאל "האם מצלמה מתאימה למשימה בלחץ זמן?".
3. **לוגיקת scoring / psychological dimension** — נעולה. "סיכון/יציבות/FOMO/אימפולסיביות" של כל משימה — החלטת עיצוב משחק.
4. **slot ranking בשלישייה** — נעול. אם slot A=1pt ו-C=3pt, זה לא לדיון.
5. **מכניקת משחק** — "איך זה עובד" → שאלה לעיצוב המשחק, לא לציור.

**בזמן הדיון על כלי ויזואלי, 5 מתוך 6 השאלות המקוריות נופלות לתחום הנעול. נשארת רק שאלה 1 (אינסטיקנט שם עברי) + שאלה 2 (הבחנה ויזואלית בשלישייה, עדיין ויזואלית-טהורה).**

---

## 6 שאלות חובה בדיון על כלי (Tool / Visual Asset)

כל דיון על נכס ויזואלי חייב לענות בבירור על 6:

### 1. אינסטיקנט שם עברי
> מה השם בעברית מעורר **מיד** בראש השחקנית בבית?

- אם "גלשן" → לוח שעומדים עליו, לא כנף מעל.
- אם "זיקוק" → חגיגה צבעונית, לא טיל.
- אם יש פער בין האינסטיקנט למציאות — **האינסטיקנט מנצח.** חופש בימאי.
- ראו: `memory/feedback_tool_intuitive_identification.md`

### 2. הבחנה ויזואלית בשלישייה
> איך הכלי הזה שונה **ויזואלית** מ-2 האחרים באותה משימה?

השחקנית רואה שלושה כלים ליד זה בתיק. אם שניים דומים בצורה — היא מתבלבלת.
- דרשו **צורה/צבע/זווית/אלמנט-חתימה** שונים לכל אחד.
- דוגמה ממ11: סנפלינג (חבל מגולגל) / בנג'י (חבל מתוח-אלסטי) / מצנח (כיפה פרושה) — שונים לחלוטין.

### 3. לוגיקת הסצנה
> מה `spec_logic_only.md` אומר על **תפקיד הכלי** בסצנה?

- איזה מדד? (סיכון/יציבות/FOMO/אימפולסיביות)
- איזה slot? (1=הכי בטוח, 3=הכי נועז)
- איך השחקנית משתמשת בו בפועל? (wear/use/deploy/hold — content_lock)

### 4. כיוון רגשי / קולנועי
> מה התחושה שהסצנה יוצרת דרך הכלי?

לא תיאור טכני — **כיוון בימאי.** "אדרנלין הקפיצה", "מתח של בחירה בלחץ זמן", "תעלומה מיסטית".
זה מה ש-visual_prompt_writer צריך לתרגם ל-lighting/color/angle.

### 5. מלכודות ברירת-מחדל של המודל
> מה המודל עשוי לצייר אוטומטית שיפספס את הכוונה?

- זיקוק → ייצוייר על שמיים לילה (chroma-key נכשל) → ציין "DAYLIGHT STUDIO"
- מצנח/גלשן → אדם בפנים → ציין "no pilot, no person, no harness"
- כלי קטן בפריים → proportions צרות → ציין "square 1:1 composition fills frame"
- כלי אקדח → looks industrial/stapler → ציין aesthetic (steampunk/adventure)

### 6. דירוג במדד
> האם האינסטיקנט קורא נכון את מיקום הכלי בסולם 1→2→3?

3 צריך להראות **יותר נועז/מיומן/קיצוני** מ-1, ויזואלית.
אם טפרי-טיפוס נראים "בסיסיים" יותר מסולם-חבלים — יש בעיה ויזואלית במדרג.

---

## 4 שאלות לדיון על סצנה (לא כלי)

לדיוני scene_brief, במקום 6 השאלות של Tool:

1. **first_focus** — לאן העין של השחקנית בבית הולכת ברגע שנכנסת הסצנה?
2. **feel** — מה התחושה במשפט אחד? (לא "דרמטי" — "פאניקה מבוקרת של נפילה חופשית")
3. **מעבר מהסצנה הקודמת** — מה ממשיך, מה משתנה ברגש?
4. **מלכודות של consequence type** — wear/use/deploy/hold — מה קורה אחרי שנבחר הכלי? האם הרקע/pose תומך?

---

## סוכנים שכן creative (מפעילים דיון)
director, production_designer, set_manager, sound_designer, actor_director, editor

## סוכנים שלא creative (מקבלים directive, לא מפעילים דיון)
visual_prompt_writer, image_generator, builder, content_validator, qa, human_review, script_supervisor, folder_organizer

**Visual Prompt Writer מקבל directive — לא מחליט לבד.**

---

## כלל זהב

**אם אין debate_log — אין prompt. אם אין prompt — אין נכס. אם אין נכס — אין סצנה.**
הפרודקשן עוצרת, ולא בעלויות של 8 סיבובי תיקון אחר כך.
