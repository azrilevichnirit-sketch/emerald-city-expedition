# Bug Catalog — Studio Emerald

תיעוד שגיאות שתפסתי + מי אחראי + מה ה-root cause. כל סוכן בעתיד קורא לפני שהוא מתחיל.

---

## 2026-04-26 — M1 static rebuild session

### Bug 1: pose_05 looped video (not static)
- **תפס**: Nirit
- **גורם**: orchestrator (Claude main session)
- **Root cause**: לא קראתי `pose_composition_map.json` עד הסוף. v5 הגדיר loop_until_event=tool_clicked.
- **Fix**: regex החלפה ל-is_pose_hold:true. אחר כך — מעבר מוחלט ל-`<img>` (master_player) במקום `<video>` (pose).
- **Lesson**: אם נירית אומרת "סטטי", זה אומר ZERO וידאו לדמות. לא וידאו עם seek+pause. תמונה.

### Bug 2: M2 בחירה למערה במקום קרחת היער
- **תפס**: Nirit
- **גורם**: orchestrator שלי + set_manager (לא הופעל ל-M2)
- **Root cause**: ה-orchestrator שדחפתי בלילה דחף 14 missions עם templated bg paths בלי להפעיל director/set_manager לכל אחד.
- **Fix**: בכל בנייה חדשה — director + set_manager לכל מסיון.
- **Lesson**: orchestrator טמפלטי ⚠️ רע. צריך פרידור per-mission.

### Bug 3: content_lock.json שונה ללא הרשאה
- **תפס**: Nirit
- **גורם**: לא ידוע (קרה לפני הסשן). חשד: agent קודם או edit ידני.
- **Root cause**: violation של "content_lock נעול" iron rule.
- **Fix**: יצרתי `pipeline/_spec_original.json` מהמסמך שלה. כל סוכן קורא משם, לא מ-content_lock.
- **Lesson**: יש לוודא integrity של locked files. Hash check לפני כל סבב.

### Bug 4: progress bar עם מספרים ("M1 · ניקוד: 0")
- **תפס**: Nirit
- **גורם**: builder agent (הראשון)
- **Root cause**: ה-`_spec_original.json` שנתתי ל-builder לא כלל את spec §3 (progress_bar_spec). היו רק טקסטי המשימות.
- **Fix**: העשרתי את `_spec_original.json` עם sections 3,4,8,9 מלאים. Builder החליף ל-CSS rope+dot.
- **Lesson**: spec ל-agents חייב להיות מלא — לא רק "מה הטקסט", גם "אילו חוקים".

### Bug 5: rivals במטוס interior
- **תפס**: Nirit  
- **גורם**: set_manager
- **Root cause**: set_manager בחר rivals כי הם קיימים ב-`rivals/`. לא חשב נרטיבית — האם rivals מתאימים ל"פנים מטוס"?
- **Fix**: הסרתי rivals מ-M1 (לא מתאימים נרטיבית).
- **Lesson**: Professional Standards #1 — חשוב נרטיבית לפני שאתה מציב prop.

### Bug 6: לבן בין הרגליים
- **תפס**: Nirit
- **גורם**: visual_editor (orchestrator-edited script)
- **Root cause**: flood fill מהפינות לא מגיע לכיסי לבן פנימיים. Threshold ראשון של 248 היה גבוה מדי.
- **Fix**: scipy connected components, neutrality test (max-min ≤ 8), threshold 240.
- **Lesson**: visual_editor חייב לראות את הפלט שלו ב-Read tool ולאמת — לא רק להריץ.

### Bug 7: הידיים נמחקו (regression מ-Bug 6 fix)
- **תפס**: Nirit
- **גורם**: orchestrator שינה script בלי לבדוק
- **Root cause**: pure-white threshold ללא neutrality test תפס skin highlights.
- **Fix**: הוספתי neutrality test (max-min ≤ 8). Skin (200,165,140) diff=60 → fails.
- **Lesson**: כל שינוי ב-threshold = re-extract + Read + visual verify.

### Bug 8: updateScoreDisplay crash
- **תפס**: content_validator + qa
- **גורם**: orchestrator שלי
- **Root cause**: הסרתי `<span id="score-display">` אבל שכחתי מ-`updateScoreDisplay()`. The function tried to access null.
- **Fix**: builder agent מחק את הפונקציה + הוסיף `renderProgress()`.
- **Lesson**: כל הסרה של DOM element → גם הסרה של JS שמתייחס אליו.

### Bug 9: zone-c gradient חלש מדי (טקסט לא קריא על רקע פרטים)
- **תפס**: Nirit
- **גורם**: builder agent (gradient לא תאם spec/design_system)
- **Root cause**: builder כתב `linear-gradient(to top, 0.55 to 0)` במקום הגרסה שאושרה `linear-gradient(180deg, 0 / 0.7 / 0.7 / 0)` (solid band במרכז).
- **Fix**: orchestrator restore ל-original (חייב qa contrast check ב-handoff).
- **Lesson**: qa_supervisor מוסיף contrast check לרשימת בדיקות.

---

## qa_supervisor — checks חדשים שנוספו

- [x] חוצי-handoff: קריאה ויזואלית של פלט (לא רק existence)
- [x] Spec cross-check על כל סעיף ב-`_spec_original.json`
- [x] Sanity check נרטיבי — האם ה-prop/asset מתאים לסצנה?
- [x] **NEW**: Contrast check — האם טקסט קריא מעל הרקע? (zone-c לא יכול להיות gradient חלש)
- [x] **NEW**: כל DOM element שמוסר — האם ה-JS שמתייחס אליו נמחק גם?
- [x] **NEW**: Visual edit (alpha/chroma) — Read של התוצאה הסופית, לא רק stdout של script.
