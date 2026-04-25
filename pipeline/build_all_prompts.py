"""
Build prompt JSONs for ALL 45 tools (15 missions x 3).
Uses Camera Bible + rembg-aware object descriptions.
Writes to pipeline/prompts/<slug>.json with approved:true (agent self-approval).
"""
import json
from pathlib import Path

PROJECT = Path(r"C:/Users/azril/OneDrive/Desktop/fincail_game/new")
OUT = PROJECT / "pipeline" / "prompts"
OUT.mkdir(parents=True, exist_ok=True)

CAM = ("3/4 view angle, camera elevation 25-30 degrees, rotated 15 degrees right, "
       "hard directional key light from upper-left 10 oclock, "
       "isolated object on plain neutral studio background, product shot, "
       "clean sharp edges, stylized realism, cinematic game item, NOT cartoon, "
       "fills 65% of frame centered, square composition")

NEG_COMMON = ("human figure, person, hands, holding, gradient background, busy background, "
              "text, watermark, logo, cartoon style, anime, flat vector illustration, "
              "rusty, broken, damaged")

MODEL_PHOENIX = "aa77f04e-3eec-4034-9c07-d0f619684628"

# (slug, hebrew_label, mission, points, consequence, object_description, extra_negative)
TOOLS = [
    # M1 — risk / parachuting
    ("מצנח_מ01", "מצנח עגול רחב", "M1", 1, "deploy",
     "a large round circular parachute canopy fully open and inflated in mid-air, dome-shaped with orange and white radial segments, many visible suspension lines converging to a harness below, complete single canopy in isolation, 3D dome clearly visible",
     "person falling, closed parachute, deflated parachute, parachute pack, collapsed"),
    ("גלשן_מ01", "גלשן רחיפה", "M1", 2, "deploy",
     "a paragliding wing fully inflated in flight, elongated rectangular curved canopy with multiple cell sections, bright red and yellow stripes, thin suspension lines converging to a harness, complete single wing in isolation, streamlined 3D shape",
     "person, pilot, hang glider triangle frame, kite surfing"),
    ("כנפיים_מ01", "חליפת כנפיים", "M1", 3, "deploy",
     "a wingsuit flying suit laid out flat and slightly inflated, full body suit with fabric wing membranes stretched between arms and body and between legs, matte black fabric with red stripes, empty suit displayed as product, complete single unit in isolation",
     "person wearing suit, flying human, skydiver, model mannequin"),

    # M2 — stability
    ("ברזנט_מ02", "יריעת ברזנט", "M2", 1, "hold",
     "a heavy-duty olive-green canvas tarpaulin tightly rolled into a cylindrical bundle, visible brass grommets along the edge, coarse canvas fabric texture, tie-down ropes wrapped around the bundle, complete single rolled tarp in isolation, strong 3D cylindrical form with clear shadows",
     "open flat tarp spread out, plastic sheet, clear plastic"),
    ("פטיש_מ02", "פטיש ומסמרים", "M2", 2, "use",
     "classic carpenter claw hammer with wooden handle and polished steel head, small pile of 5-6 steel nails arranged in a fan next to the hammer, both items as one composed product shot, complete single set in isolation",
     "hammered into wood, workshop scene, tool belt"),
    ("אוהל_מ02", "אוהל סיירים", "M2", 3, "deploy",
     "compact expedition dome tent fully pitched and standing, 2-person ridge-style tent with taut green-and-khaki outer fly, visible guy lines and tent pegs at ground, small zippered entrance at front, complete single tent unit in isolation",
     "camper inside tent, campfire, forest background, collapsed tent"),

    # M3 — FOMO
    ("מפה_מ03", "המפה המקומטת", "M3", 1, "reveal",
     "an old crumpled treasure map on aged parchment paper, visible creases and wrinkles across the paper, hand-drawn trail markings and a large red X, slightly curled edges, lying flat as a single sheet, complete map in isolation",
     "rolled scroll, book, modern paper, printed map"),
    ("משקפת_מ03", "משקפת שדה", "M3", 2, "reveal",
     "a pair of military field binoculars with twin black rubber-coated barrels, central focus wheel, neck strap attached, two eyepieces at rear, one handheld unit standing upright, complete single binoculars in isolation",
     "single monocular, spyglass, telescope, opera glasses"),
    ("מפתח_מ03", "מפתח לטרקטורון מונע", "M3", 3, "commit",
     "a single metal ignition key with a black plastic head embossed with an ATV logo, short silver metal shank with cut teeth, keyring with small tag attached, one key alone isolated",
     "bunch of keys, keychain with many keys, padlock, door lock"),

    # M4 — risk
    ("קרשים_מ04", "לוחות עץ ופטיש", "M4", 1, "build",
     "a stack of 4-5 rough-cut wooden planks neatly piled with a carpenter hammer resting on top, pine wood color with visible grain, squared boards roughly 1x4 inches cross-section, complete single stack in isolation",
     "workshop, sawmill, many tools, cluttered scene"),
    ("רתמה_מ04", "רתמת אבטחה", "M4", 2, "secure",
     "a climbing safety harness with bright red and black nylon webbing, leg loops and waist belt clearly visible, large steel belay loop at front, several aluminum gear carabiners attached, single harness displayed flat open, complete unit in isolation",
     "person wearing harness, climber, backpack"),
    ("רובה_חבלים_מ04", "רובה חבלים", "M4", 3, "deploy",
     "a line-throwing rope gun with pistol grip and launcher barrel, thin black rope coiled into a compact cylinder below the barrel, matte black tactical finish, complete single device in isolation, 3D mechanical shape clearly visible",
     "real firearm, handgun, shotgun"),

    # M5 — impulse
    ("פנס_עוצמתי_מ05", "פנס עוצמתי", "M5", 1, "investigate",
     "a heavy-duty tactical handheld flashlight torch, cylindrical aluminum tube body with knurled grip, small reflector bowl at the front with a tiny LED bulb in center, rear push-button end cap, matte black finish, complete single torch in isolation",
     "camera, DSLR, lens, industrial equipment, lantern"),
    ("רשת_מ05", "רשת הגנה", "M5", 2, "defend",
     "a heavy protective mesh net bundled into a compact rolled package, thick dark-grey rope netting with square grid pattern, edges tied with cord, complete single bundle in isolation, rope texture clearly visible",
     "fishing net spread out, spider web, chain link fence"),
    ("לפיד_מ05", "לפיד בוער", "M5", 3, "attack",
     "a burning wooden torch held upright, thick wooden handle wrapped with oil-soaked rags at the top, bright orange and yellow flames rising above, slight smoke wisp, complete single torch in isolation",
     "candle, lighter, matchstick, flashlight, campfire on ground"),

    # M6 — stability
    ("גריקן_מ06", "ג'ריקן שמן", "M6", 1, "refuel",
     "a metal jerry can fuel container, rectangular riveted steel body painted matte dark green, large screw cap on top, side carry handle, complete single can standing upright in isolation",
     "plastic jug, gas pump, barrel"),
    ("ערכה_מ06", "ערכת כלי עבודה", "M6", 2, "repair",
     "an open red steel toolbox tray with compartments, containing a wrench, screwdriver, pliers and socket set arranged neatly inside, all visible as one composed set, complete single toolkit in isolation",
     "cluttered workshop, wall of tools, tool belt"),
    ("אופניים_מ06", "אופני הרים", "M6", 3, "escape",
     "a mountain bike bicycle with thick knobby tires, front suspension fork, dual disc brakes, black and red frame, handlebars and seat clearly visible, complete single bike standing on its kickstand in side-3/4 view in isolation",
     "rider on bike, BMX, racing road bike, motorcycle"),

    # M7 — FOMO
    ("דגל_מ07", "דגל המשימה המקורי", "M7", 1, "claim",
     "a small cloth expedition flag on a wooden pole, triangular red pennant with a gold emblem, pole planted upright as if stuck in ground, complete single flag in isolation, cloth slight wave",
     "national flag, large flag, flagpole stadium"),
    ("פריסקופ_מ07", "פריסקופ", "M7", 2, "scout",
     "a handheld periscope optical device, tall vertical matte-green metal tube with an angled eyepiece at the bottom and a top prism window at the top, L-shape, complete single periscope in isolation",
     "submarine, telescope, microscope"),
    ("לום_מ07", "לום ברזל", "M7", 3, "force",
     "a heavy iron crowbar pry bar, long black metal rod with curved claw hook at one end and flat wedge tip at other, matte black forged iron finish, complete single crowbar in isolation",
     "hammer, pickaxe, axe, weapon"),

    # M8 — risk
    ("סולם_חבלים_מ08", "סולם חבלים", "M8", 1, "climb",
     "a rope ladder with wooden rungs and two parallel ropes, full ladder visible, hanging vertically, eight horizontal wooden rungs evenly spaced between two straight parallel hemp-colored side ropes, complete single ladder in isolation",
     "rigid ladder, metal ladder, step stool, folded ladder"),
    ("חבל_קשרים_מ08", "חבל עם קשרים", "M8", 2, "climb",
     "a thick climbing rope with multiple large overhand knots tied along its length at regular intervals, hanging vertically, hemp-colored natural fiber rope, 6-7 visible knots, complete single rope in isolation",
     "smooth rope, ladder, chain"),
    ("טפרי_טיפוס_מ08", "טפרי טיפוס ממתכת", "M8", 3, "climb",
     "a pair of metal climbing claws, curved steel spikes mounted on leather palm straps with adjustable buckles, sharp pointed talons, both claws displayed side by side, complete single pair in isolation",
     "bear claw, animal paw, garden tool"),

    # M9 — stability
    ("שמן_מ09", "שמן לשימון צירים", "M9", 1, "lubricate",
     "a small can of machine lubricating oil, blue metal can with a long thin spout nozzle, visible label area, complete single can in isolation, standing upright",
     "cooking oil bottle, soda can, gasoline"),
    ("רב_כלי_מ09", "רב-כלי", "M9", 2, "fix",
     "a stainless steel multi-tool with pliers head opened and several folded tools visible, knife blade, screwdriver, scissors partially fanned out, complete single multi-tool in isolation",
     "swiss army knife closed, single knife, wrench"),
    ("מבער_מ09", "מבער ריתוך", "M9", 3, "cut",
     "a handheld welding torch with brass nozzle at the tip and connected thin hose trailing behind, blue steel body, complete single torch in isolation, 3D mechanical shape",
     "propane tank, flamethrower, bunsen burner"),

    # M10 — impulse
    ("מצלמה_זעירה_מ10", "מצלמה זעירה", "M10", 1, "document",
     "a tiny spy camera, small square black body with a prominent single round lens at front, minimal buttons, sits in the palm of a hand sized, complete single camera in isolation",
     "DSLR camera, phone, flashlight"),
    ("שמיכה_מ10", "שמיכת מיגון", "M10", 2, "shield",
     "a rolled up emergency fire-protection blanket in a hard plastic case, thick silver foil material visible at the opening, red case with white lettering area, complete single kit in isolation",
     "regular blanket, towel, picnic mat"),
    ("קאטר_מ10", "קאטר לחיתוך חוטים", "M10", 3, "cut",
     "a pair of heavy-duty wire cutters with red rubber-coated handles and steel jaws, jaws slightly open, complete single cutter in isolation",
     "scissors, pliers, knife"),

    # M11 — risk
    ("סנפלינג_מ11", "חבל סנפלינג עם רתמה", "M11", 1, "descend",
     "a coiled climbing rappel rope in bright blue and a harness with belay device carabiner attached, rope neatly coiled in circular loops, harness draped next to it, complete single set in isolation",
     "person rappelling, cliff, full rock wall"),
    ("בנגי_מ11", "חבל בנג'י", "M11", 2, "jump",
     "a thick bungee cord with elastic rubber core wrapped in colorful nylon sheath, coiled into a tight loop, large steel carabiner attached at one end, complete single cord in isolation",
     "person jumping, bridge, tower"),
    ("מצנח_בסיס_מ11", "מצנח בסיס", "M11", 3, "jump",
     "a base jumping parachute pack, compact rectangular backpack container with visible pilot chute handle, black fabric body with yellow accents, single small pack in isolation",
     "deployed parachute, large canopy, person wearing pack"),

    # M12 — FOMO
    ("כרטיס_מ12", "כרטיס עלייה לסירה", "M12", 1, "board",
     "a paper boat boarding pass ticket, cream colored card stock with printed passage text and a boat illustration, slightly weathered edges, lying flat, complete single ticket in isolation",
     "airplane ticket, credit card, passport"),
    ("מצלמה_פלאש_מ12", "מצלמה עם פלאש", "M12", 2, "document",
     "a vintage film camera with a large round silver flash bulb attached on top, black leather-wrapped body, single round lens at front, complete single camera in isolation",
     "modern DSLR, phone camera, spy camera tiny"),
    ("לפיד_יד_מ12", "לפיד יד בוער", "M12", 3, "signal",
     "a handheld road safety flare stick burning brightly, red cylindrical body with intense orange-red flame and visible smoke trail rising from top, complete single flare in isolation",
     "dynamite, firework, candle"),

    # M13 — stability
    ("סרגל_מ13", "סרגל ומחק", "M13", 1, "measure",
     "a wooden straight ruler with black numbered markings and a pink rubber eraser next to it, both items as one composed product shot, complete single set in isolation",
     "pen, pencil, notebook"),
    ("מצפן_מ13", "מצפן כיס", "M13", 2, "navigate",
     "a brass pocket compass with ornate round case, hinged lid open, visible compass rose dial with N-E-S-W markings and a red magnetic needle, complete single compass in isolation",
     "pocket watch, clock, sundial"),
    ("רחפן_מ13", "רחפן ניווט", "M13", 3, "scout",
     "a quadcopter navigation drone with four horizontal rotor arms and propellers, sleek white and black body, small camera gimbal underneath, landing skids, complete single drone in isolation",
     "airplane, helicopter, toy"),

    # M14 — risk
    ("מטבעות_מ14", "שקית מטבעות קטנה", "M14", 1, "take",
     "a small brown leather drawstring coin pouch bag, tied closed at the top, a few gold coins spilling out onto the surface next to it, complete single pouch in isolation",
     "modern wallet, large bag, treasure chest"),
    ("תיבה_מ14", "תיבת עץ נעולה", "M14", 2, "take",
     "a small ornate locked wooden chest box, dark stained wood with brass metal corner fittings and a prominent brass padlock on front, closed lid, complete single chest in isolation",
     "open chest, pirate treasure scene"),
    ("כדור_בדולח_מ14", "כדור בדולח כהה", "M14", 3, "take",
     "a dark smoky crystal ball orb resting on a small carved black wooden stand, smoky grey-purple translucent sphere with internal swirls, complete single orb with stand in isolation",
     "glass marble, snow globe, disco ball"),

    # M15 — FOMO
    ("דגל_סיום_מ15", "דגל סיום לבן", "M15", 1, "finish",
     "a white finish-line flag on a wooden pole, rectangular plain white cloth flag with black checkered border, pole planted upright, complete single flag in isolation",
     "racing checkered flag full, stadium, crowd"),
    ("מגאפון_מ15", "מגאפון", "M15", 2, "signal",
     "a handheld red megaphone bullhorn, conical wide red speaker with grey mouthpiece and pistol grip with trigger, small visible speaker grill on side, complete single megaphone in isolation",
     "microphone, speaker stack, radio"),
    ("זיקוק_מ15", "זיקוק צבעוני", "M15", 3, "celebrate",
     "a single firework rocket stick standing upright on a small base, long wooden stick with colorful paper tube body, fuse at top, cardboard cylinder with star pattern, complete single firework in isolation",
     "exploding firework sky, fireworks display, sparkler"),
]

TEMPLATE_SKIP_IF_EXISTS = False  # overwrite all

def build_prompt(obj_desc):
    return f"{obj_desc}, {CAM}"

def build(slug, label, mission, points, consequence, obj_desc, extra_neg):
    neg = f"{extra_neg}, {NEG_COMMON}"
    data = {
        "asset": slug,
        "label_verbatim": label,
        "target_path": f"assets/tools/{slug}.png",
        "type": "tool_item",
        "source_mission": f"{mission} slot {'A' if points==1 else 'B' if points==2 else 'C'}",
        "consequence_type": consequence,
        "points": points,
        "scene_context": f"{mission} — {label}",
        "pipeline_version": "0E_rembg_v1",
        "prompts": {
            "leonardo": build_prompt(obj_desc),
            "leonardo_negative": neg,
        },
        "leonardo_params": {
            "modelId": MODEL_PHOENIX,
            "width": 1024,
            "height": 1024,
            "num_images": 1,
            "alchemy": True,
            "photoReal": False,
        },
        "directors_note": f"{label} — single isolated object per Camera Bible, sharp edges for rembg.",
        "approved": True,
        "_approved_at": "2026-04-20",
        "_approved_by": "director + production_designer (Claude agent roles) per camera_bible.json + pipeline v0E_rembg_v1",
    }
    return data


def main():
    written = []
    skipped = []
    for tool in TOOLS:
        slug, label, mission, points, consequence, obj_desc, extra_neg = tool
        path = OUT / f"{slug}.json"
        if path.exists() and TEMPLATE_SKIP_IF_EXISTS:
            skipped.append(slug)
            continue
        data = build(slug, label, mission, points, consequence, obj_desc, extra_neg)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        written.append(slug)
    print(f"Wrote {len(written)} prompts, skipped {len(skipped)}.")
    print("Total tools in catalog:", len(TOOLS))
    (PROJECT / "pipeline" / "all_tools_catalog.json").write_text(
        json.dumps([t[0] for t in TOOLS], ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


if __name__ == "__main__":
    main()
