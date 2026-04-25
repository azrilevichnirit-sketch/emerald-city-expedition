# Folder Organizer — משימה ראשונה לפני הפקה

## מטרה
לסדר את כל הנכסים הקיימים לתוך מבנה תיקיות אחיד לפני שהpipeline מתחיל.

---

## מבנה היעד

```
assets/
├── backgrounds/      ← קבצי רקע: bg_*.mp4
├── player/           ← אנימציות שחקן: pose_*.mp4
├── tools/            ← כלי בחירה: *_מ01.png עד *_מ15.png
├── scenery/          ← אביזרי תפאורה סטטיים: *.png (לא כלים)
├── effects/          ← לולאות אפקט: *_loop.mp4
├── rivals/           ← יריבים: rival_*.png, parachute_blue_top.png
└── results/          ← תמונות תוצאה: אם קיימות
```

---

## הוראות לClauude Code

### שלב 1 — מיפוי מה קיים
```
סרוק את כל התיקיות בפרויקט.
צור קובץ: pipeline/folder_scan.json
מבנה:
{
  "scanned_at": "timestamp",
  "all_files": [
    { "current_path": "...", "filename": "...", "extension": "..." }
  ],
  "unrecognized": []
}
```

### שלב 2 — סיווג לפי שם קובץ
השתמש בחוקים הבאים לסיווג:

| תבנית שם | תיקיית יעד |
|----------|------------|
| `bg_*.mp4` | `assets/backgrounds/` |
| `pose_*.mp4` | `assets/player/` |
| `*_מ01.png` עד `*_מ15.png` | `assets/tools/` |
| `*_loop.mp4` | `assets/effects/` |
| `rival_*.png` | `assets/rivals/` |
| `parachute_blue_top.png` | `assets/rivals/` |
| `plane_fuselage.png`, `bridge_planks.png` וכד' (scenery ידועים) | `assets/scenery/` |
| `pose_*.mp4` שכבר ב-player/ | לא להזיז |

**קבצים שאי אפשר לסווג אוטומטית** → רשום ב-`unrecognized` ושאל לפני שזזים.

### שלב 3 — הצג תוכנית לפני ביצוע
**אל תזיז קובץ אחד לפני שמציגים תוכנית מלאה:**

```
אני מתכנן להזיז X קבצים:

backgrounds/ (Y קבצים):
  - bg_airplane.mp4 ← מ: [current path]
  - bg_jungle_clearing.mp4 ← מ: [current path]
  ...

player/ (Y קבצים):
  - pose_01.mp4 ← מ: [current path]
  ...

tools/ (Y קבצים):
  - מצנח_מ01.png ← מ: [current path]
  ...

לא מזוהים (צריך הנחיה):
  - [filename] — לא ברור לאיזו תיקייה שייך

האם להמשיך?
```

### שלב 4 — רק אחרי אישור: העברה
```python
import shutil, os

# צור תיקיות יעד אם לא קיימות
for folder in ['backgrounds','player','tools','scenery','effects','rivals','results']:
    os.makedirs(f'assets/{folder}', exist_ok=True)

# העבר לפי התוכנית המאושרת
shutil.copy2(src, dst)  # copy ולא move — לא מוחקים מקור עד אימות
```

### שלב 5 — אימות ודוח
אחרי ההעברה — הפק `pipeline/asset_manifest.json`:
```json
{
  "organized_at": "timestamp",
  "summary": {
    "backgrounds": 0,
    "player": 0,
    "tools": 0,
    "scenery": 0,
    "effects": 0,
    "rivals": 0,
    "unresolved": 0
  },
  "missing_from_content_lock": [],
  "extra_files_not_in_spec": []
}
```

כלומר — גם מה שחסר לפי `content_lock.json` וגם מה שיש אבל לא מוזכר בspec.

### שלב 6 — שאל לפני מחיקת מקורות
```
הסידור הושלם. נמצאו X קבצים במיקומים מקוריים.
האם למחוק את הקבצים המקוריים (המקומות הישנים)?
המלצה: לא עדיין — חכי עד שהbuilder מאמת שהpaths עובדים.
```

---

## ⚠️ אסור לעשות

- אסור לשנות שמות קבצים — רק להעביר
- אסור למחוק לפני אישור
- אסור לדחוס / לשנות פורמט
- אם קובץ קיים כבר בתיקיית היעד — שאל, אל תדרוס
