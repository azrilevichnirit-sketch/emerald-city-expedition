# HANDOFF — לקרוא לפני כל פעולה אחרת בסשן הבא

תאריך אחרון: 2026-04-26 (לפנות בוקר)
משתמשת: נירית — סגרה מחשב, חוזרת בעוד כמה שעות
גיט: `C:\emerald` על `main`, לאחרונה `5a83d0c` ב-`origin/main`

---

## מה כבר נעשה (אל תחזור על זה)

### Commit `5a83d0c` — fix(layout)
תיקון רגרסיה ב-15/15 קבצי `pipeline/builder_html/M*.html`:
- `#zone-a` → `background:transparent;pointer-events:none` (היה `#1a1a1a`, פס אטום עליון שהסתיר את הסצנה)
- `#zone-b` → `top:0;height:60vh` (היה `top:6vh;height:54vh`)
- `#zone-a .score` → נוסף `text-shadow` כדי שניקוד יישאר קריא על רקע שקוף
- סקריפט: `pipeline/fix_layout_all.py` (deterministic regex replace)

### Commit `37182f4` — orchestrator output
M2-M15 + `_finale.html` נבנו לפי V6: 14 משימות חדשות + סצנת סיום, כולן עם:
- bg-phase-1/2 כ-`<video autoplay muted playsinline>` (בלי loop)
- pose tracks: running_entry → standing_wait → catch_one_shot → jump_css_overlay → landing
- 3 כלים per משימה עם palm anchor `point_on_player_pct:{x:40,y:32}`
- localStorage cross-mission: `emerald_score` + `emerald_progress`
- M15 מפנה ל-`./_finale.html`

### Commit `acab3e2` — M1 v6 (אדנייה לפני כל הסשן הזה)
M1.html מקורי, אמיתי, יציב.

### אומת בסשן הזה (אל תבדוק שוב)
- 70 unique asset references — כל הרקעים, סצנריה, 45 כלים, 7 פוזות **קיימים בדיסק**
- 15/15 קבצי HTML עברו את regex fixes (grep אישר `background:transparent` + `top:0` + `height:60vh`)

---

## מה עדיין פתוח — 3 משימות

### 1. M14/M15 pose narrative mismatch
**הבעיה**: M14 (מקדש/עיר) ו-M15 (סיום) משתמשים ב-pose tracks שהועתקו מ-M1 (running→standing→catch→jump→landing). זה לא מתאים נרטיבית.
**הפתרון המוצע**: לקרוא `pipeline/pose_keyframes/_pose_map.json` (אם קיים) או `pose_composition_map.json`, לבחור פוזות שמתאימות ל"הגעה לעיר" ול"ניצחון/סיום". כנראה pose_07 לעמידת ניצחון, פוזה איטית למקום ריצה.
**איפה לערוך**: `pipeline/builder_html/M14.html` שורות ~75-80, `M15.html` שורות ~75-80 ב-`PAYLOAD.tracks`.

### 2. בדיקה רספונסיבית
**מה צריך**: לבדוק 15 משימות ב-3 viewports — 360px (טלפון), 768px (טאבלט), 1440px (דסקטופ).
**איך**: יש MCP server `mcp__Claude_Preview__*` (preview_start, preview_resize, preview_screenshot). מומלץ להפעיל סוכן ייעודי במקביל למשימה 1.
**מה לחפש**: overflow אופקי, אלמנטים שיוצאים מהמסך, טקסט שנחתך, כפתורי כלים שלא נראים, scaling של player canvas.

### 3. Spot-check ויזואלי 15 סצנות
**מה צריך**: לפתוח כל משימה בסיקוונס, לוודא:
- (a) רקע מנגן ואז עוצר על פריים אחרון
- (b) שחקנית מצוירת על canvas עם chroma-key (לא ירוק על השוליים)
- (c) 3 הכלים מופיעים אחרי טקסט המשימה
- (d) לחיצה על כלי = הוא עף לכף יד של השחקנית
- (e) אחרי לחיצה: jump → landing → צ'קפוינט → fade → המשימה הבאה
- (f) ב-M15: fade מוביל ל-`_finale.html` שמראה ניקוד

**איך**: dispath `general-purpose` agent עם access ל-Claude Preview MCP.

---

## כלים זמינים בסשן הבא

- `Bash` ב-Git Bash, CWD ברירת מחדל הוא ה-worktree אבל `cd /c/emerald` עובד
- `Edit`/`Read`/`Write` ב-paths מוחלטים של Windows (`C:\emerald\...`)
- `Grep`/`Glob` לחיפוש בקוד
- `Agent` עם sub-types: `general-purpose`, `Plan`, `Explore`
- MCP servers: `Claude_Preview` (פתיחת ה-HTML בדפדפן headless), `Claude_in_Chrome`

---

## כשנירית כותבת "תמשיכי":

1. **קודם כל**: קרא את הקובץ הזה.
2. **שנית**: `cd /c/emerald && git log --oneline -5` כדי לוודא שהמצב לא השתנה (אם יש commit חדש שהיא או מישהו אחר עשו בינתיים, עדכן את ההנדאוף).
3. **שלישית**: dispatch 3 sub-agents במקביל למשימות 1+2+3.
4. **לא לשאול אותה שאלות**. היא אמרה שלוש פעמים שהיא עייפה ולא רוצה להתערב. תקבל החלטות, תבצע, תדווח בסוף.
5. **לא להגיד "מצגת"** — רק "דמו".
6. **לא לקצר את האיכות** — V6 לכל 15 המשימות, אין "גרסה פשוטה".

---

## חובת ברזל מהזיכרון של נירית

- **הכל סטטי** — אין loop, אין autoplay מתמשך. seek+pause + chroma-key על פריים סטטי.
- **חברת ההפקה הכינה את כל הנכסים** — אסור לייצר תמונות/וידאו חדשים. רק לערוך קיימים.
- **visual_editor agent** קיים ב-`agents/visual_editor.md` — להפעיל אותו אם יש שאריות chroma ירוקות.
- **כל סוכן רואה את כל הקונטקסט** — לא לתת slug-only. לטעון `content_lock`, `pose_map`, `camera_bible`, `asset_manifest` בכל invocation.
