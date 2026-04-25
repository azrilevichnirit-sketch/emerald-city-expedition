"""Full-pipeline re-do for מצלמה_זעירה_מ10 — per agents/debate_protocol.md.

Stages:
  1. Director opens pre-generation debate (mode='design')
     → produces directive_to_prompt_writer
  2. visual_prompt_writer (Claude) translates directive → Imagen prompt
  3. image_generator (Imagen 4) renders
  4. chroma-key to pure green
  5. QA (Gemini vision) — does image read as 'endoscopic probe camera'?
  6. Director review (Claude vision) — final gate
  7. Only if QA + director both pass → replace in assets/tools_final/
     Otherwise → save all artifacts, DO NOT replace, report back.

Artifacts:
  pipeline/debates/pregen_production_designer_מצלמה_זעירה_מ10.json
  pipeline/prompts/מצלמה_זעירה_מ10_rD.txt
  pipeline/review/tools_qa_gemini/מצלמה_זעירה_מ10_rD_raw.png
  pipeline/review/tools_qa_gemini/מצלמה_זעירה_מ10_rD_final.png
  pipeline/review/qa/מצלמה_זעירה_מ10_rD_qa.json
  pipeline/review/director/מצלמה_זעירה_מ10_rD_director.json
  pipeline/review/מצלמה_זעירה_מ10_pipeline_summary.json
"""
import base64
import json
import urllib.request
import io
import time
from pathlib import Path
from PIL import Image
import numpy as np

from debate_runner import (
    run_debate, call_claude, call_gemini,
    GEMINI_KEY, CLAUDE_KEY, OPENAI_KEY
)

PROJECT = Path(__file__).resolve().parent.parent
KEY_FILE = PROJECT / "keys" / "gimini_key - Copy" / "key.txt"
FINAL_DIR = PROJECT / "assets" / "tools_final"
REVIEW_DIR = PROJECT / "pipeline" / "review" / "tools_qa_gemini"
QA_DIR = PROJECT / "pipeline" / "review" / "qa"
DIRECTOR_DIR = PROJECT / "pipeline" / "review" / "director"
PROMPTS_DIR = PROJECT / "pipeline" / "prompts"
DEBATES_DIR = PROJECT / "pipeline" / "debates"

for d in (REVIEW_DIR, QA_DIR, DIRECTOR_DIR, PROMPTS_DIR, DEBATES_DIR):
    d.mkdir(parents=True, exist_ok=True)

API_KEY_GEMINI = KEY_FILE.read_text(encoding="utf-8").strip()
IMAGEN_MODEL = "imagen-4.0-generate-001"
CHROMA = np.array([0, 0xB1, 0x40], dtype=float)

SLUG = "מצלמה_זעירה_מ10"


# -------------------- Step 1: Director debate (pre-gen, design mode) --------------------

DEBATE_QUESTION = (
    f"מה ה-directive הויזואלי לאייקון של הכלי '{SLUG}' (מצלמה זעירה, M10, slot A), "
    "כך שתצפית של שחקנית בבית באייקון תגרום לה לומר מיד 'מצלמה לחקירה/עינית' ולא "
    "'מצלמת סטילס' ולא 'סמארטפון'? פרט: צורה, חומר, צבע, זווית, אלמנט-חתימה, "
    "והבחנה ויזואלית משמיכת מיגון (slot B) וקאטר (slot C)."
)

DEBATE_CONTEXT = (
    "כלי: מצלמה זעירה (content_lock: 'מצלמה זעירה', slug=מצלמה_זעירה_מ10, slot A, 1pt).\n"
    "**כוונת Nirit (הגדרה מפורשת):** זו מצלמת endoscope/borescope רפואית — "
    "עינית זעירה על קצה ידית ארוכה ודקה, שנועדה להציץ לחלל סגור. כמו הכלי בניתוח "
    "שבודק בתוך הגוף. הכלי מיועד לחקור בתוך תיבה שחורה מתקתקת במקום לפעול. "
    "**אסור** לעצב מצלמת צילום רגילה / סטילס / סמארטפון / dSLR.\n\n"
    "משימה M10: בתרחיש משחקי של תיבה מתקתקת. סלוט A = האופציה לחקור במקום לפעול.\n"
    "שלישייה: A=מצלמה זעירה / B=שמיכת מיגון / C=קאטר לחיתוך חוטים.\n"
    "הבחנה נדרשת: B = בד פרוש גדול עם סרט אזהרה, C = כלי יד עם להב חיתוך. "
    "האייקון של A צריך להראות שונה מ-B וC.\n\n"
    "Scope: השם 'מצלמה זעירה' נעול. התאמת הכלי למשימה נעולה. הדיון ויזואלי בלבד — "
    "מה צריך להיצבע בפריים כדי שהשחקנית תזהה מיד 'עינית חקירה'."
)


def step1_debate():
    print("=" * 60)
    print("STEP 1 — Director opens pre-generation debate (design mode)")
    print("=" * 60)
    result = run_debate(
        role="production_designer",
        scene_id=f"pregen_{SLUG}",
        question=DEBATE_QUESTION,
        context=DEBATE_CONTEXT,
        image_path=None,
        rounds=8,
        output_dir=str(DEBATES_DIR),
        mode="design"
    )
    synthesis = result["final_decision"].get("synthesis", "")
    fix_notes = result["final_decision"].get("fix_notes", "")
    directive = (synthesis + "\n\nפרטים: " + fix_notes).strip()
    print(f"\nDirective extracted (len={len(directive)}):\n{directive[:500]}...\n")
    return directive, result


# -------------------- Step 2: visual_prompt_writer (Claude) --------------------

VPW_SYSTEM = (
    "אתה visual_prompt_writer של Studio Emerald. אתה מקבל directive יצירתי "
    "ומתרגם אותו ל-prompt באנגלית ל-Google Imagen 4. לא מוסיף יצירתיות משלך — "
    "מבצע את ה-directive. הפורמט הסטנדרטי של הסטודיו כולל:\n"
    "- 'A single heroic cinematic adventure-game inventory icon of <ITEM>'\n"
    "- Square 1:1 composition filling frame\n"
    "- Pure #00B140 chroma-key green studio background (flat solid, no gradients)\n"
    "- No text/numbers/letters/human hands\n"
    "- AAA painterly semi-realistic adventure-game icon art\n"
    "- Specific angle, lighting, color palette per directive\n"
    "- Negative prompts: explicitly exclude misreadings (e.g. 'NOT a smartphone')\n\n"
    "פלט: אך ורק ה-prompt באנגלית, ללא טקסט עברי סביב."
)


def step2_write_prompt(directive):
    print("=" * 60)
    print("STEP 2 — visual_prompt_writer (Claude) translates directive → Imagen prompt")
    print("=" * 60)
    user = (
        f"Directive מה-debate:\n{directive}\n\n"
        f"כלי: {SLUG} — מצלמה זעירה (endoscopic/borescope probe camera).\n"
        f"הוצא prompt מלא לImagen. כלול negative prompts במפורש כדי למנוע "
        f"מצלמת סטילס/סמארטפון/dSLR."
    )
    prompt = call_claude(VPW_SYSTEM, user, max_tokens=800)
    prompt = prompt.strip()
    if prompt.startswith("```"):
        # Strip code fences if Claude added them
        lines = [l for l in prompt.split("\n") if not l.strip().startswith("```")]
        prompt = "\n".join(lines).strip()
    prompt_file = PROMPTS_DIR / f"{SLUG}_rD.txt"
    prompt_file.write_text(prompt, encoding="utf-8")
    print(f"\nPrompt saved: {prompt_file}")
    print(f"Prompt ({len(prompt)} chars):\n{prompt[:500]}...\n")
    return prompt


# -------------------- Step 3+4: Imagen + chroma --------------------

def step3_imagen(prompt):
    print("=" * 60)
    print("STEP 3 — image_generator (Imagen 4)")
    print("=" * 60)
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
           f"{IMAGEN_MODEL}:predict?key={API_KEY_GEMINI}")
    body = {"instances": [{"prompt": prompt}],
            "parameters": {"sampleCount": 1, "aspectRatio": "1:1"}}
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                  headers={"Content-Type": "application/json"},
                                  method="POST")
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    raw = base64.b64decode(data["predictions"][0]["bytesBase64Encoded"])
    raw_file = REVIEW_DIR / f"{SLUG}_rD_raw.png"
    raw_file.write_bytes(raw)
    print(f"Raw: {raw_file}")
    return raw


def step4_chroma(raw_bytes):
    print("=" * 60)
    print("STEP 4 — chroma-key")
    print("=" * 60)
    img = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
    arr = np.array(img).astype(float)
    bg = arr[:30, :30].reshape(-1, 3).mean(axis=0)
    dist = np.linalg.norm(arr - bg, axis=2)
    mask = np.clip((dist - 25) / 35, 0, 1)
    a = mask[..., None]
    comp = (arr * a + CHROMA * (1 - a)).clip(0, 255).astype(np.uint8)
    final_file = REVIEW_DIR / f"{SLUG}_rD_final.png"
    Image.fromarray(comp).save(final_file)
    print(f"Final: {final_file}")
    return final_file


# -------------------- Step 5: QA (Gemini vision) --------------------

def step5_qa(final_file, directive):
    print("=" * 60)
    print("STEP 5 — QA (Gemini vision)")
    print("=" * 60)
    img_b64 = base64.b64encode(final_file.read_bytes()).decode("ascii")
    system = (
        "אתה QA של Studio Emerald. בדוק האם האייקון הויזואלי נקרא מיד בתור "
        "הכלי המיועד. עברית בלבד. החזר JSON בלבד."
    )
    user = (
        f"הכלי: '{SLUG}' — מצלמה זעירה (endoscopic/borescope probe camera, "
        f"עינית על ידית דקה לחקירת חלל סגור. **לא** מצלמת סטילס/סמארטפון).\n\n"
        f"Directive: {directive}\n\n"
        "שאלה יחידה: כשאת מסתכלת על האייקון המצורף, את קוראת מיד 'עינית/מצלמת "
        "חקירה רפואית' (pass) או שזה נראה כמצלמה אחרת (fail)?\n\n"
        'החזר JSON בלבד: {"verdict": "pass"|"fail", "reason": "...", '
        '"reads_as": "<מה שנקרא בפועל>"}'
    )
    result_text = call_gemini(system, user, image_b64=img_b64, max_tokens=400)
    import re
    m = re.search(r"\{.*\}", result_text, re.S)
    try:
        result = json.loads(m.group(0) if m else result_text)
    except Exception:
        result = {"verdict": "fail", "reason": "could not parse QA output",
                  "reads_as": result_text[:200]}
    result["raw"] = result_text
    qa_file = QA_DIR / f"{SLUG}_rD_qa.json"
    qa_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"QA verdict: {result.get('verdict')} — reads as: {result.get('reads_as')}")
    print(f"QA file: {qa_file}")
    return result


# -------------------- Step 6: Director review (Claude vision) --------------------

def step6_director(final_file, directive):
    print("=" * 60)
    print("STEP 6 — Director review (Claude vision)")
    print("=" * 60)
    img_b64 = base64.b64encode(final_file.read_bytes()).decode("ascii")
    system = (
        "אתה הבמאי של Studio Emerald. שער אחרון לפני שה-asset מגיע לNirit. "
        "דרוש: שהאייקון ייקרא מיד כשם הכלי. עברית בלבד. החזר JSON בלבד."
    )
    user = (
        f"כלי: '{SLUG}' — מצלמה זעירה (endoscopic probe).\n"
        f"Directive שהודפס על ידי קבוצת production_designer: {directive}\n\n"
        "בדיקה: כשאת מסתכלת על האייקון, האם הוא קריא כ-'עינית חקירה'? "
        "האם מובחן מ-B (שמיכת מיגון) ו-C (קאטר)? האם איכות Studio Emerald נשמרת?\n\n"
        'החזר JSON: {"verdict": "pass"|"fail", "reason": "...", '
        '"visual_readability": "...", "differentiation": "...", "notes": "..."}'
    )
    result_text = call_claude(system, user, image_b64=img_b64, max_tokens=1400)
    import re
    m = re.search(r"\{.*\}", result_text, re.S)
    try:
        result = json.loads(m.group(0) if m else result_text)
    except Exception:
        result = {"verdict": "fail", "reason": "could not parse director output",
                  "notes": result_text[:200]}
    result["raw"] = result_text
    director_file = DIRECTOR_DIR / f"{SLUG}_rD_director.json"
    director_file.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Director verdict: {result.get('verdict')}")
    print(f"Director file: {director_file}")
    return result


# -------------------- Step 7: Finalize --------------------

def step7_finalize(final_file, qa_result, director_result, directive):
    print("=" * 60)
    print("STEP 7 — Finalize")
    print("=" * 60)
    both_pass = qa_result.get("verdict") == "pass" and director_result.get("verdict") == "pass"
    summary = {
        "slug": SLUG,
        "qa_verdict": qa_result.get("verdict"),
        "qa_reason": qa_result.get("reason"),
        "qa_reads_as": qa_result.get("reads_as"),
        "director_verdict": director_result.get("verdict"),
        "director_reason": director_result.get("reason"),
        "director_notes": director_result.get("notes"),
        "both_pass": both_pass,
        "final_png": str(final_file),
        "replaced_in_tools_final": False
    }
    if both_pass:
        target = FINAL_DIR / f"{SLUG}.png"
        target.write_bytes(final_file.read_bytes())
        summary["replaced_in_tools_final"] = True
        print(f"✅ BOTH PASS — replaced: {target}")
    else:
        print(f"⚠️  NOT both pass — file NOT replaced. qa={qa_result.get('verdict')}, director={director_result.get('verdict')}")
    sum_file = PROJECT / "pipeline" / "review" / f"{SLUG}_pipeline_summary.json"
    sum_file.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Summary: {sum_file}")
    return summary


def main():
    t0 = time.time()
    directive, debate_result = step1_debate()
    prompt = step2_write_prompt(directive)
    raw = step3_imagen(prompt)
    final = step4_chroma(raw)
    qa = step5_qa(final, directive)
    director = step6_director(final, directive)
    summary = step7_finalize(final, qa, director, directive)
    print(f"\ntotal: {time.time()-t0:.0f}s")
    return summary


if __name__ == "__main__":
    main()
