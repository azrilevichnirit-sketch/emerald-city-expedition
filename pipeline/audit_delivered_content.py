"""Final visual content audit — director panel + QA on EVERY approved asset.

Per-type rubrics loaded from final_audit_brief.md + design_system.md.

Categories (98 total visual checks):
  - 18 backgrounds (mp4 keyframe)
  - 7 transitions (mp4 keyframe)
  - 51 scenery props (png)
  - 15 TOOL TRIPLES (3 tools per mission shown side-by-side — checks visual bias)
  - 7 poses (mp4 keyframe)

Incremental save + resume. Zero Veo/Imagen calls — vision-only audits.
Output: pipeline/review/_final_content_audit.json
"""
import base64
import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from PIL import Image

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "pipeline"))
from debate_runner import call_engine, call_gemini
from resolve_via_panel import _parse_json, ENGINES

# ── paths ──
ASSETS_BG = PROJECT / "assets" / "backgrounds"
ASSETS_TRANS = PROJECT / "assets" / "transitions"
ASSETS_SCENERY = PROJECT / "assets" / "scenery"
ASSETS_TOOLS = PROJECT / "assets" / "tools"
ASSETS_PLAYER = PROJECT / "assets" / "player"

REVIEW_DIR = PROJECT / "pipeline" / "review"
KF_CACHE = REVIEW_DIR / "_audit_keyframes"
KF_CACHE.mkdir(parents=True, exist_ok=True)
OUT_PATH = REVIEW_DIR / "_final_content_audit.json"

LOCK = json.loads((PROJECT / "content_lock.json").read_text("utf-8"))
AUDIT_BRIEF = (PROJECT / "pipeline" / "final_audit_brief.md").read_text("utf-8")
DESIGN_SYS = (PROJECT / "design_system.md").read_text("utf-8")

# Compact context for panel prompts (avoid blowing tokens)
SHORT_BRIEF = (
    "Final audit rules (from final_audit_brief.md):\n"
    "- No MODEL-INVENTED text/logos/watermarks/subtitles/fake brands.\n"
    "  (small brand-like marks that a player wouldn't notice at game-size are OK.)\n"
    "- INTENTIONAL text is allowed if the brief calls for it (e.g. FINISH flag).\n"
    "- No visual bias: assets that imply a 'correct' choice are flagged.\n"
    "- Tools in the same mission MUST look equally recognisable — no tool\n"
    "  should DOMINATE the frame (size, occupied area, number of elements)\n"
    "  compared to the others. Note: tools are ALWAYS shown on flat green screen\n"
    "  chroma (#00B140) — IGNORE lighting/shadow/ambient differences; those come\n"
    "  from the tool's pose, not lighting. Judge SIZE, DETAIL COUNT, and whether\n"
    "  any tool includes an unintended element (e.g. human figure integrated).\n"
    "- Scenery PNGs: prop on solid flat green #00B140 (Builder will chroma-key).\n"
    "\n"
    "OPERATIONAL NOTES RULE:\n"
    "When you flag something, write ONE concrete actionable fix — NOT a philosophical\n"
    "reason. Good: 'shrink wingsuit by ~30% to match parachute frame size', 'blur\n"
    "bottom-right 80px to mask watermark', 'remove extra nails around hammer'. Bad:\n"
    "'creates measurement corruption', 'breaks composition harmony'. If you cannot\n"
    "name a concrete fix, return verdict=pass.\n"
)

# ── helpers ──
def extract_keyframe(mp4, t=1.0):
    kf = KF_CACHE / f"{mp4.stem}_kf.png"
    if not kf.exists():
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-ss", str(t),
             "-i", str(mp4), "-vframes", "1", "-q:v", "2", str(kf)],
            check=True,
        )
    return kf


def b64(p):
    return base64.b64encode(Path(p).read_bytes()).decode("ascii")


def _v(resp):
    return _parse_json(resp) if resp else {"verdict": "fail", "notes": "no response"}


def _qa(instr, img_b64):
    return _v(call_gemini(instr, "QA this asset.", image_b64=img_b64, max_tokens=400))


def _panel(system, user, img_b64):
    votes = {}
    for eng in ENGINES:
        try:
            votes[eng] = _v(call_engine(eng, system, user, image_b64=img_b64, max_tokens=400))
        except Exception as e:
            votes[eng] = {"verdict": "fix", "notes": f"engine error: {e}"}
    return votes


def _decide(qa, votes):
    """Final verdict: pass if QA=pass AND 2+ directors pass.
    fix if 1+ director says fix. fail otherwise."""
    pass_count = sum(1 for v in votes.values() if v.get("verdict") == "pass")
    fix_count = sum(1 for v in votes.values() if v.get("verdict") == "fix")
    qa_pass = qa.get("verdict") == "pass"
    if qa_pass and pass_count >= 2:
        return "pass"
    if fix_count >= 1 or pass_count == 1:
        return "fix"
    return "fail"


# ── per-type audits ──
def audit_bg(slug, mp4_path, mission_id):
    kf = extract_keyframe(mp4_path)
    ib = b64(kf)
    m = LOCK["missions"][mission_id]
    qa_instr = (
        f"{SHORT_BRIEF}\nAsset type: BACKGROUND video keyframe. Serves mission {mission_id}.\n"
        f"Mission text: {m['mission_text']}\n"
        "Fail ONLY if: hallucinated text/logos, prominent humans in foreground, "
        "or cartoon/illustration style. Tiny/distant background figures are OK.\n"
        'STRICT JSON: {"verdict":"pass|fail","notes":"..."}'
    )
    qa = _qa(qa_instr, ib)
    system = (
        "You are 1 of 3 Studio Emerald directors doing the FINAL visual audit.\n"
        f"{SHORT_BRIEF}\n"
        f"Asset type: BACKGROUND video keyframe. Mission {mission_id}: {m['mission_text']}\n"
        "Judge: (a) does it read as this mission's location, (b) any hallucinated "
        "text/logos, (c) any prominent foreground humans that conflict with the "
        "layered player, (d) visual bias toward any narrative direction.\n"
        'STRICT JSON: {"verdict":"pass|fix|fail","notes":"one sentence"}'
    )
    votes = _panel(system, f"Review bg keyframe for {slug}.", ib)
    return {"type": "background", "slug": slug, "mission": mission_id,
            "qa": qa, "panel": votes, "verdict": _decide(qa, votes)}


def audit_transition(slug, mp4_path):
    kf = extract_keyframe(mp4_path)
    ib = b64(kf)
    qa_instr = (
        f"{SHORT_BRIEF}\nAsset type: TRANSITION video keyframe — full-screen bg "
        "between missions, 2 seconds. Player is NOT in this clip.\n"
        "Fail ONLY if: hallucinated text/logos, cartoon/illustration style, "
        "or prominent foreground humans.\n"
        'STRICT JSON: {"verdict":"pass|fail","notes":"..."}'
    )
    qa = _qa(qa_instr, ib)
    system = (
        "You are 1 of 3 Studio Emerald directors doing the FINAL visual audit.\n"
        f"{SHORT_BRIEF}\n"
        f"Asset type: TRANSITION video keyframe for {slug}. Full-screen bg, "
        "2-second inter-mission clip.\n"
        "Judge: (a) cinematic quality, (b) any hallucinated text/logos, "
        "(c) any prominent foreground humans.\n"
        'STRICT JSON: {"verdict":"pass|fix|fail","notes":"one sentence"}'
    )
    votes = _panel(system, f"Review transition keyframe for {slug}.", ib)
    return {"type": "transition", "slug": slug,
            "qa": qa, "panel": votes, "verdict": _decide(qa, votes)}


def audit_scenery(slug, png_path, mission_hint=""):
    ib = b64(png_path)
    qa_instr = (
        f"{SHORT_BRIEF}\nAsset type: SCENERY PROP PNG (compositor layer).\n"
        f"Slug: {slug}.  Mission context: {mission_hint}\n"
        "Expectation: single isolated prop on neutral bg (removable) OR clean alpha.\n"
        "Fail ONLY if: hallucinated text/logos, cartoon style, or multiple "
        "competing subjects in one image.\n"
        'STRICT JSON: {"verdict":"pass|fail","notes":"..."}'
    )
    qa = _qa(qa_instr, ib)
    system = (
        "You are 1 of 3 Studio Emerald directors doing the FINAL visual audit.\n"
        f"{SHORT_BRIEF}\n"
        f"Asset type: SCENERY PROP PNG. Slug: {slug}. Context: {mission_hint}\n"
        "Judge: (a) recognisable as the intended prop, (b) hallucinated text/"
        "logos, (c) cinematic photorealistic style, (d) clean isolation.\n"
        'STRICT JSON: {"verdict":"pass|fix|fail","notes":"one sentence"}'
    )
    votes = _panel(system, f"Review scenery PNG: {slug}.", ib)
    return {"type": "scenery", "slug": slug, "mission_hint": mission_hint,
            "qa": qa, "panel": votes, "verdict": _decide(qa, votes)}


def audit_pose(slug, mp4_path):
    kf = extract_keyframe(mp4_path)
    ib = b64(kf)
    qa_instr = (
        f"{SHORT_BRIEF}\nAsset type: PLAYER POSE video keyframe (usually green "
        "screen chroma key source).\n"
        "Fail ONLY if: multiple figures instead of one, wrong basic action, "
        "unusable green screen (e.g. green spill on skin that's unrecoverable).\n"
        'STRICT JSON: {"verdict":"pass|fail","notes":"..."}'
    )
    qa = _qa(qa_instr, ib)
    system = (
        "You are 1 of 3 Studio Emerald directors doing the FINAL visual audit.\n"
        f"{SHORT_BRIEF}\n"
        f"Asset type: PLAYER POSE video keyframe ({slug}).\n"
        "Judge: (a) single clear figure, (b) green screen quality (if green "
        "bg used), (c) motion/pose reads correctly, (d) no biased emotion\n"
        "(e.g. triumphant pose for 'high-risk' option that would bias measurement).\n"
        'STRICT JSON: {"verdict":"pass|fix|fail","notes":"one sentence"}'
    )
    votes = _panel(system, f"Review pose keyframe: {slug}.", ib)
    return {"type": "pose", "slug": slug,
            "qa": qa, "panel": votes, "verdict": _decide(qa, votes)}


def make_tool_triple_grid(mission_id, tool_paths):
    """3-column side-by-side composite of the 3 tools."""
    out = KF_CACHE / f"triple_{mission_id}.png"
    if out.exists():
        return out
    imgs = [Image.open(p).convert("RGBA") for p in tool_paths]
    tile = 400
    cells = []
    for img in imgs:
        w, h = img.size
        s = tile / max(w, h)
        img2 = img.resize((int(w * s), int(h * s)), Image.LANCZOS)
        cell = Image.new("RGBA", (tile, tile), (255, 255, 255, 255))
        cell.paste(img2, ((tile - img2.size[0]) // 2, (tile - img2.size[1]) // 2), img2)
        cells.append(cell.convert("RGB"))
    grid = Image.new("RGB", (tile * 3, tile), "white")
    for i, c in enumerate(cells):
        grid.paste(c, (i * tile, 0))
    grid.save(out, "PNG")
    return out


def audit_tool_triple(mission_id, tool_info):
    """Audit the 3 tools of a mission as a TRIPLE — check visual equality.
    tool_info: [(label, path, points, consequence_type), ...]
    """
    paths = [t[1] for t in tool_info]
    labels = [t[0] for t in tool_info]
    # Mission scientific reasoning — so directors know the tool design isn't arbitrary.
    m = LOCK["missions"][mission_id]
    tools_meta = m.get("tools", [])
    reasoning_lines = []
    for t in tools_meta:
        reasoning_lines.append(
            f"    • slot {t.get('slot','?')}: {t.get('label','?')} — "
            f"{t.get('points','?')}p, consequence={t.get('consequence_type','?')}"
        )
    reasoning = "\n".join(reasoning_lines)

    grid = make_tool_triple_grid(mission_id, paths)
    ib = b64(grid)
    qa_instr = (
        f"{SHORT_BRIEF}\nAsset type: TOOL TRIPLE for mission {mission_id}.\n"
        f"Mission: {m['mission_text']}\n"
        f"Tools shown left-to-right: {', '.join(labels)}\n"
        "IMPORTANT CONTEXT — these are chroma-key source PNGs. The green (or white)\n"
        "background is just the studio screen the Builder will key out. IGNORE\n"
        "'lighting', 'cinematography', 'hero framing' — there is none; it's a flat\n"
        "studio shot. Judge ONLY:\n"
        " (a) relative SIZE — does one tool fill dramatically more frame than another?\n"
        "     (if yes, fix = 'shrink tool X by ~N%')\n"
        " (b) unintended elements — e.g. human figure integrated into a tool,\n"
        "     multiple instances of the tool, extra props attached.\n"
        " (c) subject correctness — does each tool actually depict what its label says?\n"
        " (d) any large obviously-readable hallucinated logo that occupies >5% of the tool.\n"
        'STRICT JSON: {"verdict":"pass|fail","notes":"concrete fix or \'pass\'"}'
    )
    qa = _qa(qa_instr, ib)
    system = (
        "You are 1 of 3 Studio Emerald directors doing the FINAL visual audit.\n"
        f"{SHORT_BRIEF}\n"
        f"Asset type: TOOL TRIPLE for mission {mission_id}.\n"
        f"Mission: {m['mission_text']}\n"
        f"Checkpoint: {m.get('checkpoint_text','')}\n"
        f"Tools (L→R): {', '.join(labels)}\n"
        f"Tool scoring (hidden from player, decided by game design):\n{reasoning}\n\n"
        "**IMPORTANT — these are chroma-key source PNGs.** The background is flat\n"
        "studio green/white, to be keyed out by the Builder. There is NO cinematic\n"
        "lighting, NO scene atmosphere — do NOT comment on 'dramatic lighting' or\n"
        "'heroic framing'. The only dominance factors that exist in these images are:\n"
        " (1) relative SIZE in frame,\n"
        " (2) unintended elements (integrated human, extra accessories),\n"
        " (3) clearly-readable invented logos occupying >5% of the tool.\n\n"
        "The tool scoring above was decided by game-design. Different designs across\n"
        "the 3 tools are INTENTIONAL — do NOT flag 'one looks more adventure-y'.\n"
        "Flag only if one tool DOMINATES by SIZE or has an UNINTENDED element.\n\n"
        "Your flagged note MUST be an operational fix: 'shrink tool X by ~30%',\n"
        "'remove the integrated human figure from tool Y'. If no such concrete fix\n"
        "exists, return verdict=pass.\n"
        'STRICT JSON: {"verdict":"pass|fix|fail","notes":"concrete fix or \'pass\'"}'
    )
    votes = _panel(system, f"Audit tool triple for {mission_id}.", ib)
    return {"type": "tool_triple", "mission": mission_id,
            "tools": [{"label": t[0], "file": Path(t[1]).name} for t in tool_info],
            "qa": qa, "panel": votes, "verdict": _decide(qa, votes)}


# ── inventory ──
def bg_inventory():
    cov = json.loads((REVIEW_DIR / "backgrounds" / "_bg_coverage_audit.json").read_text("utf-8"))
    slug_to_mission = {}
    for mid, r in cov.items():
        d = r.get("decision", {})
        if d.get("action") == "use_existing":
            slug_to_mission[d["slug"]] = mid
    items = []
    for mp4 in sorted(ASSETS_BG.glob("bg_*.mp4")):
        items.append((mp4.stem, mp4, slug_to_mission.get(mp4.stem, "unmapped")))
    return items


def trans_inventory():
    return [(p.stem, p) for p in sorted(ASSETS_TRANS.glob("T_*.mp4"))]


def scenery_inventory():
    struct = PROJECT / "pipeline" / "debates" / "scenery" / "_props_structured.json"
    slug_to_mission = {}
    if struct.exists():
        for p in json.loads(struct.read_text("utf-8")):
            slug_to_mission[p["slug"]] = p.get("mission", "")
    items = []
    for png in sorted(ASSETS_SCENERY.glob("*.png")):
        items.append((png.stem, png, slug_to_mission.get(png.stem, "")))
    return items


def tool_inventory():
    """Group tool PNGs by mission suffix מ<NN>. Return dict mid -> [(label, path), ...]"""
    groups = defaultdict(list)
    suffix_re = re.compile(r"_מ(\d{2})\.png$")
    for png in ASSETS_TOOLS.glob("*.png"):
        if "styletest" in png.stem:
            continue  # skip variants
        m = suffix_re.search(png.name)
        if not m:
            continue
        mid = f"M{int(m.group(1))}"
        # label = filename stem without _מNN
        label = suffix_re.sub("", png.name)
        groups[mid].append((label, png))
    return groups


def pose_inventory():
    return [(p.stem, p) for p in sorted(ASSETS_PLAYER.glob("*.mp4"))]


# ── main ──
def load_results():
    if OUT_PATH.exists():
        try:
            return json.loads(OUT_PATH.read_text("utf-8"))
        except Exception:
            return {}
    return {}


def save_results(r):
    OUT_PATH.write_text(json.dumps(r, ensure_ascii=False, indent=2), "utf-8")


def main():
    results = load_results()
    results.setdefault("backgrounds", {})
    results.setdefault("transitions", {})
    results.setdefault("scenery", {})
    results.setdefault("tool_triples", {})
    results.setdefault("poses", {})
    save_results(results)

    def done(bucket, key):
        return key in results[bucket] and results[bucket][key].get("verdict")

    # 1. backgrounds
    bgs = bg_inventory()
    print(f"\n=== BACKGROUNDS ({len(bgs)}) ===")
    for slug, mp4, mid in bgs:
        if done("backgrounds", slug):
            print(f"  {slug}: skip (already audited)")
            continue
        print(f"  {slug} ({mid}) ...", flush=True)
        r = audit_bg(slug, mp4, mid) if mid != "unmapped" else \
            audit_bg(slug, mp4, list(LOCK["missions"].keys())[0])  # fallback
        print(f"    -> {r['verdict']}")
        results["backgrounds"][slug] = r
        save_results(results)

    # 2. transitions
    trs = trans_inventory()
    print(f"\n=== TRANSITIONS ({len(trs)}) ===")
    for slug, mp4 in trs:
        if done("transitions", slug):
            print(f"  {slug}: skip")
            continue
        print(f"  {slug} ...", flush=True)
        r = audit_transition(slug, mp4)
        print(f"    -> {r['verdict']}")
        results["transitions"][slug] = r
        save_results(results)

    # 3. scenery
    scs = scenery_inventory()
    print(f"\n=== SCENERY ({len(scs)}) ===")
    for slug, png, mid in scs:
        if done("scenery", slug):
            print(f"  {slug}: skip")
            continue
        print(f"  {slug} ({mid}) ...", flush=True)
        r = audit_scenery(slug, png, mid)
        print(f"    -> {r['verdict']}")
        results["scenery"][slug] = r
        save_results(results)

    # 4. tool triples
    tool_groups = tool_inventory()
    print(f"\n=== TOOL TRIPLES ({len(tool_groups)}) ===")
    for mid in sorted(tool_groups.keys(), key=lambda x: int(x[1:])):
        if done("tool_triples", mid):
            print(f"  {mid}: skip")
            continue
        tools = tool_groups[mid]
        if len(tools) != 3:
            print(f"  {mid}: SKIP — has {len(tools)} tool files instead of 3")
            continue
        print(f"  {mid} triple ...", flush=True)
        r = audit_tool_triple(mid, tools)
        print(f"    -> {r['verdict']}")
        results["tool_triples"][mid] = r
        save_results(results)

    # 5. poses
    ps = pose_inventory()
    print(f"\n=== POSES ({len(ps)}) ===")
    for slug, mp4 in ps:
        if done("poses", slug):
            print(f"  {slug}: skip")
            continue
        print(f"  {slug} ...", flush=True)
        r = audit_pose(slug, mp4)
        print(f"    -> {r['verdict']}")
        results["poses"][slug] = r
        save_results(results)

    # summary
    print("\n" + "=" * 60)
    print("AUDIT COMPLETE")
    print("=" * 60)
    for bucket in ["backgrounds", "transitions", "scenery", "tool_triples", "poses"]:
        rs = results[bucket]
        total = len(rs)
        p = sum(1 for v in rs.values() if v.get("verdict") == "pass")
        fx = sum(1 for v in rs.values() if v.get("verdict") == "fix")
        fl = sum(1 for v in rs.values() if v.get("verdict") == "fail")
        print(f"  {bucket:15} {total:3}  pass={p:3}  fix={fx:2}  fail={fl:2}")


if __name__ == "__main__":
    main()
