"""
Round 2 — Targeted prompt rewrites for 26 FAIL tools.
Each prompt is fully rewritten to address the specific failure mode.
Marks _retry_attempt=1 on each tool, wipes old generated files.
"""
import json
from pathlib import Path

PROJECT = Path(r"C:/Users/azril/OneDrive/Desktop/fincail_game/new")
PROMPTS = PROJECT / "pipeline" / "prompts"
QA = PROJECT / "pipeline" / "review" / "tools_qa"
STATE = PROJECT / "pipeline" / "loop_state.json"

CAM = ("3/4 view angle, camera elevation 25-30 degrees, rotated 15 degrees right, "
       "hard directional key light from upper-left 10 oclock, "
       "isolated object on plain neutral studio background, product shot, "
       "clean sharp edges, stylized realism, cinematic game item, NOT cartoon, "
       "fills 65% of frame centered, square composition, prominent 3D subject")

NEG_COMMON = ("human figure, person, hands, holding, gradient background, busy background, "
              "text, watermark, logo, cartoon style, anime, flat vector illustration")

# slug -> (new_leonardo_prompt, extra_negative)
REWRITES = {
    "גלשן_מ01": (
        "a paraglider wing gliding canopy, elongated rectangular RECTANGULAR curved fabric wing "
        "with visible cell sections along the leading edge, bright red and yellow stripes, "
        "thin suspension lines hanging down converging to a harness seat below, "
        "wing shown from below slight angle, NOT a sphere NOT a balloon NOT a dome",
        "hot air balloon, round balloon, sphere, globe, dome shape"
    ),
    "דגל_מ07": (
        "a small handheld expedition pennant flag, thick tall sturdy wooden pole planted upright "
        "into soft ground, triangular bright RED cloth pennant attached to top, "
        "visible gold circular emblem embroidered on the flag cloth, "
        "flag slightly waving, entire pole and flag together in one tall composition",
        "national flag, stadium flag, large flagpole, modern signage"
    ),
    "דגל_סיום_מ15": (
        "a plain simple white finish flag on a wooden pole: solid pure WHITE rectangular cloth "
        "with a thin narrow black-and-white CHECKERED border strip running along the right edge only, "
        "no central design, no text, no symbol, clean white field, attached to a vertical wooden pole "
        "planted in ground",
        "black circle, letters, text, complex pattern, stadium flag, fully checkered flag"
    ),
    "זיקוק_מ15": (
        "a single amateur celebration firework rocket stick, thin cylindrical cardboard body "
        "about 30cm tall with colorful wrapper, short black fuse poking out the top, "
        "mounted on a small wooden or cardboard LAUNCH BASE flat and stable, whole item small-scale, "
        "like a consumer hobby rocket firework sold in shops",
        "statue, monument, obelisk, tower, rocket launch pad, space rocket"
    ),
    "חבל_קשרים_מ08": (
        "a single thick hemp-colored climbing rope hanging vertically straight down from top of frame, "
        "with SIX very prominent LARGE OVERHAND KNOTS tied along its length at regular intervals, "
        "each knot is a clearly visible bulging bulb thicker than the rope itself, "
        "rope strictly straight vertical, knots like beads on a string",
        "coiled rope, looped rope, tangled rope, smooth rope without knots"
    ),
    "טפרי_טיפוס_מ08": (
        "a matching PAIR of metal tree-climbing spike claws, two identical curved steel talons "
        "mounted on brown leather PALM straps with buckles, both claws laid flat side by side, "
        "mirror image of each other, both fully visible, symmetric pair composition",
        "single claw, animal paw, bear paw, fork, garden tool"
    ),
    "כנפיים_מ01": (
        "an empty unworn wingsuit flying suit DISPLAYED FLAT on an invisible mannequin as a product shot, "
        "full body jumpsuit with large fabric WING MEMBRANES stretched between the arms and body "
        "and between the legs, matte black fabric with red accent stripes, "
        "suit is unoccupied and empty, no person inside, no face, no head visible, "
        "suit floating on neutral background like a clothing catalog shot",
        "person wearing suit, body, head, face, human figure inside"
    ),
    "כרטיס_מ12": (
        "a single paper boat boarding pass TICKET card, rectangular cream-colored card stock paper "
        "lying flat on the surface, printed with bold black text BOARDING PASS and a small boat logo, "
        "weathered slightly torn edges, paper ticket only, nothing else in frame, "
        "FLAT PRINTED PAPER CARD",
        "physical boat, ship, vessel, marine vehicle, 3D model of boat"
    ),
    "לום_מ07": (
        "a full-length iron crowbar pry bar, long straight black forged-iron metal rod "
        "about 60cm long shown in its ENTIRE length diagonally across frame, "
        "one end has a curved claw hook for pulling nails, other end has a flat chisel wedge tip, "
        "both ends clearly visible, matte black finish with slight highlights",
        "partial view, cropped tool, hammer, axe"
    ),
    "לפיד_יד_מ12": (
        "a handheld road safety flare stick ACTIVELY BURNING, red cylindrical body held vertically, "
        "bright intense ORANGE-RED FLAME shooting out the top about 20cm tall with bright glow, "
        "visible pale smoke curling upward from flame, "
        "flare stick and flame both fully visible in frame, nighttime feel with ambient glow",
        "unlit, no fire, extinguished, candle, lighter, matchstick"
    ),
    "לפיד_מ05": (
        "a complete wooden torch held upright, the ENTIRE torch visible top to bottom in frame: "
        "long wooden handle at bottom, oil-soaked rags wrapped at the top, and LARGE ORANGE FLAME "
        "rising above the rags with visible smoke, all elements fit comfortably inside the square "
        "frame with margin on all sides",
        "cropped, partial, flame cut off, handle cut off"
    ),
    "מפה_מ03": (
        "a large crumpled old TREASURE MAP on thick beige PARCHMENT PAPER laid flat, "
        "deep wrinkles and creases across the paper surface, hand-drawn trail lines in brown ink, "
        "a prominent red X mark in the center, slightly curled and torn edges, "
        "full map sheet fills most of the square frame, strong pronounced paper texture",
        "modern paper, printed map, book, scroll rolled up"
    ),
    "מפתח_מ03": (
        "a single automobile ignition key, black plastic OVAL head with a small embossed logo, "
        "long silver metal shank with visible notched teeth cut along one edge, "
        "key laid flat on the surface horizontally, small metal keyring loop attached to the head, "
        "SINGLE KEY ONLY, clearly a car ignition key",
        "faucet, tap, water valve, bottle opener, many keys, keychain bunch"
    ),
    "מצלמה_פלאש_מ12": (
        "a vintage 1960s film camera with a LARGE round silver FLASH REFLECTOR DISH clearly "
        "mounted on TOP of the camera body, flash reflector is prominent about half the size of "
        "the camera body, black leather-wrapped camera body, round front lens, "
        "camera sits on a flat surface, flash unit is the dominant feature at the top",
        "no flash, modern DSLR, smartphone camera, tiny spy camera, video camera"
    ),
    "מצנח_בסיס_מ11": (
        "a BASE-JUMPING parachute rig container, compact low-profile rectangular PACK worn on back, "
        "small square shape with visible PILOT CHUTE fabric pouch bulging at the bottom corner, "
        "prominent yellow-and-white pilot chute handle dangling, padded shoulder straps and chest "
        "strap visible, black nylon fabric, shown as a product on stand, not being worn",
        "hiking backpack, tactical backpack, duffel bag, hydration pack"
    ),
    "סולם_חבלים_מ08": (
        "a rope ladder with flat WOODEN PLANK RUNGS: two parallel vertical hemp-colored ropes running "
        "top to bottom, with SEVEN FLAT HORIZONTAL WOODEN PLANKS connecting them as rungs, "
        "evenly spaced at regular intervals, each rung is a small wooden board about the width of "
        "a foot, ladder hangs straight vertically, full ladder visible top to bottom, rungs are "
        "the prominent feature",
        "ropes only, no rungs, metal ladder, step ladder, tangled ropes"
    ),
    "סנפלינג_מ11": (
        "a climbing rappel rope arranged as a neat CIRCULAR COIL of bright blue rope laid flat on "
        "the ground, about 40cm diameter coil with 8 or so loops, "
        "AND next to it a black nylon CLIMBING HARNESS with visible leg loops, waist belt, and a "
        "silver belay device carabiner attached, both items together as one composition in frame",
        "person rappelling, cliff, single sling, rope alone without harness"
    ),
    "סרגל_מ13": (
        "a wooden ruler straight stick with black numbered inch and centimeter markings along one edge "
        "LYING FLAT, AND a separate rectangular PINK RUBBER ERASER block next to it, "
        "BOTH items side by side as two DISTINCT OBJECTS in one composition, "
        "eraser is a soft pink rectangular brick clearly separate from the ruler",
        "two rulers, one L-shape, missing eraser, pen, pencil"
    ),
    "פריסקופ_מ07": (
        "a simple L-SHAPED handheld periscope: one tall straight VERTICAL matte-olive metal tube about "
        "40cm long, connected at the bottom via a 90-DEGREE ELBOW BEND to a short HORIZONTAL tube "
        "about 10cm long that sticks out to the side, at the top of vertical tube is a small angled "
        "prism window, at the end of horizontal tube is a round eyepiece, like a cartoon submarine "
        "periscope in shape, clean simple mechanical design",
        "abstract gadget, sci-fi device, microscope, binoculars, complex machinery"
    ),
    "קאטר_מ10": (
        "a COMPLETE pair of heavy-duty wire cutter pliers in FULL view, both red rubber-coated "
        "handles at bottom AND steel jaws at top fully visible within the frame, "
        "jaws slightly open, the entire tool comfortably fits inside the square frame with margin, "
        "nothing cropped, nothing cut off",
        "cropped image, handles missing, partial tool, scissors"
    ),
    "קרשים_מ04": (
        "a small stack of 4 RECTANGULAR wooden PLANKS boards piled neatly on top of each other, "
        "pine-colored wood with visible grain, AND a CARPENTER HAMMER with wooden handle and steel "
        "head RESTING ON TOP of the stack clearly visible at the top, hammer is the prominent "
        "second element, both items together as one composed group",
        "only planks, no hammer, workshop scene, many tools"
    ),
    "רובה_חבלים_מ04": (
        "a rope-throwing LINE LAUNCHER tool: chunky orange and black PLASTIC body shaped like a power "
        "tool or caulking gun, with a wide cylindrical ROPE CANISTER attached to the side containing "
        "coiled white nylon rope with a grappling hook sticking out the nose, bright orange safety "
        "plastic casing, obviously a utility device NOT a firearm",
        "real gun, firearm, pistol, handgun, revolver, rifle, weapon, metal gun"
    ),
    "רשת_מ05": (
        "a heavy PROTECTIVE MESH NET rolled into a large compact BUNDLE CYLINDER about 40cm long, "
        "thick dark-grey CORDED ROPE strands forming a visible square grid pattern, "
        "3D bulging cylindrical bundle shape with strong shadows, edges tied with cord, "
        "net bundle is thick and opaque, prominent subject",
        "thin wire mesh, spider web, transparent net, fishing net spread out, wire fence"
    ),
    "רתמה_מ04": (
        "a FULL climbing safety harness displayed open flat as a product: two separate leg loop "
        "circles at the bottom, a closed waist belt ring at the top, connecting strap between them, "
        "prominent steel BELAY LOOP at the front center, several silver GEAR CARABINERS clipped to "
        "gear loops along the waist belt, bright red and black NYLON WEBBING throughout, "
        "entire harness unit visible and intact",
        "only buckle, partial strap, small clip, missing leg loops"
    ),
    "שמיכה_מ10": (
        "an emergency FIRE-PROTECTION BLANKET kit: a rectangular SILVER MYLAR FOIL BLANKET folded and "
        "partially pulled out of a small SQUARE RED HARD-SHELL CASE, shiny metallic silver foil "
        "clearly visible as the main feature, red case with 'FIRE BLANKET' text area, "
        "both case and folded silver blanket visible together",
        "paper packaging, document case, laptop case, regular blanket"
    ),
    "שמן_מ09": (
        "a small TEAR-DROP shaped LUBRICATING OIL can, narrow curved body with a LONG THIN CURVED "
        "METAL SPOUT NOZZLE projecting upward at the top for precision lubrication application, "
        "blue enamel body with simple label area, like a classic 3-in-1 oil sewing machine oil can, "
        "the long thin spout is the MOST PROMINENT visual feature",
        "paint can, paint bucket, cylindrical can, spray can, bottle, no spout"
    ),
}


def update_prompt(slug, new_prompt, extra_neg):
    path = PROMPTS / f"{slug}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["prompts"]["leonardo"] = f"{new_prompt}, {CAM}"
    data["prompts"]["leonardo_negative"] = f"{extra_neg}, {NEG_COMMON}"
    data["_retry_attempt"] = data.get("_retry_attempt", 0) + 1
    data["_rewrite_round"] = 2
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    # wipe old generated files
    for suffix in ("_raw.png", "_rembg.png", "_final.png"):
        f = QA / f"{slug}{suffix}"
        if f.exists():
            f.unlink()


def main():
    state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {"tools": {}}
    done = []
    for slug, (new_p, neg) in REWRITES.items():
        update_prompt(slug, new_p, neg)
        state["tools"].pop(slug, None)  # let the runner re-generate
        done.append(slug)
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Rewrote {len(done)} prompts and cleared their state entries.")
    print(", ".join(done))


if __name__ == "__main__":
    main()
