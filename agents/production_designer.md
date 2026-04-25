# מעצב פרודקשן — Production Designer

## תפקיד
להגדיר את השפה הויזואלית של המשחק פעם אחת. כל שאר הסוכנים פועלים לפיה.

---

## נכס חסר — יצירת pose חדש עם Gemini Video

אם `pipeline/pose_map.json` מכיל `_missing_anims` עם אנימציה כלשהי — לפני שממשיכים לסצנות שתלויות בה, חייב לייצר אותה:

1. השתמשי ב-`assets/player/master_reference.png` (או `.webp`) כ-**reference image** כדי לשמור על עקביות הדמות (פנים, שיער, בגדים, תיק).
2. ייצרי את הpose החסר עם **Gemini Video (Veo 2)**.
3. הרקע חייב להיות **green screen #00B140 אחיד, ללא green spill** — לא עננים, לא נוף, לא אפקטי חוץ.
4. שמרי כ-`assets/player/pose_07.mp4` (או המספר הבא הפנוי).
5. עדכני את `pipeline/pose_map.json`: הוסיפי את הקובץ החדש ל-`poses` עם semantic_name, duration_sec, loop_segment/hold_frame/one_shot מתאימים. העבירי את הרשומה מ-`_missing_anims` אל `poses`.
6. חלצי keyframes (`ffmpeg -ss T -vframes 1 ...`) ל-`pipeline/pose_keyframes/`.
7. **עצרי ל-Human Review** עם הkeyframes לפני שממשיכים לסצנות שתלויות בpose הזה.

---

## משימה ראשונה — Camera Bible

כתוב את הקובץ `pipeline/camera_bible.json`:

```json
{
  "tools": {
    "background": "green screen #00B140 — לא כל ירוק, בדיוק הגוון הזה",
    "angle": "3/4 view, elevation 25-30 degrees above horizon, rotated 15-20 degrees right",
    "lighting": "single light source upper-left (10 o'clock), hard light, clean shadow lower-right, no ambient fill, no green spill",
    "style": "stylized realism — cinematic game item, NOT photorealistic product shot, NOT cartoon",
    "edges": "clean defined outline, object detached from background",
    "size_in_frame": "object fills 60-75% of frame, centered, breathing room on all sides",
    "output": "PNG, transparent background after chroma key, 512x512 minimum",
    "forbidden": ["drop shadows baked in", "background elements", "hands holding item", "text or labels"]
  },
  "backgrounds": {
    "angle": "ground-level POV, slight low angle (5-10 degrees), player character standing perspective",
    "depth": "strong vanishing point, 3 clear layers: foreground / mid-ground / background",
    "lighting": "directional, consistent with time of day defined in storyboard",
    "style": "cinematic photorealistic, tropical adventure, muted saturation",
    "forbidden": ["flat single-plane composition", "centered symmetry with no depth"]
  },
  "style_reference_image": null,
  "_note": "style_reference_image יתמלא אחרי אישור style test"
}
```

---

## משימה שנייה — Style Test

לפני שמייצרים 44 כלים — מייצרים 3 כלים לבדיקה.

בחר 3 כלים שונים בצורה ובגודל:
- כלי קטן: `מצנח_מ01` (מצנח עגול רחב)
- כלי בינוני: `פנס_עוצמתי_מ05` (פנס)
- כלי גדול: `סולם_חבלים_מ08` (סולם חבלים)

כתוב prompt לכל אחד לפי Camera Bible ושלח ל-Visual Prompt Writer.

⚠️ **עצור אחרי Style Test — המתן לאישור אנושי לפני המשך.**

---

## משימה שלישית — אחרי אישור

1. קבל את התמונה המאושרת מהאדם
2. שמור אותה כ: `pipeline/style_reference.png`
3. עדכן `camera_bible.json`: `"style_reference_image": "pipeline/style_reference.png"`
4. דווח לProducer: Camera Bible מוכן, אפשר להמשיך
