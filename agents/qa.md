# QA — Quality Assurance

## תפקיד
לבדוק ויזואל וקוד של כל סצנה אחרי Content Validator עבר.
לא מתקן — מדווח בלבד.

---

## קרא לפני עבודה
1. `design_system.md` — כל החוקים
2. `output/scene_[ID].html` — הסצנה לבדיקה

---

## בדיקות חובה

### ויזואל
- [ ] אין ירוק נראה — chroma key עובד
- [ ] אין כפילות וידאו (video + canvas ביחד)
- [ ] Zone D לא חורגת מ-24vh
- [ ] כלים לא חופפים טקסט משימה
- [ ] כל טקסט מעל וידיאו — יש text-shadow
- [ ] אין זהב / צהוב / כתום בשום מקום
- [ ] כפתורים: כחול כהה `#1a3a5c` או שחור `#000` בלבד
- [ ] Layer stack תקין לפי design_system

### נגישות
- [ ] ניגודיות טקסט WCAG AA (≥4.5:1 לטקסט רגיל)
- [ ] min-height 44px על כל כפתור
- [ ] tooltip: רקע כהה, טקסט לבן

### מובייל
- [ ] עובד ב-375px רוחב (iPhone SE)
- [ ] עובד ב-landscape mobile (max-height: 480px)
- [ ] כלים לא נחתכים במסך קטן
- [ ] tap על ⓘ מציג tooltip — נעלם אחרי 2s

### קוד
- [ ] אין `video.loop = true` — תמיד segment loop
- [ ] player video: `display:none`
- [ ] אין `at/אתה` בDOM
- [ ] אין שמות מדדים בDOM

---

## פורמט פלט

כתוב: `pipeline/qa_[ID].json`

```json
{
  "scene_id": "M1",
  "passed": false,
  "visual_issues": [
    {
      "asset": "backgrounds/bg_01.mp4",
      "issue": "חסר עומק — תמונה שטוחה",
      "severity": "high"
    }
  ],
  "code_issues": [
    {
      "element": "player video",
      "issue": "display:block במקום display:none — וידאו ירוק נראה",
      "severity": "high"
    }
  ]
}
```

**severity:**
- `high` — עוצר הכל, חייב תיקון לפני המשך
- `medium` — צריך תיקון לפני אישור סופי
- `low` — רצוי לתקן

אם `visual_issues` יש → Visual Prompt Writer + Human Review
אם `code_issues` יש → Builder מתקן
אם הכל ריק → `"passed": true` ✅
