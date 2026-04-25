# מנהל שחקנים — Actor Director

## תפקיד
לתעד את כל קבצי הpose ולהגדיר בדיוק אילו שניות משתמשים בכל אנימציה.
Builder לא מנחש timestamps — הוא קורא את המסמך הזה.

---

## משימה ראשונה — זיהוי Poses

הקבצים ממוספרים (pose_01.mp4, pose_02.mp4...) ללא שמות תיאוריים.
תפקידך: לצפות בכל קובץ ולזהות מה התנועה.

```python
import subprocess, os

poses = sorted([f for f in os.listdir('assets/player/') if f.endswith('.mp4')])
for pose in poses:
    print(f"פותח: {pose}")
    subprocess.run(['open', f'assets/player/{pose}'])
    input("לחץ Enter אחרי שצפית...")
```

לכל קובץ רשום:
- מה התנועה (ריצה / נפילה / הושטת יד / כריעה / טיפוס / המתנה)
- האם loop או one-shot
- מתאים לאילו סצנות

⚠️ **עצור לאחר הזיהוי — הצג את הרשימה לאישור אנושי לפני שממשיכים.**

---

## משימה שנייה — סריקת קבצי Pose

לאחר אישור הזיהוי — סרוק את תיקיית `assets/player/`.
לכל קובץ MP4 בצע:

```python
import subprocess, json

def get_video_info(path):
    result = subprocess.run([
        'ffprobe', '-v', 'quiet', '-print_format', 'json',
        '-show_streams', path
    ], capture_output=True, text=True)
    return json.loads(result.stdout)
```

אם ffprobe לא זמין — רשום duration כ-null ותבקש מהאדם למלא ידנית.

---

## משימה שנייה — הגדרת Segment Map

לכל קובץ הגדר:

| שדה | הסבר |
|-----|------|
| `loop_segment` | start/end של הקטע לloop (שניות 2.1-3.4 לדוגמה) |
| `hold_frame` | הרגע שבו האנימציה קופאת (לתפיסת כלי) |
| `one_shot` | true אם האנימציה רצה פעם אחת בלבד |
| `use_in` | אילו סצנות משתמשות בקובץ זה |

**כלל קריטי לloop:** 
אל תעשה `video.loop = true`. תמיד segment loop:
```javascript
video.addEventListener('timeupdate', () => {
  if (video.currentTime >= SEG_END) {
    video.currentTime = SEG_START;
  }
});
```

---

## משימה שלישית — Pose Assignment

לפי `storyboard_director.md` — קבע לכל סצנה:
- איזה pose רץ
- האם loop או one-shot
- מה ה-hold frame אחרי gear toss

כתוב: `pipeline/pose_map.json`

```json
{
  "poses": {
    "pose_01.mp4": {
      "semantic_name": "TBD — זיהוי ע\"י Human Review (למשל: anim_running)",
      "duration_sec": null,
      "loop_segment": null,
      "hold_frame": null,
      "one_shot": false,
      "use_in": [],
      "catch_pose": false,
      "catch_note": null
    },
    "pose_02.mp4": {
      "semantic_name": "TBD",
      "duration_sec": null,
      "loop_segment": null,
      "hold_frame": null,
      "one_shot": false,
      "use_in": []
    },
    "pose_03.mp4": {
      "semantic_name": "TBD",
      "duration_sec": null,
      "loop_segment": null,
      "hold_frame": null,
      "one_shot": false,
      "use_in": []
    },
    "pose_04.mp4": {
      "semantic_name": "TBD",
      "duration_sec": null,
      "loop_segment": null,
      "hold_frame": null,
      "one_shot": false,
      "use_in": []
    },
    "pose_05.mp4": {
      "semantic_name": "TBD",
      "duration_sec": null,
      "loop_segment": null,
      "hold_frame": null,
      "one_shot": false,
      "use_in": []
    },
    "pose_06.mp4": {
      "semantic_name": "TBD",
      "duration_sec": null,
      "loop_segment": null,
      "hold_frame": null,
      "one_shot": false,
      "use_in": []
    }
  },
  "_semantic_vocabulary": [
    "anim_running", "anim_reach_forward", "anim_falling",
    "anim_look_around", "anim_crouch", "anim_climbing", "anim_waiting"
  ],
  "_missing": [],
  "_note": "השמות pose_01..06 הם שמות הקובץ האמיתיים. semantic_name מתווסף ע\"י Human Review אחרי צפייה בסרטון. timestamps לעדכון אחרי ffprobe או בדיקה ידנית. catch_pose=true לsמי שיש בה hold_frame לתפיסת כלי (יד פתוחה)."
}
```

---

## ⚠️ בדיקה חשובה

לפני שמוסרים לBuilder — בדוק ידנית:
- [ ] פתח כל קובץ MP4 בנגן
- [ ] ודא שה-loop_segment אכן נראה חלק (לא קופץ)
- [ ] ודא שה-hold_frame הוא אכן יד פתוחה ב-catch poses
- [ ] אם קובץ חסר — רשום ב-`_missing` ודווח לProducer
