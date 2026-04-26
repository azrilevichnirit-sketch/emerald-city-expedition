# Studio Emerald — Team Context (חובה לקריאה לכל סוכן)

**הסשן הזה הופעל מחדש מאפס.** הסיבה: בכל הניסיונות הקודמים סוכנים פעלו בבידוד וב-orchestrator טמפלטי. נירית דרשה: "הסוכנים חייבים לעבוד טוב ולהיות בהרמוניה. כולם יודעים את התפקיד של כולם".

---

## 1. הצוות וצינור ההפקה

| שלב | סוכן | קלטים | פלט | למי הפלט הולך |
|------|------|-------|-----|----------------|
| 1 | director | content_lock, scene_brief קודם, design_system | scene_brief_static_M{N}.json | script_supervisor + set_manager + actor_director + sound_designer + builder |
| 2 | script_supervisor | content_lock (M{N}), scene_brief | scene_script_M{N}.json | builder |
| 3 | set_manager | scene_brief, asset_manifest, camera_bible, scenery folders | set_list_M{N}.json | builder |
| 4 | actor_director | scene_brief, master_player, player/anim_*, pose_map | pose_map_M{N}.json | builder |
| 5 | sound_designer | scene_brief, content_lock | sound_design_M{N}.json | builder |
| 6 | visual_editor | תמונות מקור עם רקע לבן/ירוק | תמונות עם alpha | set_manager + builder |
| 7 | builder | כל הפלטים מ-1-6 | builder_html_static/M{N}.html | human_review |
| 8 | content_validator | content_lock (verbatim) | pass/fail report | builder אם fail |
| 9 | editor | scene HTML, scene_brief timing | issues report | builder אם fail |
| 10 | qa | scene HTML, design_system | pass/fail report | builder אם fail |
| 11 | human_review | רנדור של scene בדפדפן | approved/rejected | producer (= the orchestrator) |

---

## 2. חוקי ברזל (אסור לפרש מחדש)

1. **STATIC = תמונת PNG אחת קפואה לדמות.** לא וידאו עם seek+pause. לא לופ. לא RAF clamp. כשרוצים שינוי tiny (catch reaction), משתמשים ב-PNG שני שמתחלף ב-`<img src=>` reassignment, לא בוידאו.
2. **content_lock.json נעול.** אסור לכתוב לכאן. קריאה verbatim של mission_text, checkpoint_text, tools labels.
3. **design_system.md הוא חוק פיזיקה.** zones (a/b/c/d), צבעים, RTL, viewport `width=device-width, initial-scale=1.0`.
4. **chroma key #00B140** רק אם תמונה ירוקה. ל-`master_player/*.png` — רקע לבן, צריך alpha extraction (visual_editor).
5. **אין זהב בשום מקום** (color rule).
6. **אין video.loop=true.** Browser-native loop על background OK בלבד; player = `<img>`.
7. **כשסוכן נתקע — עוצר ומדווח. לא מנחש.**
8. **לפני כל החלטה creative — debate_protocol.md** (6 שאלות חובה).

---

## 3. התיקיות הנכונות (CRITICAL — לא להחליף)

```
C:\emerald\
├── master_player/                ← תמונת PNG קנונית של נירית
│   ├── niritazr_*.png           ← מקור (white bg, 976KB)
│   └── nirit_alpha.png          ← אחרי visual_editor (alpha, מוכן ל-overlay)
│
├── player/                       ← אנימציות עם שמות סמנטיים (NEW canonical)
│   ├── anim_waiting.mp4          ← המתנה (idle)
│   ├── anim_running.mp4          ← ריצה
│   ├── anim_reach_forward.mp4    ← הושטת יד (catch)
│   ├── anim_crouch.mp4           ← כיפוף (landing)
│   ├── anim_look_around.mp4
│   ├── anim_climbing.mp4
│   └── master_reference.png      ← reference still
│
├── poses_video/list.txt          ← spec של ה-poses הנדרשים (קרא לפני בחירת pose)
│
├── assets/player/pose_*.mp4      ← ⚠️ OLD numerical files. לא להשתמש בהם בבילד החדש.
│
├── backgrounds/                  ← phase-2/named bgs
│   ├── bg_jungle_clearing.mp4    ← M1 phase 2 (landing)
│   ├── bg_jungle_path.mp4
│   ├── bg_jungle_night_storm.mp4
│   ├── bg_temple.mp4
│   ├── bg_cave.mp4
│   ├── bg_cliff.mp4
│   ├── bg_river_shore.mp4
│   ├── bg_airplane.mp4
│   ├── bg_gate.mp4
│   └── bg_jungle_loop2.mp4
│
├── assets/backgrounds/           ← per-mission bgs (bg_M{N}.mp4)
│   └── bg_M1.mp4 ... bg_M15.mp4 (וגם bg_02, bg_03, bg_04 legacy)
│
├── rivals/                       ← מתחרים נפרדים (felt-not-seen, not in main composition)
│   ├── parachute_blue_top.png
│   ├── rival_female_run_1..4.png
│   └── rival_male_run_1..4.png
│
├── scenery/                      ← scenery legacy (some M1 references this directly)
│   └── two_jungle_trees.png
│
├── assets/scenery/               ← scenery main folder per mission
│   └── (~58 files, named per scene)
│
├── assets/tools/                 ← 45 כלים (3 per mission)
│   └── *.png (Hebrew filenames per content_lock)
│
├── effects/                      ← אפקטים לפעולות (rain, smoke, parachute, etc.)
│   ├── parachute_loop.mp4
│   ├── rain_effect_loop.mp4
│   └── ...
│
├── content_lock.json             ← נעול. mission_text + checkpoint_text + tools verbatim
├── design_system.md              ← physics
├── delivery_manifest.json        ← מה ההפקה כבר מסרה (138 assets, 80 optimized)
│
├── pipeline/
│   ├── _team_context.md          ← ⭐ הקובץ הזה (קרא ראשון)
│   ├── _handoff.md               ← מה היה לפני הסשן הזה (לא לפעול לפיו — outdated)
│   ├── content_lock.json         ← (אם לא בשורש)
│   ├── asset_manifest.json       ← מסך נכסים scaned
│   ├── pose_map.json             ← v2 pose map (יותר ישן)
│   ├── camera_bible.json         ← style+composition rules
│   ├── tool_consequence_map.json ← palm anchor x=40 y=32, attach geometries
│   ├── pose_composition_map.json ← v5 OUTDATED (multi-track timeline) — אסור להשתמש
│   ├── static_fallback/plan_M1.json ← producer's static plan v3 — REFERENCE ראשי לסטטי
│   ├── scene_briefs/scene_M{N}.json ← directors' briefs (interactive-movie version, partial)
│   ├── scene_compose/M{N}_composition.json ← compositor outputs
│   ├── builder_html/             ← ⚠️ builds ישנים (M1-M15) — לא נוגעים בהם
│   └── builder_html_static/      ← תיקיית היעד החדשה לבילדים סטטיים
│
└── agents/                       ← spec של כל סוכן (קרא את שלך לפני שאתה מתחיל)
    ├── director.md, script_supervisor.md, set_manager.md
    ├── actor_director.md, sound_designer.md, visual_editor.md
    ├── builder.md, editor.md, content_validator.md, qa.md
    ├── human_review.md, debate_protocol.md
    └── ...
```

---

## 4. הגדרת "סטטי" — נירית verbatim

> "אין בspec לופ, אתמול בלילה עודכן שהכל עובר לסטטי"
> "זה לא סטטי כי לפני כן יש לופ ווידיאו וריצות"

**משמעות מעשית**:
- **שחקנית = `<img src="master_player/nirit_alpha.png">`**. אין `<video>` לדמות.
- **רקע**: יכול להיות `<video autoplay loop muted>` של bg.mp4 (browser-native loop) — נירית לא התלוננה על רקע מתנגן ארוכות. יכול גם להיות תמונה סטטית (פריים שחולץ).
- **catch reaction**: PNG שני (אם נדרש) ב-`<img>` swap, לא segment של pose video.
- **tool flight**: אנימציה JS bezier (כלי עף לכף יד). זה היחיד שזז.
- **crossfade scene→scene**: 800ms opacity fade. המעבר היחיד.

---

## 5. ⚠️ ground truth — `pipeline/_spec_original.json` (NOT content_lock.json)

**קריטי**: `content_lock.json` שונה ללא הרשאה — מישהו כתב מחדש את הטקסטים מ"אנחנו/מה נבחר" ל"אני/איך אני מזנקת". נירית verbatim: "מישהו שינה את הטקסטים... אסור אסור אסור לגעת בטקסט".

**ה-source החדש לכל סוכן:**
- `C:\emerald\pipeline\_spec_original.json` — חולץ מ-`old/spec-emerald-city-expedition (1).md.txt` (UTF-16) שזה המקור של נירית
- מכיל לכל משימה: scene_setting, narrative (verbatim), question, tools[], expected_bg
- וגם: metrics_taxonomy, player_profiles, interface_rules

**אסור** לקרוא טקסטים מ-content_lock.json. אם אתה צריך mission_text — קח את `narrative` מ-_spec_original.json.

ל-M1 (דוגמה מ-_spec_original):
- narrative: "דלת המטוס נפתחת בבת אחת ורוח פרצים שואבת הכל החוצה. המתחרים כבר באוויר, הופכים לנקודות קטנות מעל הג'ונגל הירוק. הקרקע מתקרבת במהירות וחייבים לקפוץ עכשיו כדי לא לפספס את אזור הנחיתה."
- question: "איך נתקדם?"
- tools: A=מצנח עגול רחב (1pt), B=גלשן רחיפה (2pt), C=חליפת כנפיים (3pt)
- expected_bg: "airplane interior with view of sky+jungle below"

---

## 6. ה-Workflow לסשן הזה

### WAVE 1 (running now, parallel):
- visual_editor → `master_player/nirit_alpha.png`
- director M1 → `scene_briefs/scene_M1_static.json`

### WAVE 2 (after director M1 returns):
- script_supervisor M1 → `scene_scripts/scene_M1_static.json`
- set_manager M1 → `set_lists/set_list_M1_static.json` + composition.json
- actor_director M1 → `pose_map_M1_static.json` (איזה pose, איזה frame)
- sound_designer M1 → `sound_design_M1.json` (אם רלוונטי לסטטי)

### WAVE 3 (after WAVE 2 + visual_editor):
- builder M1 → `pipeline/builder_html_static/M1.html`

### WAVE 4 (after builder M1):
- content_validator M1 (verbatim check)
- editor M1 (timing check)
- qa M1 (visual+code)
- אם כל ה-3 PASS → human_review (Nirit) רנדור בדפדפן

### WAVE 5 (after Nirit approval of M1):
- ריצה במקביל של WAVE 2-4 ל-M2-M15

---

## 7-A. ⚠️ Continuous QA Supervisor — חובה

נירית: "וחייב להיות להם מישהו שכל הזמן בודק אותם".

**תפקיד חדש: `qa_supervisor`** — לא יושב בסוף הצינור, אלא **על כל handoff**:

| Handoff | qa_supervisor בודק |
|---------|--------------------|
| visual_editor → builder | האם הפלט (PNG) באמת נקי? פתח Read tool, תראה. אין שאריות? |
| director → set_manager | האם ה-brief מספיק קונקרטי? הוא מצביע על אסטים אמיתיים? |
| set_manager → builder | האם המיקומים הגיוניים נרטיבית? rivals במטוס = FAIL. |
| actor_director → builder | palm anchor אומת ויזואלית על ה-PNG הסופי? |
| editor → builder | timing events מתואמים? אין כפילויות? |
| builder → human_review | רץ בדפדפן בלי crash? כל הזונות מציגים? validators ירוקים? |

### qa_supervisor מבצע 3 פעולות בכל handoff:

1. **קריאה ויזואלית של הפלט**: Read tool על תמונות, screenshot של HTML
2. **Spec cross-check**: עבר על `_spec_original.json` כל הסעיפים הרלוונטיים, מצא הפרות
3. **Sanity check נרטיבי**: האם הפלט הזה אמיתי לסצנה? אם לא — חוזר לסוכן עם reason

### חוקי qa_supervisor

- **לא מאשר אוטומטית**. אם משהו לא בדוק — FAIL.
- **לא לוקח dependencies על trust**. כל פלט נבדק מחדש.
- **כותב ל-`pipeline/bug_catalog.md`** כל בעיה שתפס + מי גרם לה. הסוכן הבא בשרשרת לומד.
- **חוסם handoffs** עד שהבעיה תוקנה. orchestrator (Claude main) לא ממשיך לסוכן הבא בלי אישור qa_supervisor.

---

## 7. ⚠️ Professional Standards — קריטי

נירית verbatim: "החברת הפקה צריכה להבין שהם לא רובוטים שרק בודקים, אלא צריכים להכיר, להבין את התחום ולפעול כמקצוענים בתחום".

**אתה לא executor, אתה professional. מקצוען בתחום שלך.**

### חוקי התנהגות לכל סוכן

1. **חשוב לפני שאתה כותב**. הקלט לא מספיק. שאל את עצמך:
   - האם זה הגיוני נרטיבית? (set_manager: rivals בתוך מטוס = לא הגיוני)
   - האם זה הגיוני ויזואלית? (visual_editor: לבן בין רגליים = לא חולץ)
   - האם זה עוקב אחרי spec §X? (qa: spec §3 אומר "אין מספרים")
   - האם זה עומד בחוויית משתמש מקצועית?

2. **בדוק את הפלט שלך לפני handoff**. 
   - visual_editor: פתח את התמונה הסופית עם Read tool. תסתכל. יש שאריות? קצוות מסולסלים? לבן פנימי?
   - set_manager: דמיין את הסצנה הסופית. ה-props שאתה ממקם — האם הם קוהרנטיים?
   - builder: אם יש לך גישה לדפדפן, רנדר. אם לא, קרא את ה-HTML שלך מחדש כשחקן ושאל "האם זה ברור?"
   - qa: רנדר ב-Preview MCP. תפוס. בדוק overflow. בדוק תקלות.

3. **אתגר briefs חלשים**. אם ה-brief שקיבלת מ-upstream לא מספיק — אל תבצע בעיניים עצומות. דווח: "ה-brief חסר X. אני מציע Y". זה לא הפסקת זמן, זה protection.

4. **חשוב במונחים של נירית**. השפה שלה: "סטטי", "רספונסיבי", "מקצועי", "כלי שעובד". לא: "demo_minimal", "v5", "RAF clamp". אם אתה כותב termin רטוריים — היא לא תבין. אם אתה כותב במונחים שלה — היא יכולה לאמת.

5. **האחריות שלך לא נגמרת בכתיבת הקובץ**. היא נגמרת רק כשה-deliverable שלך נראה מקצועי בעיני נירית. אם משהו לא נראה מקצועי — זה כשל שלך, לא של builder, לא של orchestrator, לא של "שפה אחרת". שלך.

### דוגמאות לקפיצות מקצועיות שצפויות

- **visual_editor** מחלץ alpha: גם מהפינות וגם מכיסים פנימיים. בודק את התוצאה ב-Read אחרי ההרצה. אם יש שאריות — מתקן באותו run.
- **set_manager** ממקם props: בודק נרטיבית — האם הסצנה היא "פנים מטוס"? אם כן, rivals שצפים מחוץ לדלת = לא. אם הסצנה היא "אווירי", rivals בשמיים = כן. **לא ממקם prop "כי הוא קיים בתיקייה"**.
- **director** כותב brief: מתחיל מהשאלה "מה הסצנה צריכה להעביר רגשית?" לא "אילו זונים יש".
- **builder** מיישם: בסיום, פותח Preview, רנדר, מסתכל. אם משהו לא ברור — מתקן לפני handoff.
- **qa** מאשר: לא רק verbatim text. מסתכל על הסצנה ב-Preview. שואל "האם זה נראה כמו משחק מקצועי?"

### חובה: bug catalog

בכל סבב, סוכן שמוצא בעיה כותב אותה ל-`pipeline/bug_catalog.md` עם:
- מה הבעיה
- מי איתר אותה (איזה agent role)
- מה תוקן
- האם יש שורש שצריך לטפל גם בו

ככה אנחנו לומדים. הסבב הבא לא חוזר על אותן טעויות.

---

## 8. Important — communication between agents

כל סוכן בסיום עבודה חייב לכתוב **בנוסף לפלט הראשי**:
- שורה אחת ב-stdout: `READY: <agent_name> M{N} -> <output_path>`
- שדה `_consumed_inputs` בתוך הפלט: רשימת הקבצים שהוא קרא בפועל
- שדה `_handoff_to` בתוך הפלט: שמות הסוכנים הבאים בשרשרת

ככה ה-orchestrator (Claude main) יכול לעקוב.
