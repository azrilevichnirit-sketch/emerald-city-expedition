# Design System — משלחת אל עיר האזמרגד
# כל סוכן חייב לקרוא קובץ זה לפני כל עבודה

---

## 1. מבנה המסך — Staging Zones

המסך מחולק ל-4 אזורים קבועים. **אסור לחרוג מהם.**

```
┌─────────────────────────────────────┐
│  ZONE A — Progress Bar (top)        │  height: 6vh | min: 28px
├─────────────────────────────────────┤
│                                     │
│  ZONE B — Scene / Story (center)    │  height: 54vh
│  טקסט נרטיב, אנימציית שחקן,        │
│  רקע, תפאורה, יריבים, אפקטים       │
│                                     │
├─────────────────────────────────────┤
│  ZONE C — Mission Text (lower mid)  │  height: 16vh
│  טקסט המשימה בלבד — RTL            │
├─────────────────────────────────────┤
│  ZONE D — Tool Container (bottom)   │  height: 24vh | min: 120px
│  3 כלים תמיד — שווה-ערך, שווה-גודל │
└─────────────────────────────────────┘
Total: 100vh — no scrolling ever
```

### Zone D — Tool Container — חוקים נוקשים

#### Tooltip — מכניקת אייקון i

כל כלי מציג אייקון `ⓘ` קטן בפינה שלו. זה המנגנון היחיד לגילוי שם הכלי.

```
┌──────────────┐
│              │
│  [tool img]  │
│            ⓘ │  ← אייקון i בפינה ימין עליונה
└──────────────┘
```

**Desktop:** `hover` על אייקון ⓘ → שם הכלי מופיע  
**Mobile:** `tap` על אייקון ⓘ → שם הכלי מופיע, נעלם אחרי 2 שניות

**אסור:** hover על הכלי עצמו פותח tooltip  
**אסור:** tooltip מופיע אוטומטית ללא אינטראקציה עם ⓘ

```css
.tool-info-icon {
  position: absolute;
  top: 6px;
  right: 6px;        /* RTL: פינה ימין עליונה */
  width: 20px;
  height: 20px;
  background: rgba(0,0,0,0.6);
  color: #fff;
  border-radius: 50%;
  font-size: 0.7rem;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  z-index: 21;
  border: 1px solid rgba(255,255,255,0.4);
}

.tool-tooltip {
  position: absolute;
  bottom: calc(100% + 8px);
  right: 0;
  background: rgba(0,0,0,0.85);
  color: #FFFFFF;
  padding: 5px 10px;
  border-radius: 6px;
  font-size: 0.8rem;
  white-space: nowrap;
  direction: rtl;
  pointer-events: none;
  opacity: 0;
  transition: opacity 150ms;
  z-index: 50;
}

/* Desktop: hover על ⓘ */
.tool-info-icon:hover + .tool-tooltip,
.tool-info-icon:focus + .tool-tooltip {
  opacity: 1;
}

/* Mobile: class מתווסף ב-JS אחרי tap, מוסר אחרי 2s */
.tool-tooltip.visible {
  opacity: 1;
}
```

```javascript
// Mobile tap handler
document.querySelectorAll('.tool-info-icon').forEach(icon => {
  icon.addEventListener('click', (e) => {
    e.stopPropagation(); // לא מפעיל בחירת כלי
    const tooltip = icon.nextElementSibling;
    tooltip.classList.add('visible');
    setTimeout(() => tooltip.classList.remove('visible'), 2000);
  });
});
```



- תמיד 3 כלים בשורה אחת
- רוחב כל כלי: `calc(28vw)` מקסימום, `80px` מינימום
- גובה: `calc(20vh)` מקסימום, `80px` מינימום
- רווח שווה בין הכלים: `justify-content: space-evenly`
- **אסור שכלי יחרוג מחוץ ל-Zone D**
- **אסור שכלי יחפוף על טקסט המשימה**
- רקע Zone D: `rgba(0,0,0,0.65)` — כהה מספיק לנראות, שקוף מספיק לאווירה
- גבול עליון: `1px solid rgba(255,255,255,0.15)`

---

## 2. Player Character — גדלים ומיקום

```css
/* Desktop */
.player-character {
  height: 52vh;
  max-height: 420px;
  bottom: 24vh; /* מעל Zone D */
  right: 35%;
  position: absolute;
  z-index: 10;
}

/* Mobile portrait */
@media (max-width: 480px) {
  .player-character {
    height: 38vh;
    max-height: 280px;
    right: 28%;
    bottom: 25vh;
  }
}

/* Mobile landscape */
@media (max-height: 480px) {
  .player-character {
    height: 55vh;
    bottom: 22vh;
  }
}
```

**כלל קריטי:** השחקן תמיד נמצא מעל Zone D. לעולם לא מכוסה על ידי כלים.

---

## 3. טיפוגרפיה — חוקי גופן

### גופנים מורשים
```css
font-family: 'Heebo', 'Assistant', sans-serif; /* עברית */
```

### גדלי טקסט
| סוג | Desktop | Mobile | משקל |
|-----|---------|--------|------|
| Narrative (סיפור) | 1.35rem | 1.1rem | 400 |
| Mission question | 1.1rem | 0.95rem | 600 |
| Tool tooltip | 0.85rem | 0.8rem | 400 |
| Checkpoint text | 1.0rem | 0.9rem | 400 |
| Button CTA | 1.2rem | 1.05rem | 700 |

### כיוון טקסט
**כל טקסט עברי:** `direction: rtl; text-align: right;`  
**טקסט מרכזי (כותרת/נרטיב):** `direction: rtl; text-align: center;`

---

## 4. פלטת צבעים — מה מותר ומה אסור

### צבעים מורשים
```
רקע כהה:       #0d0d0d, #1a1a1a, rgba(0,0,0,0.7-0.85)
טקסט ראשי:     #FFFFFF — רק על רקע כהה (contrast ratio ≥ 4.5:1)
טקסט משני:     #E0E0E0 — רק על רקע כהה
כפתור ראשי:    #1a3a5c (כחול כהה) עם טקסט #FFFFFF
כפתור חלופי:   #000000 (שחור) עם טקסט #FFFFFF
כפתור hover:   #0f2540 (כחול כהה יותר) / #1a1a1a (שחור)
Progress fill: #1a3a5c on #333333
אייקון ⓘ:      rgba(0,0,0,0.6) עם border לבן
```

### ❌ צבעים אסורים לחלוטין — אפס חריגות
```
זהב בכל גוון:  #FFD700, #FFC200, #c8860a, #e8a020, gold — אסור לחלוטין
צהוב:          כל גוון צהוב — אסור
כתום חם:       כל גוון כתום/ענבר — אסור
לבן על לבן:    #FFF on #EEE — אסור
אפור בהיר על לבן: contrast < 3:1 — אסור
```

**הכלל הפשוט:** כפתורים — כחול כהה או שחור עם טקסט לבן. שום דבר אחר.

---

## 5. נגישות — חוקים מחייבים

### ניגודיות טקסט (WCAG AA)
כל טקסט שמוצג על רקע חייב לעמוד ב:
- **טקסט רגיל** (< 18pt): contrast ratio ≥ **4.5:1**
- **טקסט גדול** (≥ 18pt / bold ≥ 14pt): contrast ratio ≥ **3:1**

### בדיקות חובה לפני כל deliverable
```
לבן #FFF על שחור #000     → 21:1 ✅
לבן #FFF על #1a1a1a       → 15:1 ✅  
לבן #FFF על rgba(0,0,0,.7) → ~8:1 ✅
לבן #FFF על רקע ג'ונגל ללא overlay → ❌ חייב להוסיף text-shadow או overlay
```

### text-shadow חובה על כל טקסט מעל וידיאו/תמונה
```css
text-shadow: 0 1px 3px rgba(0,0,0,0.9), 0 2px 8px rgba(0,0,0,0.7);
```

### tooltip חובה
```css
.tooltip {
  background: rgba(0,0,0,0.85);
  color: #FFFFFF;
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 0.85rem;
  direction: rtl;
  /* contrast: white on rgba(0,0,0,0.85) ≈ 17:1 ✅ */
}
```

---

## 6. כפתורים — spec מחייב

```css
.btn-primary {
  background: #1a3a5c;   /* כחול כהה */
  color: #FFFFFF;        /* contrast: ~9:1 ✅ */
  padding: 12px 40px;
  border-radius: 25px;
  font-size: 1.2rem;
  font-weight: 700;
  border: none;
  cursor: pointer;
  min-height: 44px;
  min-width: 120px;
}

.btn-primary:hover {
  background: #0f2540;
}

/* חלופה: שחור */
.btn-primary.dark {
  background: #000000;
  color: #FFFFFF;        /* contrast: 21:1 ✅ */
}

.btn-secondary {
  background: transparent;
  color: #FFFFFF;
  border: 2px solid #FFFFFF;
  padding: 10px 28px;
  border-radius: 25px;
  min-height: 44px;
}

/* ❌ אסור לחלוטין */
/* background: gold / #FFD700 / #c8860a / #e8a020 / כל גוון צהוב-כתום */
```

---

## 7. Progress Bar

```css
.progress-bar {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 6vh;
  min-height: 28px;
  max-height: 44px;
  background: #1a1a1a;
  z-index: 100;
  display: flex;
  align-items: center;
  padding: 0 16px;
}

/* אסור: מספרים, "1/15", ספירה כלשהי */
/* מותר: נקודת אור שזזת קדימה בלבד */
```

---

## 8. Layer Stack — סדר Z-index

```
z-index: 0   — background video
z-index: 2   — scenery props (behind player)
z-index: 5   — rivals
z-index: 9   — tool consequence animations (behind player)
z-index: 10  — player character (canvas chroma key)
z-index: 11  — tool overlay on player (wingsuit etc)
z-index: 15  — effects overlay (mix-blend-mode: screen)
z-index: 20  — tool items in container
z-index: 30  — mission text
z-index: 40  — narrative text overlay
z-index: 50  — tooltip
z-index: 100 — progress bar (always on top)
z-index: 200 — transition overlay (fade to black)
```

---

## 9. Mobile First — breakpoints

```css
/* Base: mobile portrait (360px+) */
/* Tablet: 768px+ */
/* Desktop: 1024px+ */
/* Landscape mobile: max-height: 480px */
```

**כלל:** בנה תמיד mobile ראשון. Desktop הוא enhancement, לא הבסיס.

**בדיקות חובה:**
- [ ] iPhone SE (375×667)
- [ ] iPhone 14 (390×844)  
- [ ] Samsung Galaxy (360×800)
- [ ] iPad portrait (768×1024)
- [ ] Desktop (1280×720)

---

## 10. אנימציות — עקרונות

- Transition בין סצנות: תמיד `cross-dissolve 800ms` — **אין hard cuts**
- Tool stagger: 0ms / 120ms / 240ms — אחיד בכל המשחק
- Gear toss arc: `cubic-bezier(0.25, 0.46, 0.45, 0.94)` — אחיד בכל המשחק  
- Post-choice hold: 1800ms–2500ms — אחיד בכל המשחק
- **אסור:** `animation: shake` על טקסט שצריך לקרוא

---

## 11. שפה — חוקים

- **אסור:** את / אתה בכל טקסט שחקן
- **מותר:** הצוות, נתקדם, נבחר, פונים, עוברים
- **אסור:** לציין שמות מדדים (סיכון / יציבות / FOMO / אימפולסיביות) בממשק
- **אסור:** לציין מספר משימות / 1 מתוך 15
- **Tooltip:** שם כלי בלבד — לא תיאור, לא רמז

---

## 12. Green Screen — Chroma Key

### מה יש בפרויקט
רוב אנימציות השחקן (`player/pose_*.mp4`) צולמו על **רקע ירוק**.
הם לא יוצגו ישירות — חייבים להסיר את הירוק לפני הצגה.

### השיטה היחידה המאושרת — Canvas Chroma Key

**אסור** להשתמש ב: `mix-blend-mode`, `CSS filter`, `opacity` לבד.  
אלה לא מסירים ירוק — הם רק מסווים אותו.

```javascript
function setupChromaKey(videoEl, canvasEl) {
  const ctx = canvasEl.getContext('2d');

  videoEl.addEventListener('loadedmetadata', () => {
    canvasEl.width  = videoEl.videoWidth;
    canvasEl.height = videoEl.videoHeight;
  });

  function processFrame() {
    if (videoEl.paused || videoEl.ended) return;
    ctx.drawImage(videoEl, 0, 0, canvasEl.width, canvasEl.height);
    const frame = ctx.getImageData(0, 0, canvasEl.width, canvasEl.height);
    const data  = frame.data;
    for (let i = 0; i < data.length; i += 4) {
      const r = data[i], g = data[i+1], b = data[i+2];
      if (g > 100 && g > r * 1.4 && g > b * 1.4) data[i+3] = 0;
    }
    ctx.putImageData(frame, 0, 0);
    requestAnimationFrame(processFrame);
  }

  videoEl.addEventListener('play', processFrame);
}
```

### שימוש בHTML — תמיד כך:

```html
<!-- וידיאו נסתר — מקור בלבד -->
<video id="player-video" src="assets/player/pose_01.mp4"
       autoplay loop muted playsinline style="display:none"></video>

<!-- canvas — זה מה שנראה -->
<canvas id="player-canvas" class="player-character"></canvas>

<script>
  setupChromaKey(
    document.getElementById('player-video'),
    document.getElementById('player-canvas')
  );
</script>
```

### אילו קבצים דורשים chroma key

| תיקייה | green screen? |
|--------|--------------|
| `player/pose_*.mp4` | ✅ כולם |
| `effects/*_loop.mp4` | תלוי — Asset Manager בודק ומסמן |
| `backgrounds/bg_*.mp4` | ❌ לא |
| `tools/*.png` | ❌ לא |
| `scenery/*.png` | ❌ לא |

### סימון ב-asset_manifest.json

```json
{ "file": "player/pose_01.mp4", "chroma_key": true, "render_as": "canvas" }
{ "file": "backgrounds/bg_jungle.mp4", "chroma_key": false, "render_as": "video" }
```

Builder בודק את השדה — `chroma_key: true` → canvas + setupChromaKey. אחרת → `<video>` רגיל.

### שגיאות אסורות לחזרה
- להציג `<video>` ישירות בלי canvas כשיש green screen
- לשכוח `display:none` על הוידיאו — יופיע כפול
- `mix-blend-mode: screen` — לא פתרון לchroma key

## 13. Tool Consequence Animations

אחרי הgear toss (הכלי מגיע ליד השחקנית) — כל סוג כלי מתנהג אחרת.
הסוג מוגדר ב-`content_lock.json` תחת `tool_consequence_types.per_tool`.

### שלב 1 — Gear Toss (זהה לכולם)
```javascript
// הכלי עף מהסלוט אל יד השחקנית
function gearToss(toolEl, playerCanvas, onComplete) {
  const playerRect = playerCanvas.getBoundingClientRect();
  const toolRect   = toolEl.getBoundingClientRect();
  
  const toX = playerRect.left + playerRect.width  * 0.55 - toolRect.left;
  const toY = playerRect.top  + playerRect.height * 0.35 - toolRect.top;
  const arcY = Math.min(toolRect.top, playerRect.top) - 80;

  toolEl.animate([
    { transform: 'translate(0,0) scale(1)',                              offset: 0   },
    { transform: `translate(${toX/2}px,${arcY - toolRect.top}px) scale(1.1)`, offset: 0.45 },
    { transform: `translate(${toX}px,${toY}px) scale(0.85)`,            offset: 1   }
  ], { duration: 380, easing: 'cubic-bezier(0.25,0.46,0.45,0.94)', fill: 'forwards' })
  .finished.then(onComplete);
}
```

### שלב 2 — Consequence לפי סוג

#### 🟢 hold — נשאר ביד
```javascript
// הכלי נשאר במיקום שהגיע אליו — אין אנימציה נוספת
// מחזיק 1800ms ואז transition
function applyHold(toolEl, duration = 1800) {
  return new Promise(r => setTimeout(r, duration));
}
```

#### 🔴 use — תנועת פעולה
```javascript
// הכלי עושה קשת/חיתוך/הנפה
function applyUse(toolEl) {
  return toolEl.animate([
    { transform: 'rotate(0deg)   scale(0.85)', offset: 0    },
    { transform: 'rotate(-35deg) scale(1.0)',  offset: 0.3  },
    { transform: 'rotate(25deg)  scale(0.9)',  offset: 0.7  },
    { transform: 'rotate(0deg)   scale(0.85)', offset: 1    }
  ], { duration: 600, easing: 'ease-in-out', fill: 'forwards' }).finished;
}
// לאחר mכן: מחזיק 1200ms ואז transition
```

#### 🔵 wear — נצמד לדמות
```javascript
// הכלי עובר מיד השחקנית → מיקום גוף (כתפיים / גב / ידיים)
// מיקום יעד: מרכז canvas השחקנית
function applyWear(toolEl, playerCanvas) {
  const pr = playerCanvas.getBoundingClientRect();
  const tr = toolEl.getBoundingClientRect();
  
  // מיקום על הגוף — 40% מהרוחב, 50% מהגובה (אזור כתפיים-חזה)
  const bodyX = pr.left + pr.width  * 0.40 - tr.left;
  const bodyY = pr.top  + pr.height * 0.50 - tr.top;

  return toolEl.animate([
    { transform: toolEl.style.transform,                          offset: 0 },
    { transform: `translate(${bodyX}px,${bodyY}px) scale(1.15)`, offset: 1 }
  ], { duration: 400, easing: 'ease-out', fill: 'forwards' }).finished;
  // הכלי נשאר על הגוף — מחזיק 1500ms ואז transition
}
```

#### 🟡 deploy — מתפרש
```javascript
// הכלי גדל ומופיע מאחורי/מעל הדמות
function applyDeploy(toolEl, playerCanvas) {
  const pr = playerCanvas.getBoundingClientRect();
  const tr = toolEl.getBoundingClientRect();

  // מיקום מאחורי הדמות — מעל ומרכז
  const deployX = pr.left + pr.width  * 0.5  - tr.left;
  const deployY = pr.top  - pr.height * 0.25 - tr.top;

  // שינוי z-index לפני animation — מאחורי השחקנית
  toolEl.style.zIndex = '9';

  return toolEl.animate([
    { transform: toolEl.style.transform + ' scale(0.85)',                          offset: 0   },
    { transform: `translate(${deployX}px,${deployY}px) scale(2.2)`,               offset: 0.6 },
    { transform: `translate(${deployX}px,${deployY - 20}px) scale(2.0)`,          offset: 1   }
  ], { duration: 700, easing: 'cubic-bezier(0.34,1.56,0.64,1)', fill: 'forwards' }).finished;
  // מחזיק 1500ms ואז transition
}
```

### חיבור הכל — פונקציה ראשית

```javascript
async function handleToolSelection(toolEl, toolLabel, playerCanvas) {
  // 1. Gear toss
  await new Promise(r => gearToss(toolEl, playerCanvas, r));

  // 2. Consequence לפי סוג — נשלף מ-content_lock
  const type = CONTENT_LOCK.tool_consequence_types.per_tool[toolLabel];

  switch(type) {
    case 'hold':   await applyHold(toolEl);               break;
    case 'use':    await applyUse(toolEl);
                   await applyHold(toolEl, 1200);          break;
    case 'wear':   await applyWear(toolEl, playerCanvas);
                   await applyHold(toolEl, 1500);          break;
    case 'deploy': await applyDeploy(toolEl, playerCanvas);
                   await applyHold(toolEl, 1500);          break;
  }

  // 3. Narrative beat מופיע
  showNarrativeBeat();

  // 4. Transition לסצנה הבאה
  await transitionOut();
}
```

### ⚠️ חוקים
- הכלי **לא נעלם** אחרי הtoss — הוא נשאר גלוי עד transition
- wear/deploy → z-index:9 (מאחורי השחקנית)
- hold/use → z-index:20 (לפני השחקנית, ביד)
- **אסור** להשתמש בsetTimeout שרשרת במקום async/await



### Builder
- [ ] Zone D לא חורג מ-24vh
- [ ] כלים לא חופפים טקסט משימה
- [ ] כל טקסט מעל וידיאו/תמונה — יש text-shadow
- [ ] אין זהב / צהוב / כתום בשום מקום
- [ ] אין "את" / "אתה"
- [ ] אין מספרי משימה בממשק
- [ ] min-height 44px על כל כפתור
- [ ] כל נכס עם chroma_key:true → canvas + setupChromaKey
- [ ] וידיאו green screen → display:none, לא מוצג ישירות

### QA
- [ ] בדק ב-375px רוחב (iPhone SE)
- [ ] בדק ב-landscape mobile
- [ ] ניגודיות טקסט עומדת ב-WCAG AA
- [ ] Layer stack תואם את הטבלה למעלה
- [ ] Tooltip מופיע ב-hover (desktop) / tap על ⓘ (mobile) — נעלם אחרי 2s
- [ ] אין ירוק נראה על המסך — canvas עובד
- [ ] אין כפילות וידיאו (וידיאו + canvas ביחד)
