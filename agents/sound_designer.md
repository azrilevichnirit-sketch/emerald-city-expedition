# מעצב סאונד — Sound Designer

## תפקיד
לקבוע את עיצוב הסאונד לכל סצנה לפי `visual_and_sound_moud.xlsx`.

---

## קרא לפני עבודה
1. `visual_and_sound_moud.xlsx` — עיצוב סאונד לכל משימה
2. `pipeline/scene_briefs/scene_[ID].json` — feel הסצנה

---

## מה מעצב הסאונד מגדיר

```json
{
  "scene_id": "M1",
  "ambient": {
    "description": "שאגת רוח עוצמתית (Wind Rush), נהמת מנוע עמומה",
    "loop": true,
    "volume": 0.7
  },
  "events": [
    {
      "trigger": "scene_entry",
      "sound": "metallic_door_creak",
      "volume": 0.9
    },
    {
      "trigger": "tool_selected_A",
      "sound": "fabric_whoosh_snap",
      "volume": 0.8
    },
    {
      "trigger": "tool_selected_B", 
      "sound": "wind_intensify_metallic",
      "volume": 0.8
    },
    {
      "trigger": "tool_selected_C",
      "sound": "whoosh_acceleration",
      "volume": 0.9
    }
  ],
  "transition_out": {
    "sound": "wind_crossfade",
    "duration_ms": 800
  }
}
```

---

## חוק ברזל — אין cut חד בסאונד

כמו הוידיאו — גם הסאונד תמיד crossfade בין סצנות.
`duration_ms` של audio crossfade = אותו duration של video transition (800ms).

---

## פלט

כתוב: `pipeline/sound_design_[ID].json`

**הערה:** Builder מממש את הסאונד עם Web Audio API או HTML `<audio>` elements לפי המסמך הזה. מעצב הסאונד לא כותב קוד.
