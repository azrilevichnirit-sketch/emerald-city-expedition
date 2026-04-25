# Studio Emerald — Executive Producer

---

## ⚠️ קריאת חובה לכולם לפני הכל
`design_system.md` + `content_lock.json`

## ⚠️ כל סוכן creative — לפני כל החלטה
קרא `agents/debate_protocol.md` והפעל את הדיון.
סוכנים creative: director, production_designer, set_manager, sound_designer, actor_director, editor.

---

## צוות החברה

| סוכן | קובץ | תפקיד |
|------|------|-------|
| מעצב פרודקשן | agents/production_designer.md | Camera Bible, style |
| מנהל שחקנים | agents/actor_director.md | segment map, poses |
| במאי | agents/director.md | ויזואל, feel, העמדה |
| תסריטאי | agents/script_supervisor.md | טקסט verbatim + קול |
| מנהל סט | agents/set_manager.md | props, תפאורה |
| מעצב סאונד | agents/sound_designer.md | ambient, events |
| Visual Prompt Writer | agents/visual_prompt_writer.md | prompts לנכסים |
| Image Generator | agents/image_generator.md | Leonardo API |
| Builder | agents/builder.md | HTML/CSS/JS |
| עורך | agents/editor.md | תזמון, מעברים |
| Content Validator | agents/content_validator.md | verbatim check |
| QA | agents/qa.md | visual + code |
| Human Review | agents/human_review.md | בדיקת עין — חובה |

---

## חוקי ברזל

1. content_lock.json — נעול. אף אחד לא כותב לכאן
2. design_system.md — חוק פיזיקה. אין יוצא מן הכלל
3. Builder לא קורא spec — רק brief
4. אין דילוג על Human Review
5. אין video.loop = true — תמיד segment loop
6. אין זהב בשום מקום
7. סוכן שנתקע — עוצר ומדווח. לא מנחש
8. visual_prompt_writer לא כותב prompt ללא debate_log מאושר. הבמאי מפעיל את הדיון — ראה `agents/debate_protocol.md`

---

## Pipeline מלא

### פאזה 0 — הכנת תשתית (פעם אחת)

שלב 0A — סידור תיקיות
  קרא: agents/folder_organizer.md
  פלט: assets/ מסודר

שלב 0B — סריקת נכסים
  פלט: pipeline/asset_manifest.json

שלב 0C — segment map
  Agent: מנהל שחקנים
  פלט: pipeline/pose_map.json
  STOP: Human Review — timestamps

שלב 0D — Camera Bible + Style Test
  Agent: מעצב פרודקשן
  פלט: pipeline/camera_bible.json
  STOP: Human Review — אישור סגנון

שלב 0E — 44 כלים
  במאי → debate (agents/debate_protocol.md) — 6 שאלות לכל כלי
  Agent: Visual Prompt Writer + Image Generator — רק לפי directive מה-debate_log
  STOP: Human Review — כל כלי בנפרד

### פאזה 1 — לכל סצנה (32 פעמים)

  במאי → scene_brief
  תסריטאי → scene_script
  מנהל סט → set_list
  מעצב סאונד → sound_design
  Builder → scene_[ID].html
  STOP: Human Review — בדיקת עין
  Content Validator → אם נכשל: Builder מתקן
  עורך → אם יש issues: Builder מתקן
  QA → אם נכשל: Builder/Visual Prompt Writer מתקנים
  סצנה מאושרת ✅
