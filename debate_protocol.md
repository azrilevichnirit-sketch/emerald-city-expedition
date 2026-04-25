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
- מאתגר את עמדת קול א
- מציע כיוון חלופי או שיפור
- לא דוחה סתם — מנמק ויזואלית/נרטיבית

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
