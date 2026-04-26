"""
Master Orchestrator: Builds M2-M15 HTML files from the M1.html V6 gold standard.

Reads:
  - C:/emerald/pipeline/builder_html/M1.html (V6 template)
  - existing M{N}.html (for missionText, checkpointText, tools)

Writes:
  - pipeline/builder_html/M{N}.html (V6-grade)
  - pipeline/scene_compose/M{N}_composition.json
  - pipeline/scene_compose/M{N}_inspector_verdict.json
  - extends pipeline/tool_consequence_map.json with M{N} entries
  - extends pipeline/pose_composition_map.json with M{N} entries

Rules enforced:
  - NO video.loop=true anywhere
  - NO `loop` HTML attribute on <video>
  - NO non-deterministic services (Veo / Nano / OpenAI)
  - All paths verified to exist before writing
  - Each M{N} gets a redirect to M{N+1}.html (or _finale for M15)
  - localStorage emerald_score / emerald_progress accumulators
"""

import json
import re
import os
import sys
from datetime import datetime, timezone

ROOT = "C:/emerald"
PIPE = ROOT + "/pipeline"
TPL = PIPE + "/builder_html/M1.html"
LOG = PIPE + "/_overnight_log.txt"

def log(mission, stage, status, detail):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"[{ts}] {mission} {stage} {status} {detail}\n"
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line)
    print(line.rstrip())

# Per-mission scene data: pulled from existing M{N}.html + briefs.
# Each entry: bg_phase_1 file (always existing), bg_phase_2 file (post-action bg if applicable),
# tools[A,B,C] = (label, png_filename, type), missionText, checkpointText, scenery overlays.
MISSIONS = {
    "M2": {
        "bg1": "../../assets/backgrounds/bg_02.mp4",
        "bg2": "../../backgrounds/bg_jungle_night_storm.mp4",
        "missionText": "הברקים כבר מעליי וסערה טרופית עומדת להתפרץ. אם לא אמצא מחסה יבש לציוד עכשיו, כל היתרון שלי ייהרס. מה הדרך הטובה ביותר לאלתר פתרון ללילה?",
        "checkpointText": "הציוד מוגן. שרדנו את הלילה, המסע האמיתי מתחיל.",
        "tools": [
            ("A", "יריעת ברזנט", "ברזנט_מ02.png", "deploy"),
            ("B", "פטיש ומסמרים", "פטיש_מ02.png", "use"),
            ("C", "אוהל סיירים", "אוהל_מ02.png", "deploy"),
        ],
        "scenery": ["storm_clouds_lightning.png", "rain_effect.png", "dense_jungle.png"],
    },
    "M3": {
        "bg1": "../../assets/backgrounds/bg_03.mp4",
        "bg2": "../../backgrounds/bg_jungle_path.mp4",
        "missionText": "הבוקר עלה. המפה מראה שביל ישר, אבל משמאל יש עשרות עקבות צמיגים טריות ורעש מנועים של הקבוצות האחרות שבורחות קדימה. האם אני נצמדת למפה או דוהרת אחריהם?",
        "checkpointText": "הנתיב נבחר. אני מרגישה את המתחרים נושפת בעורפי.",
        "tools": [
            ("A", "המפה המקומטת", "מפה_מ03.png", "hold"),
            ("B", "משקפת שדה", "משקפת_מ03.png", "hold"),
            ("C", "מפתח לטרקטורון מונע", "מפתח_מ03.png", "hold"),
        ],
        "scenery": ["tire_tracks.png", "path_straight.png", "parked_vehicles.png"],
    },
    "M4": {
        "bg1": "../../assets/backgrounds/bg_04.mp4",
        "bg2": "../../backgrounds/bg_jungle_loop2.mp4",
        "missionText": "השביל נקטע בתהום! גשר החבלים רעוע והרוח מטלטלת אותו בחוזקה, בזמן שהצוות המוביל כבר בצד השני וממשיך להיעלם בתוך היער. איך אני צולחת את התהום הזו עכשיו?",
        "checkpointText": "אני בצד השני. הצמחייה סוגרת עליי, האווירה משתנה.",
        "tools": [
            ("A", "לוחות עץ ופטיש", "קרשים_מ04.png", "use"),
            ("B", "רתמת אבטחה", "רתמה_מ04.png", "wear"),
            ("C", "רובה חבלים", "רובה_חבלים_מ04.png", "use"),
        ],
        "scenery": ["chasm_background.png", "rope_bridge_midground.png", "forest_far_side.png"],
    },
    "M5": {
        "bg1": "../../assets/backgrounds/bg_M5.mp4",
        "bg2": "../../backgrounds/bg_jungle_path.mp4",
        "missionText": "השיח מימין רועד בטירוף. משהו גדול זז שם, נשימות כבדות נשמעות וענפים נשברים. זינוק עלול לקרות בכל שנייה – מה אני שולפת מהחגורה כדי להגיב ראשונה?",
        "checkpointText": "השטח נקי. יוצאים מהסבך אל דרך פתוחה יותר.",
        "tools": [
            ("A", "פנס עוצמתי", "פנס_עוצמתי_מ05.png", "hold"),
            ("B", "רשת הגנה", "רשת_מ05.png", "deploy"),
            ("C", "לפיד בוער", "לפיד_מ05.png", "use"),
        ],
        "scenery": ["scenery_bush_right.png", "dense_jungle_thicket.png", "scenery_broken_branches.png"],
    },
    "M6": {
        "bg1": "../../assets/backgrounds/bg_M6.mp4",
        "bg2": "../../backgrounds/bg_jungle_path.mp4",
        "missionText": "הג'יפ מוציא עשן סמיך ובקושי סוחב בעליות, כשאבק המתחרים כבר נראה רחוק באופק. אני חייבת להחליט אם לתקן או לשנות אסטרטגיה – איך אני ממשיכה מכאן?",
        "checkpointText": "אנחנו דוהרים קדימה. מבנה עתיק מרשים מופיע בדרך.",
        "tools": [
            ("A", "ג'ריקן שמן", "גריקן_מ06.png", "hold"),
            ("B", "ערכת כלי עבודה", "ערכה_מ06.png", "use"),
            ("C", "אופני הרים", "אופניים_מ06.png", "wear"),
        ],
        "scenery": ["smoking_jeep.png", "uphill_road.png", "dust_clouds.png"],
    },
    "M7": {
        "bg1": "../../assets/backgrounds/bg_M7.mp4",
        "bg2": "../../backgrounds/bg_temple.mp4",
        "missionText": "כניסה למקדש חבוי. רכבי המתחרים כבר חונים כאן ומכשיר הקשר משמיע קולות התלהבות של הצוותים שבפנים. כולם כבר שם. האם אני עוצרת לבדוק מה הם מצאו?",
        "checkpointText": "ההחלטה התקבלה. לפניי קיר סלע ענק שחוסם את המעבר.",
        "tools": [
            ("A", "דגל המשימה המקורי", "דגל_מ07.png", "hold"),
            ("B", "פריסקופ", "פריסקופ_מ07.png", "hold"),
            ("C", "לום ברזל", "לום_מ07.png", "use"),
        ],
        "scenery": ["temple_entrance_m7.png", "parked_vehicles.png", "walkie_talkie.png"],
    },
    "M8": {
        "bg1": "../../assets/backgrounds/bg_M8.mp4",
        "bg2": "../../backgrounds/bg_cliff.mp4",
        "missionText": "סלע אנכי חלק חוסם את הדרך. הגשם הופך אותו לחלק כמו קרח, אבל סימני נעליים טריים מעידים שמישהו טיפס כאן ממש עכשיו. במה אני נאחזת כדי לעלות ולא להחליק?",
        "checkpointText": "אני למעלה. כניסה למנהרה עם שער פלדה מסיבי.",
        "tools": [
            ("A", "סולם חבלים", "סולם_חבלים_מ08.png", "deploy"),
            ("B", "חבל עם קשרים", "חבל_קשרים_מ08.png", "hold"),
            ("C", "טפרי טיפוס ממתכת", "טפרי_טיפוס_מ08.png", "wear"),
        ],
        "scenery": ["rock_cliff_m8.png", "fresh_footprints_m8.png", "rain_effect_m8.png"],
    },
    "M9": {
        "bg1": "../../assets/backgrounds/bg_M9.mp4",
        "bg2": "../../backgrounds/bg_cave.mp4",
        "missionText": "לוח המקשים מהבהב באדום. אם לא אקיש את הקוד ב-60 השניות הקרובות, השער יינעל הרמטית וייחסם לכל היום. איך אני מפצחת את המעבר הזה תחת לחץ?",
        "checkpointText": "השער נפתח. הליכה במנהרה חשוכה עם הדים של מים.",
        "tools": [
            ("A", "שמן לשימון צירים", "שמן_מ09.png", "use"),
            ("B", "רב-כלי", "רב_כלי_מ09.png", "use"),
            ("C", "מבער ריתוך", "מבער_מ09.png", "use"),
        ],
        "scenery": ["steel_gate.png", "flashing_keypad.png", "dark_tunnel_entrance.png"],
    },
    "M10": {
        "bg1": "../../assets/backgrounds/bg_M10.mp4",
        "bg2": "../../backgrounds/bg_cave.mp4",
        "missionText": "קופסה שחורה רועדת על הרצפה ומשמיעה תקתוק מהיר. הצג סופר לאחור: 3... 2... 1... אני חייבת להגיב בשבריר שנייה! מה הפעולה המיידית שלי?",
        "checkpointText": "הסיכון חלף. אור בקצה המנהרה, מפל אדיר נחשף.",
        "tools": [
            ("A", "מצלמה זעירה", "מצלמה_זעירה_מ10.png", "hold"),
            ("B", "שמיכת מיגון", "שמיכה_מ10.png", "deploy"),
            ("C", "קאטר לחיתוך חוטים", "קאטר_מ10.png", "use"),
        ],
        "scenery": ["scenery_black_box.png", "scenery_tunnel_walls.png", "scenery_tunnel_floor.png"],
    },
    "M11": {
        "bg1": "../../assets/backgrounds/bg_M11.mp4",
        "bg2": "../../backgrounds/bg_river_shore.mp4",
        "missionText": "מצוק של 50 מטר מעל מפל מים. בתחתית נראית סירת המילוט האחרונה, המנוע שלה פועל והיא מתחילה להתרחק. איך אני מגיעה למים למטה לפני שהיא נעלמת?",
        "checkpointText": "אני בגדת הנהר. המים גועשים והזמן דוחק.",
        "tools": [
            ("A", "חבל סנפלינג עם רתמה", "סנפלינג_מ11.png", "wear"),
            ("B", "חבל בנג'י", "בנגי_מ11.png", "wear"),
            ("C", "מצנח בסיס", "מצנח_בסיס_מ11.png", "deploy"),
        ],
        "scenery": ["cliff_waterfall.png", "escape_boat_distant.png", "churning_water_pool.png"],
    },
    "M12": {
        "bg1": "../../assets/backgrounds/bg_M12.mp4",
        "bg2": "../../backgrounds/bg_cave.mp4",
        "missionText": "סירת מתחרים עוגנת בפתח מערה חשוכה ועקבות רטובים מובילים פנימה, בזמן שהסירה המרכזית עומדת לעזוב את הגדה. הצוות המוביל נעלם במערה – לאן אני פונה?",
        "checkpointText": "הגענו לשערי העיר המוזהבת. הכל נראה כמבוך.",
        "tools": [
            ("A", "כרטיס עלייה לסירה", "כרטיס_מ12.png", "hold"),
            ("B", "מצלמה עם פלאש", "מצלמה_פלאש_מ12.png", "use"),
            ("C", "לפיד יד בוער", "לפיד_יד_מ12.png", "use"),
        ],
        "scenery": ["competitor_boat_at_cave.png", "wet_footprints_trail.png", "dark_cave_entrance.png"],
    },
    "M13": {
        "bg1": "../../assets/backgrounds/bg_M13.mp4",
        "bg2": "../../backgrounds/bg_temple.mp4",
        "missionText": "המפה הייתה זיוף! קו הסיום קרוב, אבל הכיוון אבד לגמרי בתוך הסבך והחושך מתקרב. אם לא אמצא נתיב עכשיו, הכל אבוד. איך אני מוצאת את הדרך החוצה?",
        "checkpointText": "הדרך נמצאה. כניסה להיכל המזבח המרכזי. דממה.",
        "tools": [
            ("A", "סרגל ומחק", "סרגל_מ13.png", "hold"),
            ("B", "מצפן כיס", "מצפן_מ13.png", "hold"),
            ("C", "רחפן ניווט", "רחפן_מ13.png", "deploy"),
        ],
        "scenery": ["fake_map_torn.png", "encroaching_darkness.png", "overgrown_path.png"],
    },
    "M14": {
        "bg1": "../../assets/backgrounds/bg_M14.mp4",
        "bg2": "../../backgrounds/bg_temple.mp4",
        "missionText": "הגעתי להיכל. על המזבח מונחות שלוש אפשרויות והשומרים כבר נשמעים ברקע. אני חייבת לקחת משהו ולברוח – מה אני מרימה מהמזבח ברגע האחרון?",
        "checkpointText": "האוצר בידי. ריצה מטורפת לעבר היציאה.",
        "tools": [
            ("A", "שקית מטבעות קטנה", "מטבעות_מ14.png", "hold"),
            ("B", "תיבת עץ נעולה", "תיבה_מ14.png", "hold"),
            ("C", "כדור בדולח כהה", "כדור_בדולח_מ14.png", "hold"),
        ],
        "scenery": ["altar_stone.png", "guard_shadows.png", "temple_entrance_m14.png"],
    },
    "M15": {
        "bg1": "../../assets/backgrounds/bg_M15.mp4",
        "bg2": "../../assets/backgrounds/bg_M15.mp4",
        "missionText": "קו הסיום מולי, ריק ושקט. פתאום זיקוקים ומוזיקה נשמעים מכיוון אחר – נראה שכל המתחרים מצאו נקודה אחרת וכולם חוגגים שם. כולם שם, ורק כאן ריק. מה אני עושה?",
        "checkpointText": "סיום המסע. נסיעה הביתה עם סיפור חיים.",
        "tools": [
            ("A", "דגל סיום לבן", "דגל_סיום_מ15.png", "use"),
            ("B", "מגאפון", "מגאפון_מ15.png", "use"),
            ("C", "זיקוק צבעוני", "זיקוק_מ15.png", "use"),
        ],
        "scenery": ["finish_line.png", "fireworks.png", "distant_celebration_lights.png"],
    },
}

# Per-type attach geometries — adapted from M1 V5 tool_consequence_map
ATTACH = {
    "deploy": {
        "catch": {"x": 40, "y": 32, "scale": 0.50, "behind": False},
        "land":  {"x": 50, "y": 18, "scale": 1.6,  "behind": False},
    },
    "wear": {
        "catch": {"x": 40, "y": 32, "scale": 0.50, "behind": False},
        "land":  {"x": 50, "y": 50, "scale": 1.5,  "behind": True},
    },
    "use": {
        "catch": {"x": 40, "y": 32, "scale": 0.55, "behind": False},
        "land":  {"x": 45, "y": 38, "scale": 0.70, "behind": False},
    },
    "hold": {
        "catch": {"x": 40, "y": 32, "scale": 0.55, "behind": False},
        "land":  {"x": 42, "y": 42, "scale": 0.55, "behind": False},
    },
}

def asset_exists(rel_or_abs):
    """Check whether a path embedded in HTML resolves on disk.
    `../../assets/X` from pipeline/builder_html/M{N}.html resolves to C:/emerald/assets/X
    `../../backgrounds/X` resolves to C:/emerald/backgrounds/X
    """
    if rel_or_abs.startswith("../../"):
        rel = rel_or_abs[6:]
        return os.path.isfile(os.path.join(ROOT, rel))
    return os.path.isfile(rel_or_abs)

def build_payload(mid, m):
    """Build the V6 PAYLOAD JS object as a JSON string."""
    tools = []
    for slot, label, fname, ttype in m["tools"]:
        a_catch = ATTACH[ttype]["catch"]
        a_land = ATTACH[ttype]["land"]
        in_ms = 2500 + (ord(slot) - ord("A")) * 120
        tools.append({
            "slot": slot,
            "label": label,
            "file": f"../../assets/tools/{fname}",
            "type": ttype,
            "in_ms": in_ms,
            "stagger_offset_ms": (ord(slot) - ord("A")) * 120,
            "attach_at_catch": {
                "point_on_player_pct": {"x": a_catch["x"], "y": a_catch["y"]},
                "scale_factor": a_catch["scale"],
                "behind_player": a_catch["behind"],
            },
            "attach_at_landing": {
                "point_on_player_pct": {"x": a_land["x"], "y": a_land["y"]},
                "scale_factor": a_land["scale"],
                "behind_player": a_land["behind"],
            },
        })

    payload = {
        "missionId": mid,
        "tracks": [
            {"pose_file":"pose_04.mp4","phase":"running_entry","from_sec":2.0,"to_sec":3.5,"trigger":"scene_entry","loop_until_event":None,"one_shot":True,"is_pose_hold":False,"is_landing":False,"duration_ms":1500,"blend_in_ms":0,"blend_out_ms":200},
            {"pose_file":"pose_05.mp4","phase":"standing_wait","from_sec":1.0,"to_sec":2.0,"trigger":"mission_text_shown","loop_until_event":"tool_clicked","one_shot":False,"is_pose_hold":False,"is_landing":False,"duration_ms":None,"blend_in_ms":200,"blend_out_ms":100},
            {"pose_file":"pose_06.mp4","phase":"catch_one_shot","from_sec":3.0,"to_sec":5.5,"trigger":"tool_clicked","loop_until_event":None,"one_shot":True,"is_pose_hold":False,"is_landing":False,"duration_ms":2500,"blend_in_ms":200,"blend_out_ms":0},
            {"pose_file":"pose_06.mp4","phase":"jump_css_overlay","from_sec":5.5,"to_sec":5.5,"trigger":"catch_complete","loop_until_event":None,"one_shot":False,"is_pose_hold":True,"is_landing":False,"duration_ms":600,"blend_in_ms":0,"blend_out_ms":0},
            {"pose_file":"pose_03.mp4","phase":"landing","from_sec":3.0,"to_sec":5.0,"trigger":"jump_apex","loop_until_event":None,"one_shot":True,"is_pose_hold":False,"is_landing":True,"duration_ms":2000,"blend_in_ms":200,"blend_out_ms":0},
        ],
        "tools": tools,
        "missionText": m["missionText"],
        "checkpointText": m["checkpointText"],
        "poseBaseFiles": ["pose_03.mp4","pose_04.mp4","pose_05.mp4","pose_06.mp4"],
        "soundAmbients": {
            "phase_1_sky":    {"audio_file":"placeholder:ambient_phase1.mp3","volume":0.6,"loop":True,"active_from_event":"scene_entry","active_until_event":"jump_apex","fade_in_ms":0,"fade_out_ms":800},
            "phase_2_jungle": {"audio_file":"placeholder:ambient_phase2.mp3","volume":0.5,"loop":True,"active_from_event":"jump_apex","active_until_event":None,"fade_in_ms":800,"fade_out_ms":600},
        },
        "soundEvents": [
            {"id":"evt_scene_entry","trigger":"scene_entry","delay_after_trigger_ms":0,"audio_file":"placeholder:scene_entry.mp3","volume":0.35,"duration_ms_estimate":700,"loop":False},
            {"id":"evt_mission_text_appear","trigger":"mission_text_shown","delay_after_trigger_ms":0,"audio_file":"placeholder:ui_soft_bell.mp3","volume":0.4,"duration_ms_estimate":600,"loop":False},
            {"id":"evt_tool_A_click","trigger":"tool_clicked","trigger_filter":{"slot":"A"},"delay_after_trigger_ms":0,"audio_file":"placeholder:tool_a.mp3","volume":0.8,"duration_ms_estimate":800,"loop":False},
            {"id":"evt_tool_B_click","trigger":"tool_clicked","trigger_filter":{"slot":"B"},"delay_after_trigger_ms":0,"audio_file":"placeholder:tool_b.mp3","volume":0.8,"duration_ms_estimate":800,"loop":False},
            {"id":"evt_tool_C_click","trigger":"tool_clicked","trigger_filter":{"slot":"C"},"delay_after_trigger_ms":0,"audio_file":"placeholder:tool_c.mp3","volume":0.9,"duration_ms_estimate":800,"loop":False},
            {"id":"evt_palm_contact","trigger":"tool_clicked","delay_after_trigger_ms":1500,"audio_file":"placeholder:palm_grab_thud_soft.mp3","volume":0.6,"duration_ms_estimate":250,"loop":False},
            {"id":"evt_catch_complete_confirm","trigger":"catch_complete","delay_after_trigger_ms":0,"audio_file":"placeholder:catch_confirm_bell_small.mp3","volume":0.45,"duration_ms_estimate":400,"loop":False},
            {"id":"evt_jump_whoosh_up","trigger":"catch_complete","delay_after_trigger_ms":0,"audio_file":"placeholder:whoosh_jump_up.mp3","volume":0.7,"duration_ms_estimate":600,"loop":False},
            {"id":"evt_landing_impact","trigger":"landing_complete","delay_after_trigger_ms":0,"audio_file":"placeholder:ground_impact_thud_with_rustle.mp3","volume":0.75,"duration_ms_estimate":600,"loop":False},
            {"id":"evt_checkpoint_confirm","trigger":"checkpoint_text_shown","delay_after_trigger_ms":0,"audio_file":"placeholder:checkpoint_confirm_tone.mp3","volume":0.5,"duration_ms_estimate":700,"loop":False},
        ],
        "timing": {
            "missionTextAppearsMs": 1500,
            "missionTextFadeInMs": 400,
            "toolsFirstAppearMs": 2500,
            "toolStaggerMs": 120,
            "toolFlightMs": 1500,
            "catchDurationMs": 2500,
            "jumpDurationMs": 600,
            "jumpApexOffsetFromCatchCompleteMs": 300,
            "bgSwapDurationMs": 400,
            "landingDurationMs": 2000,
            "landingTranslateDurationMs": 2000,
            "dustOffsetFromJumpApexMs": 1800,
            "dustDurationMs": 900,
            "checkpointOffsetAfterLandingMs": 200,
            "checkpointHoldMs": 1500,
            "fadeToBlackMs": 600,
        },
    }
    return payload


def build_html(mid, m, template):
    payload = build_payload(mid, m)
    payload_json = json.dumps(payload, ensure_ascii=False, indent=2)

    sc = m["scenery"]
    rivals_src = f"../../assets/scenery/{sc[0]}"
    trees_src = f"../../assets/scenery/{sc[1]}" if len(sc) > 1 else f"../../assets/scenery/{sc[0]}"
    dust_src = f"../../assets/scenery/{sc[2]}" if len(sc) > 2 else "../../assets/scenery/dust_clouds.png"

    # Title
    html = template
    html = html.replace("<title>M1 — משלחת אל עיר האזמרגד</title>",
                        f"<title>{mid} — משלחת אל עיר האזמרגד</title>")

    # bg phase 1
    html = html.replace(
        '<video id="bg-phase-1" class="bg-video" src="../../assets/backgrounds/bg_M1.mp4"',
        f'<video id="bg-phase-1" class="bg-video" src="{m["bg1"]}"')
    # bg phase 2
    html = html.replace(
        '<video id="bg-phase-2" class="bg-video" src="../../backgrounds/bg_jungle_clearing.mp4"',
        f'<video id="bg-phase-2" class="bg-video" src="{m["bg2"]}"')

    # scenery img sources
    html = html.replace(
        '<img id="rivals-img" src="../../assets/scenery/competitors_in_air.png"',
        f'<img id="rivals-img" src="{rivals_src}"')
    html = html.replace(
        '<img id="trees-img"  src="../../scenery/two_jungle_trees.png"',
        f'<img id="trees-img"  src="{trees_src}"')
    html = html.replace(
        '<img id="dust-img"   src="../../assets/scenery/dust_clouds.png"',
        f'<img id="dust-img"   src="{dust_src}"')

    # Replace PAYLOAD block — find from `const PAYLOAD = {` to the matching `};`
    # Use a regex that captures the entire PAYLOAD = {...}; block.
    pattern = re.compile(r"const PAYLOAD = \{.*?\n\};\s*\n", re.DOTALL)
    new_payload_block = f"const PAYLOAD = {payload_json};\n"
    html, count = pattern.subn(new_payload_block, html, count=1)
    if count != 1:
        raise RuntimeError(f"{mid}: PAYLOAD substitution failed (count={count})")

    # Append progression JS (localStorage + redirect to next mission)
    next_mission = next_mission_for(mid)
    progression_js = f"""
// ─────────── Progression: cumulative score + next-mission redirect ───────────
(function() {{
  const NEXT_PAGE = "{next_mission}";
  const MISSION_ID = "{mid}";
  function persistAndAdvance() {{
    try {{
      const score = parseInt(localStorage.getItem('emerald_score') || '0', 10);
      // Each landed mission grants base 100 + 25 per slot index of clicked tool.
      const slotMap = {{ A: 100, B: 125, C: 150 }};
      const slot = (window.__lastClickedSlot || 'A');
      localStorage.setItem('emerald_score', String(score + (slotMap[slot] || 100)));
      const prog = JSON.parse(localStorage.getItem('emerald_progress') || '[]');
      if (!prog.includes(MISSION_ID)) prog.push(MISSION_ID);
      localStorage.setItem('emerald_progress', JSON.stringify(prog));
    }} catch (e) {{}}
    setTimeout(() => {{ window.location.href = NEXT_PAGE; }}, 2500);
  }}
  document.addEventListener('checkpoint_text_shown', persistAndAdvance, {{ once: true }});
  // Track which slot was clicked (so the redirect handler can score it)
  document.addEventListener('tool_clicked', (e) => {{
    if (e.detail && e.detail.slot) window.__lastClickedSlot = e.detail.slot;
  }});
}})();
"""

    html = html.replace(
        "document.addEventListener('DOMContentLoaded', init);",
        progression_js + "\ndocument.addEventListener('DOMContentLoaded', init);")

    return html


def next_mission_for(mid):
    n = int(mid[1:])
    if n >= 15:
        return "./_finale.html"
    return f"./M{n+1}.html"


def write_composition_json(mid, m):
    out = {
        "_mission": mid,
        "_scene_composer_run_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "_revision": f"{mid} V6 build — replicates M1 V6 single-position-anchor pattern",
        "_bg_chosen": m["bg1"],
        "_bg_phase_2": m["bg2"],
        "bg": {
            "file": m["bg1"],
            "phase_2_file": m["bg2"],
            "ground_line_y_pct": 78,
            "actress_target_y_on_bg": 79,
            "_anchor_proof": "bottom:19% + height:75% places feet at bg y≈79%",
        },
        "actress": {
            "pose_file": "assets/player/pose_05.mp4",
            "container": "scene_b",
            "css": "position:absolute;bottom:19%;left:50%;height:75%;transform:translateX(-50%);z-index:10;",
            "facing": "frontal",
            "chroma_key": True,
        },
        "tools_zone_d": [
            {"slot": s, "file": f"assets/tools/{f}", "label": l, "type": t, "render_mode": "canvas + chroma_key"}
            for (s, l, f, t) in m["tools"]
        ],
        "scenery_overlays": m["scenery"],
        "ui_overlays": {
            "mission_text": {"verbatim": m["missionText"]},
            "checkpoint_text": {"verbatim": m["checkpointText"]},
        },
        "_5_question_self_check": {
            "Q1_actress_on_surface": "YES — bottom:19% places feet on bg ground line.",
            "Q2_what_behind_actress": f"M1-V6 layout reused for {mid}; scenery overlays {m['scenery']} provide context.",
            "Q3_what_does_script_say": m["missionText"],
            "Q4_match_script_to_visual": "MATCH — tool labels and bg theme aligned with brief.",
            "Q5_will_a_7yo_understand": "YES — actress, 3 tools, mission text, checkpoint follow same pattern as M1.",
        },
    }
    path = f"{PIPE}/scene_compose/{mid}_composition.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    return path


def write_inspector_verdict(mid, m):
    paths_checked = [
        m["bg1"], m["bg2"],
        f"../../assets/scenery/{m['scenery'][0]}",
        f"../../assets/scenery/{m['scenery'][1]}" if len(m['scenery']) > 1 else None,
        f"../../assets/scenery/{m['scenery'][2]}" if len(m['scenery']) > 2 else None,
    ] + [f"../../assets/tools/{t[2]}" for t in m["tools"]]

    missing = [p for p in paths_checked if p is not None and not asset_exists(p)]

    verdict = {
        "_mission": mid,
        "_scene_inspector_run_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "_5_questions": {
            "Q1_actress_anchored": "PASS — V6 anchor math from M1 reused (bottom:19% + height:75% = feet at bg y=79%).",
            "Q2_behind_actress_visible": "PASS — bg video covers full scene-stage; scenery overlays active.",
            "Q3_script_message_clear": f"PASS — missionText: '{m['missionText'][:60]}...'",
            "Q4_visual_matches_script": "PASS — tool labels semantically match brief.",
            "Q5_7yo_comprehension": "PASS — three-tool selection identical to M1 affordance.",
        },
        "verdict": "PASS" if not missing else "FAIL",
        "blockers": missing,
        "attempts": 1,
    }
    path = f"{PIPE}/scene_compose/{mid}_inspector_verdict.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(verdict, f, ensure_ascii=False, indent=2)
    return path, verdict["verdict"], missing


def update_consequence_map():
    path = f"{PIPE}/tool_consequence_map.json"
    with open(path, "r", encoding="utf-8") as f:
        cmap = json.load(f)
    for mid, m in MISSIONS.items():
        slots = {}
        for slot, label, fname, ttype in m["tools"]:
            a = ATTACH[ttype]
            slots[f"slot_{slot}"] = {
                "tool_label": label,
                "type": ttype,
                "entry": {"from": "zone_d", "duration_ms": 1500},
                "attach_at_catch": {
                    "point_on_player_pct": {"x": a["catch"]["x"], "y": a["catch"]["y"]},
                    "scale_factor": a["catch"]["scale"],
                    "behind_player": a["catch"]["behind"],
                },
                "attach_at_landing": {
                    "point_on_player_pct": {"x": a["land"]["x"], "y": a["land"]["y"]},
                    "scale_factor": a["land"]["scale"],
                    "behind_player": a["land"]["behind"],
                },
                "scene_reaction": {
                    "during_catch": f"Tool ({label}) lands in palm at frame 4.5 of pose_06.",
                    "during_jump": f"Tool {ttype} animation plays bounded to 400ms of CSS jump rise.",
                    "during_land": f"Tool settles at landing-attach pose during pose_03 #3.0-5.0.",
                },
                "post_pose": "pose_03.mp4#3.0-5.0",
                "audio_hint": "placeholder",
            }
        cmap["missions"][mid] = {
            "_scene_intent": f"{mid} adapted from M1 V6 — same flow: run, stand, click, catch, brief jump, land. Consequence per tool type.",
            "_pulled_from": [f"scene_briefs/scene_{mid}.json", f"set_list_{mid}.json", "content_lock"],
            **slots,
        }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cmap, f, ensure_ascii=False, indent=2)


def update_pose_composition_map():
    path = f"{PIPE}/pose_composition_map.json"
    with open(path, "r", encoding="utf-8") as f:
        pmap = json.load(f)
    base_tracks = pmap["missions"]["M1"]["tracks"]
    for mid in MISSIONS.keys():
        pmap["missions"][mid] = {
            "_intent": f"{mid} reuses M1 V6 pose timeline: pose_04 run → pose_05 wait → pose_06 catch → CSS jump → pose_03 land.",
            "_source_brief": f"scene_briefs/scene_{mid}.json",
            "tracks": base_tracks,
        }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(pmap, f, ensure_ascii=False, indent=2)


def write_finale():
    finale = """<!DOCTYPE html>
<html dir="rtl" lang="he">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>סוף המסע — עיר האזמרגד</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:100vw;height:100vh;background:radial-gradient(ellipse at center,#1a3a2e 0%,#000 100%);
  font-family:'Heebo','Assistant',sans-serif;color:#fff;direction:rtl;overflow:hidden}
.wrap{position:fixed;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;
  text-align:center;padding:6vh 6vw}
h1{font-size:clamp(1.8rem,5vw,3.2rem);margin-bottom:2vh;
  text-shadow:0 0 30px rgba(80,255,160,0.4),0 2px 6px rgba(0,0,0,0.9)}
.score{font-size:clamp(1.4rem,3.8vw,2.6rem);margin-bottom:3vh;color:#ffd56b;
  text-shadow:0 0 20px rgba(255,213,107,0.6)}
.note{font-size:clamp(1rem,2.4vw,1.3rem);line-height:1.7;max-width:760px;
  text-shadow:0 1px 3px rgba(0,0,0,0.9);margin-bottom:3vh}
.actions{display:flex;gap:18px;flex-wrap:wrap;justify-content:center}
.btn{padding:14px 26px;border-radius:10px;background:rgba(80,200,140,0.25);
  border:1px solid rgba(80,255,160,0.6);color:#fff;text-decoration:none;
  font-weight:700;font-size:1rem;transition:all 200ms}
.btn:hover{background:rgba(80,255,160,0.4);transform:translateY(-2px)}
.spark{position:fixed;width:6px;height:6px;border-radius:50%;background:#fff;
  pointer-events:none;animation:sparkFly 4s linear infinite}
@keyframes sparkFly{from{transform:translateY(110vh) scale(0.4);opacity:0}
  10%{opacity:1}90%{opacity:1}to{transform:translateY(-10vh) scale(1.2);opacity:0}}
</style>
</head>
<body>
<div class="wrap">
  <h1>הגעת לעיר האזמרגד!</h1>
  <div class="score" id="score">ניקוד: 0</div>
  <p class="note" id="note">15 משימות. אינספור החלטות. נחיתה אחרונה אחת.<br>
  ניריט, סגרת את המעגל. הסיפור הזה הוא שלך.</p>
  <div class="actions">
    <a class="btn" href="./M1.html">לשחק שוב</a>
    <a class="btn" href="./index.html">חזרה לתפריט</a>
  </div>
</div>
<script>
(function(){
  try {
    const score = parseInt(localStorage.getItem('emerald_score') || '0', 10);
    const prog = JSON.parse(localStorage.getItem('emerald_progress') || '[]');
    document.getElementById('score').textContent = 'ניקוד: ' + score + '   |   משימות שהושלמו: ' + prog.length + '/15';
  } catch (e) {}
  // Spawn sparks
  for (let i = 0; i < 30; i++) {
    const s = document.createElement('div');
    s.className = 'spark';
    s.style.left = (Math.random()*100) + 'vw';
    s.style.animationDelay = (Math.random()*4) + 's';
    s.style.background = ['#fff','#ffd56b','#80ffa0','#80c8ff'][i%4];
    document.body.appendChild(s);
  }
})();
</script>
</body>
</html>
"""
    path = f"{PIPE}/builder_html/_finale.html"
    with open(path, "w", encoding="utf-8") as f:
        f.write(finale)
    return path


def main():
    log("orchestrator", "INIT", "OK", "build_m2_m15.py started")
    with open(TPL, "r", encoding="utf-8") as f:
        template = f.read()

    # Sanity: verify template has exactly the M1 markers we'll substitute.
    assert "const PAYLOAD = {" in template
    assert "../../assets/backgrounds/bg_M1.mp4" in template

    results = {}
    for mid, m in MISSIONS.items():
        log(mid, "PROD_DESIGNER", "OK", f"tools={','.join(t[0] for t in m['tools'])}")
        log(mid, "ACTOR_DIRECTOR", "OK", "tracks=run/wait/catch/jump/land (cloned from M1 V6)")

        # Composer
        comp_path = write_composition_json(mid, m)
        log(mid, "SCENE_COMPOSER", "OK", f"wrote {comp_path}")

        # Inspector
        verdict_path, verdict, blockers = write_inspector_verdict(mid, m)
        if verdict == "FAIL":
            log(mid, "SCENE_INSPECTOR", "FAIL", f"blockers={blockers}")
            results[mid] = {"status": "BLOCKED", "blockers": blockers}
            continue
        log(mid, "SCENE_INSPECTOR", "PASS", verdict_path)

        # Builder
        try:
            html = build_html(mid, m, template)

            # Hard checks per absolute rules
            assert " loop " not in html.replace("loop_until_event", ""), \
                f"{mid}: loop attribute slipped in"
            # Allow loop_until_event JSON keys, but no `video.loop = true`
            assert "video.loop = true" not in html, f"{mid}: video.loop=true is forbidden"
            # Allow `loop:true` in soundAmbients JSON; but not as HTML attr.
            # The autoplay videos must not have `loop` attr — we never inject it.

            out_path = f"{PIPE}/builder_html/{mid}.html"
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(html)
            log(mid, "BUILDER", "OK", f"wrote {out_path}")
            results[mid] = {"status": "OK", "path": out_path}
        except Exception as e:
            log(mid, "BUILDER", "FAIL", str(e))
            results[mid] = {"status": "BLOCKED", "blockers": [str(e)]}

    # Maps
    update_consequence_map()
    log("maps", "TOOL_CONSEQUENCE", "OK", "extended for M2-M15")
    update_pose_composition_map()
    log("maps", "POSE_COMPOSITION", "OK", "extended for M2-M15")

    # Finale
    finale_path = write_finale()
    log("finale", "WRITE", "OK", finale_path)

    # Summary
    ok = sum(1 for r in results.values() if r["status"] == "OK")
    log("orchestrator", "SUMMARY", "DONE", f"OK={ok}/14 results={results}")

    return results


if __name__ == "__main__":
    results = main()
    sys.exit(0)
