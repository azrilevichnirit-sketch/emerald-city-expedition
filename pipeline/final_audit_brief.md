# Final Audit Brief — Directors & QA

**Added by Producer (Nirit) 2026-04-24.** Every Director and QA agent must read this
before casting votes, especially during the final audit (after all
assets—scenery, backgrounds, transitions, poses, tools—are produced).

---

## 1. HIDDEN PSYCHOLOGICAL METRICS — CRITICAL CONTEXT

The game is a **disguised behavioral assessment**. The player sees an adventure;
the game silently measures four psychological traits via their tool choices:

| Metric | Hebrew | Measured in missions | Score range |
|---|---|---|---|
| Risk | סיכון | 1, 4, 8, 11, 14 | 5–15 |
| Stability | יציבות | 2, 6, 9, 13 | 4–12 |
| Impulsivity | אימפולסיביות | 5, 10 | 2–6 |
| FOMO | FOMO | 3, 7, 12, 15 | 4–12 |

Each mission has 3 tools worth 1 / 2 / 3 points. The higher the points, the more
extreme the trait signaled by that choice. **The player is NEVER told which
metric is being measured, or that ANY measurement is happening.**

---

## 2. FINAL AUDIT CHECKLIST — VISUAL-BIAS CHECK

When reviewing any asset, verify that NO visual cue tells the player which choice
"wins" the metric. The only legitimate difference between tools is the KIND of
action (what the tool does) — never the quality of production.

### Tools (3 per mission)

- ❌ **Flag** if tool #3 (highest points) looks cooler / more heroic / better lit /
  more detailed / more cinematic than tools #1–2.
- ❌ **Flag** if tool #1 (lowest points) looks boring / dull / cheap / childish
  compared to #2–3.
- ✅ **Pass** when all three tools look equally professional, equally desirable,
  equally well-crafted. Difference in shape and function, not in production value.

### Backgrounds, transitions, scenery

- ❌ **Flag** scenes that suggest "the right answer is obvious" — e.g. one path
  dramatically lit while another is dark, warning signs on one route only,
  celebration imagery biased toward one mission outcome, etc.
- ✅ **Pass** when all narrative options look equally viable. Tension comes from
  the adventure itself, not from visual hints that pre-answer the choice.

### Player animations (reactions during & after each choice)

- ❌ **Flag** if a "high-risk" choice triggers a triumphant pose while a
  "low-risk" choice triggers a defeated / apologetic pose (or vice versa).
- ✅ **Pass** when the same basic demeanor runs across all branches; the
  consequence animation matches the physical TOOL, not the score.

### UI & tooltip content

- ❌ **Flag** any tooltip, label, or micro-copy that mentions `risk / stability
  / impulsivity / FOMO`, or shows point values next to tools.
- ✅ **Pass** when tooltips show the tool's label only — verbatim from
  `tools[].label` in `content_lock.json`.

### Text inside assets — INTENTIONAL vs MODEL-INVENTED

The blanket "no text/logos" rule applies to **model-invented text** only
(random watermarks, subtitle bars, fake brand names Veo/Imagen hallucinates
into the frame). Some assets LEGITIMATELY contain text by design:

- ✅ **Allowed — intentional text**:
  - `דגל_סיום_מ15` — the finish-line flag normally shows **FINISH** or a
    checkered banner; this is the recognisable racing-finish icon.
  - Any asset whose content_lock brief explicitly calls for text/signage
    (street signs, warning plaques, meter dials) — the brief is the
    source of truth.
- ❌ **Still flag — hallucinated text**:
  - Random logos, brand marks, subtitle bars, watermarks, gibberish
    lettering that the model inserted on its own accord, **not** called for
    by the brief.
- ✅ **Pass** when text presence matches the brief: absent when the brief
  says nothing about text; present (and readable, English or Hebrew) only
  when the brief requests it.

---

## 3. WHEN YOU FLAG

If any asset visually biases the measurement:

1. **Describe the specific bias** in your vote notes — e.g. "tool #3 in M1
   (חליפת כנפיים) is lit more dramatically than #1–2, making the high-risk
   choice visually dominant."
2. **Recommend an action**: regenerate with equalized visual weight, or swap
   with a variant, or promote a neighboring candidate that doesn't bias.
3. **Do not promote to delivered** until the bias is resolved.

Being decisive here is part of the Director's role. A passing vote on a
visually-biased asset corrupts the measurement the entire game is built to make.

---

## 4. NIRIT'S GOVERNING PRINCIPLE

> המשחק מוצג כחוויה הרפתקנית בלבד.
> *The game is presented as an adventure only.*

The psychology is inside. The surface is pure adventure. Audit accordingly.
