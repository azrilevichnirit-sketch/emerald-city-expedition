# Vector Compositor — סוכן העריכה

## תפקיד
הסוכן הזה הוא **העורך הוויזואלי** של חברת ההפקה. כל שאר הסוכנים מתכננים ומחפשים — הוא לוקח את הקובץ הגולמי שירד מ-Shutterstock והופך אותו לנכס מוכן־למשחק.

זה לא AI יצירתי. אין כאן Gemini, Imagen, Nano Banana, rembg, או כל מודל שמצייר. זה PIL — דטרמיניסטי, צפוי, חוזר על עצמו ביט־ל־ביט. אותו spec מפיק תמיד אותו פלט.

הוא נכנס לפעולה רק אחרי ש-`download_checker` אישר שהקובץ הגולמי תקין. הוא לא מחליט בעצמו מה לעשות — הוא מקבל `compositor_spec` מהמאסטר, ומריץ אותו פקודה אחר פקודה.

---

## למה הוא קיים
שני סוגי בעיות שצצו ברצף הקודם של 96 הפריטים:

**בעיה 1 — ירוק על ירוק.** כל הסצנריה במשחק יושבת על וידאו רקע ב-green-screen #00B140. כש-Shutterstock מחזיר וקטור ש-contributor שמר על רקע ירוק דומה, ה-keyer בצד הלקוח לא יודע איפה הפרופ נגמר ואיפה הסצנה מתחילה. התוצאה: פרופ נעלם או נצבע דרך הסצנה.

**בעיה 2 — slug שאינו ליטרלי.** "צל של שומרים" אינו תמונה במאגר. הדרך הטובה ביותר לחפש זה היא להוריד וקטור של שומר ולצבע אותו שחור. "ג'ונגל" אינו תמונה — מורידים עץ אחד ומכפילים. ה-master מבין את זה ושולח hint, אבל ההכפלה והצביעה חייבות לקרות בקובץ אחרי ההורדה.

המסקנה: צריך עורך. עכשיו יש.

---

## חוקי ברזל

### חוק 1 — דטרמיניסטי בלבד.
אין שום מודל יצירתי. אין rembg, אין Gemini, אין AI שצובע פיקסלים בעצמו. רק PIL ופעולות מתמטיות פשוטות (chroma-key לפי מרחק צבע, silhouette = החלפת צבע בכל פיקסל לא-שקוף, tile = שכפול במטריצה).

### חוק 2 — תמיד פלט PNG עם alpha.
לא משנה מה היה הפורמט הגולמי (PNG, JPG, EPS אם רנדרנו אותו) — הקובץ שיוצא הוא PNG עם שכבת alpha. ה-builder ב-CSS מצפה לזה.

### חוק 3 — אין spec? עוברים pass בטוח.
אם המאסטר לא שלח `compositor_spec` (או שלח dict ריק), הסוכן עדיין מריץ פעם אחת `remove_background` עם זיהוי אוטומטי. לעולם לא מחזירים את הקובץ הגולמי בלי לפחות לנרמל אותו ל-PNG עם alpha נקי.

### חוק 4 — אין החלטות יצירתיות.
הסוכן הזה לא מחליט שצריך silhouette או tile. הוא רק מבצע. ההחלטה בידי המאסטר. אם המאסטר טעה — תיקון בסיבוב חוזר של המאסטר, לא איתור־עצמי כאן.

---

## פעולות נתמכות

| op | מה זה עושה | פרמטרים |
|----|------------|---------|
| `remove_background` (אוטומטי לפני transforms) | מזהה את צבע הרקע (corners → median) ומחליף ב-alpha. tolerance מותאם: רחב יותר ללבן, צר יותר לירוק רווי. | `background_hint`: `"auto"\|"white"\|"green"\|"black"\|"#RRGGBB"\|null` |
| `silhouette` | ממלא כל פיקסל גלוי בצבע יחיד, שומר alpha. | `color` (ברירת־מחדל `#000000`), `opacity` (0–1, ברירת־מחדל 1.0) |
| `tile` | משכפל את התמונה במטריצה NxM עם חפיפה אופציונלית. | `cols`, `rows`, `overlap_pct` (0–0.5) |
| `scale_to` | משנה את הגודל כך שהצלע הארוכה ביותר תהיה N פיקסלים. שומר יחס. | `max_side` |
| `pad_to` | ממרכז על קנבס בגודל מבוקש עם רקע שקוף. | `width`, `height` |
| `flatten_to_color` | מבטל alpha על־ידי flatten לצבע אחיד. נדיר — רק כשה-builder ביקש. | `color` |

---

## פורמט ה-spec שהמאסטר שולח
```json
{
  "remove_background": true,
  "background_hint": "auto",
  "transforms": [
    {"op": "silhouette", "color": "#000000", "opacity": 1.0},
    {"op": "tile", "cols": 4, "rows": 1, "overlap_pct": 0.15},
    {"op": "scale_to", "max_side": 1600}
  ]
}
```

`remove_background` ברירת־מחדל `true`. נטרל אותו רק אם הקובץ כבר הגיע עם alpha נקי לחלוטין ומדובר בפרופ ש-tile/silhouette ואז ה-keyer יסיר רעש כפול.

`background_hint`: ברוב המקרים `"auto"` מספיק. ציין `"green"` כש-Shutterstock החזיר וקטור על #00B140; `"white"` ברירת־מחדל ל-illustration+jpg fallback.

`transforms` רשימה סדורה. הפעולות מורצות לפי הסדר.

---

## פלט הסוכן
```json
{
  "status": "OK | FAIL_no_raw | FAIL_open",
  "ops_applied": ["remove_background(corners=(0,177,64), tol=24)",
                  "silhouette(color=(0,0,0), opacity=1.0)"],
  "input_bytes": 320145,
  "output_bytes": 178902,
  "saved_path": "pipeline/review/shutterstock/scenery/<slug>.png",
  "notes": ""
}
```

`ops_applied` הוא יומן מלא של מה שבוצע — חשוב לאודיט מאוחר. אם פלט נראה רע, זה הצירוף ההיסטורי שמראה איזה op נכשל.

`notes` מתעדף אזהרות לא־קריטיות (למשל "פלט קטן מ-5% מהקלט — חשד ל-over-key") שלא מעוררות FAIL אבל ראוי לבדוק ידנית.

---

## איך הוא נקרא
ב-`shutterstock_orchestrator.py`, אחרי ש-`download_checker` החזיר PASS:

```python
from vector_compositor import composite_one

comp = composite_one(
    raw_path=target,                        # מה ש-downloader כתב
    target_path=target.with_suffix(".png"), # תמיד .png
    compositor_spec=cmd.get("compositor_spec"),
)
if comp["status"] != "OK":
    feedback = f"compositor failed: {comp['status']} — {comp['notes']}"
    # ... המאסטר חוזר עם ops מתוקנות
```

הקובץ הסופי בתיקיית review הוא הפלט של ה-compositor. הקובץ הגולמי נמחק אחרי שהוא נצרך (נשאר ב-ledger ה-sha256 וה-license_id).

---

## חוק ברזל
- **לא לקבל החלטות.** מבצע spec, נקודה.
- **תמיד PNG עם alpha** (אלא אם flatten_to_color מופיע ברשימה).
- **אם spec ריק — pass בטוח** (remove_background אוטומטי בלבד).
- **אין AI יצירתי בשום מקרה.** אם המאסטר ירצה זה — צריך לעדכן את החוק במאסטר עצמו, לא לעקוף כאן.
