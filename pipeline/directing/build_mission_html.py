"""build_mission_html — emit one HTML per mission from the materialized
Builder inputs.

Reads:
  pipeline/scene_scripts/script_<M>.json
  pipeline/scene_briefs/scene_<M>.json
  pipeline/set_list_<M>.json
  pipeline/sound_design_<M>.json
  pipeline/pose_map.json
  content_lock.json (only tool_consequence_types.per_tool)

Writes:
  pipeline/builder_html/<M>.html  (self-contained; assets via ../../assets/...)
  pipeline/builder_html/_index.json

Follows builder.md template + design_system.md helpers:
  - 4 staging zones (A/B/C/D)
  - canvas chroma key for player video (NEVER raw <video>)
  - segment loop (NEVER video.loop=true)
  - gear toss + per-type consequence (hold/use/wear/deploy)
  - RTL Hebrew, no gold/orange palette, ⓘ tooltip on tools
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT = Path(__file__).resolve().parent.parent.parent
OUT_DIR = PROJECT / "pipeline" / "builder_html"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Hebrew "stop tokens" — common modifiers that don't carry semantic identity
HEB_STOP = {"של", "עם", "ה", "ב", "מ", "ו", "את", "על", "אל", "ל",
            "מ01", "מ02", "מ03", "מ04", "מ05", "מ06", "מ07", "מ08",
            "מ09", "מ10", "מ11", "מ12", "מ13", "מ14", "מ15"}


def _norm(s: str) -> str:
    """Strip mission tag and apostrophe variants, return clean tokens str."""
    import re
    s = re.sub(r"_מ\d+$", "", s)
    s = re.sub(r"מ\d+", "", s)
    s = s.replace("'", "").replace("'", "").replace("'", "")
    return s


def _tokens(s: str) -> set[str]:
    s = _norm(s)
    parts = s.replace(" ", "_").split("_")
    return {p for p in parts if p and p not in HEB_STOP and len(p) > 1}


def _common_prefix_len(a: str, b: str) -> int:
    n = 0
    for ca, cb in zip(a, b):
        if ca == cb:
            n += 1
        else:
            break
    return n


def _best_token_pair_score(label_toks: set[str], cand_toks: set[str]) -> int:
    """For each label token, find best pairing with a cand token.
    Returns sum of (exact=10, prefix3+=6, prefix2+=3, substr=2)."""
    total = 0
    for lt in label_toks:
        best = 0
        for ct in cand_toks:
            if lt == ct:
                best = max(best, 10)
            else:
                p = _common_prefix_len(lt, ct)
                if p >= 3:
                    best = max(best, 6)
                elif p >= 2:
                    best = max(best, 3)
                if (lt in ct or ct in lt) and p > 0:
                    best = max(best, 2)
        total += best
    return total


def _score_tool(label: str, directed_stem: str, candidate: Path) -> int:
    """Higher = better match between (label or directed name) and candidate."""
    cand_toks = _tokens(candidate.stem)
    score = 0
    # Strong: directed stem matches candidate stem exactly (after normalize)
    if _norm(candidate.stem) == _norm(directed_stem):
        return 1000
    # Token overlap (strong+prefix) with label — primary signal
    label_toks = _tokens(label)
    score += _best_token_pair_score(label_toks, cand_toks) * 3
    # Token overlap with directed name (secondary)
    directed_toks = _tokens(directed_stem)
    score += _best_token_pair_score(directed_toks, cand_toks)
    return score


def _assign_tools_optimally(script_tools: list[dict],
                             candidates: list[Path]) -> dict:
    """Find the slot→file assignment that maximizes total score.
    Returns {slot: Path} dict. Brute-force is fine — ≤4 candidates × 3 slots."""
    import itertools
    if not candidates:
        return {}
    n = len(candidates)
    slots = [t.get("slot") for t in script_tools]
    labels = [t.get("label", "") for t in script_tools]
    directed = [Path(t.get("file") or "").stem for t in script_tools]
    # for each permutation of candidates, sum scores
    best_total = -1
    best_assign = {}
    for perm in itertools.permutations(range(n), len(script_tools)):
        total = 0
        for i, idx in enumerate(perm):
            total += _score_tool(labels[i], directed[i], candidates[idx])
        if total > best_total:
            best_total = total
            best_assign = {slots[i]: candidates[perm[i]]
                          for i in range(len(script_tools))}
    return best_assign


def _list_mission_tools(mission: str) -> list[Path]:
    """All real tool PNGs for this mission, excluding styletest dupes."""
    tools_dir = PROJECT / "assets" / "tools"
    if not tools_dir.exists():
        return []
    tag = "מ" + mission[1:].zfill(2)
    return [
        f for f in tools_dir.iterdir()
        if f.is_file() and f.suffix == ".png"
        and "styletest" not in f.name and not f.name.startswith("_")
        and tag in f.name
    ]


def resolve_tool_file(label: str, directed_file: str, mission: str) -> str:
    """Map a script tool (label + directing-time path) to the actual file
    on disk. Returns the ../../assets/tools/<name>.png form."""
    if not directed_file:
        return ""
    candidates = _list_mission_tools(mission)
    directed_stem = Path(directed_file).stem
    if not candidates:
        return f"../../assets/tools/{Path(directed_file).name}"
    best = max(candidates, key=lambda c: _score_tool(label, directed_stem, c))
    return f"../../assets/tools/{best.name}"


def resolve_asset(rel: str) -> str:
    """Resolve a (possibly bare) asset filename to a path that works from
    pipeline/builder_html/<M>.html (i.e. starts with ../../assets/).
    Best-effort — falls back to literal if nothing better is found."""
    if not rel:
        return ""
    if rel.startswith("assets/"):
        # try literal first, then fall back to bare-name search
        if (PROJECT / rel).exists():
            return f"../../{rel}"
        # search by basename
        name = Path(rel).name
        for sub in ("backgrounds", "scenery", "tools", "player",
                    "rivals", "effects", "transitions"):
            if (PROJECT / "assets" / sub / name).exists():
                return f"../../assets/{sub}/{name}"
        return f"../../{rel}"  # broken — caller will see it
    name = Path(rel).name
    for sub in ("backgrounds", "scenery", "tools", "player",
                "rivals", "effects", "transitions"):
        if (PROJECT / "assets" / sub / name).exists():
            return f"../../assets/{sub}/{name}"
    return f"../../assets/{rel}"


def consequence_for(label: str, per_tool: dict) -> str:
    return per_tool.get(label, "hold")


def build_one(mission: str, per_tool: dict, pose_map: dict) -> dict:
    sb = json.loads((PROJECT / "pipeline" / "scene_briefs"
                     / f"scene_{mission}.json").read_text("utf-8"))
    sc = json.loads((PROJECT / "pipeline" / "scene_scripts"
                     / f"script_{mission}.json").read_text("utf-8"))
    sl = json.loads((PROJECT / "pipeline"
                     / f"set_list_{mission}.json").read_text("utf-8"))

    mission_text = sc.get("mission_text", "")
    checkpoint_text = sc.get("checkpoint_text", "")

    # Background
    bg_layer = sb.get("background") or {}
    bg_file = bg_layer.get("file") or ""
    bg_src = resolve_asset(bg_file)

    # Player pose
    player = sb.get("player", {})
    pose_file = player.get("pose_file") or ""
    pose_src = resolve_asset(pose_file)
    pose_meta = pose_map.get("poses", {}).get(pose_file, {})
    seg = pose_meta.get("loop_segment") or {"start": 0, "end": 8}
    is_one_shot = bool(pose_meta.get("one_shot"))
    hold_frame = pose_meta.get("hold_frame")

    # Scenery layers — skip ones whose file is missing on disk so HTML
    # stays valid; missing loop assets are tracked separately in the
    # BLOCKED todo (rain/jeep/etc. need Veo generation).
    scenery = []
    skipped_scenery = []
    for L in sl.get("layers", []):
        if L.get("role") == "scenery":
            f = L.get("file")
            if not f:
                continue
            # check resolution
            name = Path(f).name
            found = False
            for sub in ("scenery", "effects", "transitions", "rivals"):
                if (PROJECT / "assets" / sub / name).exists():
                    found = True
                    break
            if not found and not (PROJECT / f).exists():
                skipped_scenery.append(f)
                continue
            scenery.append({
                "src": resolve_asset(f),
                "x": L.get("pos", {}).get("x_pct", 50),
                "y": L.get("pos", {}).get("y_pct", 50),
                "scale": L.get("scale", 0.4),
                "rot": L.get("rot_deg", 0),
                "z": L.get("z", 10),
                "anchor": L.get("anchor", "center"),
            })

    # Tools — optimal slot↔file assignment via score maximization.
    # Avoids greedy cascades that swap tools when labels & filenames diverge.
    tools = []
    script_tools = sc.get("tools", [])
    candidates = _list_mission_tools(mission)
    assignment = _assign_tools_optimally(script_tools, candidates)
    for t in script_tools:
        slot = t.get("slot")
        label = t.get("label", "")
        f = t.get("file") or ""
        chosen = assignment.get(slot)
        if chosen:
            src = f"../../assets/tools/{chosen.name}"
        else:
            src = resolve_tool_file(label, f, mission)
        tools.append({
            "slot": slot,
            "label": label,
            "src": src,
            "points": t.get("points", 0),
            "consequence": consequence_for(label, per_tool),
        })

    duration_ms = sb.get("duration_ms") or 12000

    # ── Build HTML ──
    # Note: design_system rules — RTL, Heebo font, no gold, ⓘ tooltip,
    # canvas chroma for player, segment loop, no video.loop=true.
    scenery_html_parts = []
    for s in scenery:
        anchor_offset = ""
        if s["anchor"] == "bottom-left":
            anchor_offset = "transform-origin:bottom left;"
        elif s["anchor"] == "bottom-right":
            anchor_offset = "transform-origin:bottom right;"
        elif s["anchor"] == "bottom-center":
            anchor_offset = "transform-origin:bottom center;"
        scenery_html_parts.append(
            f'    <img class="scenery" src="{s["src"]}" '
            f'style="position:absolute;left:{s["x"]}%;top:{s["y"]}%;'
            f'width:{int(s["scale"]*100)}%;'
            f'transform:translate(-50%,-50%) rotate({s["rot"]}deg);'
            f'{anchor_offset}'
            f'z-index:{s["z"]};pointer-events:none;object-fit:contain">'
        )
    scenery_html = "\n".join(scenery_html_parts)

    # Tool data as JS array
    tools_js = json.dumps([
        {"slot": t["slot"], "label": t["label"], "file": t["src"],
         "points": t["points"], "consequence": t["consequence"]}
        for t in tools
    ], ensure_ascii=False, indent=2)

    pose_js = json.dumps({
        "file": pose_src,
        "loopStart": float(seg.get("start", 0)),
        "loopEnd": float(seg.get("end", 8)),
        "holdFrame": hold_frame,
        "isOneShot": is_one_shot,
    }, indent=2)

    scene_js = json.dumps({
        "missionId": mission,
        "missionText": mission_text,
        "checkpointText": checkpoint_text,
        "durationMs": duration_ms,
    }, ensure_ascii=False, indent=2)

    html = f"""<!DOCTYPE html>
<html dir="rtl" lang="he">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0,maximum-scale=1.0">
<title>{mission} — משלחת אל עיר האזמרגד</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Heebo:wght@400;600;700&display=swap" rel="stylesheet">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:100vw;height:100vh;overflow:hidden;background:#000;font-family:'Heebo','Assistant',sans-serif;color:#fff}}

/* Zone A — Progress Bar (6vh, min 28px) */
#zone-a{{position:fixed;top:0;left:0;width:100%;height:6vh;min-height:28px;z-index:100;
  display:flex;align-items:center;justify-content:space-between;
  padding:0 4%;background:linear-gradient(180deg,rgba(0,0,0,0.65),rgba(0,0,0,0));
  pointer-events:none}}
#zone-a .score{{font-size:clamp(0.85rem,2.2vw,1rem);font-weight:700;
  text-shadow:0 1px 3px rgba(0,0,0,0.9)}}
#zone-a .progress-bar{{flex:1;max-width:50%;height:6px;margin:0 16px;
  background:rgba(255,255,255,0.15);border-radius:3px;overflow:hidden}}
#zone-a .progress-fill{{height:100%;background:#4A90E2;width:0;transition:width 400ms}}

/* Zone B — Scene (54vh, top 6vh) */
#zone-b{{position:fixed;top:6vh;left:0;width:100%;height:54vh;z-index:1;overflow:hidden;background:#000}}
#bg-video{{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;z-index:0}}
.scenery{{position:absolute;z-index:5}}
#player-source{{display:none}}
#player-canvas{{position:absolute;left:50%;top:70%;transform:translate(-50%,-50%);
  height:90%;width:auto;z-index:10;pointer-events:none}}

/* Zone C — Mission Text (16vh, top 60vh) */
#zone-c{{position:fixed;top:60vh;left:0;width:100%;height:16vh;z-index:30;
  display:flex;align-items:center;justify-content:center;padding:0 5%}}
#mission-text{{direction:rtl;text-align:center;font-size:clamp(0.9rem,2.5vw,1.1rem);
  font-weight:600;line-height:1.5;
  text-shadow:0 1px 3px rgba(0,0,0,0.9),0 2px 8px rgba(0,0,0,0.7);
  opacity:0;transition:opacity 400ms}}
#mission-text.visible{{opacity:1}}

/* Zone D — Tools (24vh, bottom 0) */
#zone-d{{position:fixed;bottom:0;left:0;width:100%;height:24vh;min-height:120px;z-index:20;
  display:flex;align-items:center;justify-content:space-evenly;padding:0 5%;
  background:rgba(0,0,0,0.65);border-top:1px solid rgba(255,255,255,0.15)}}
.tool-wrapper{{position:relative;cursor:pointer;display:flex;align-items:center;justify-content:center;
  min-width:44px;min-height:44px;transition:opacity 200ms}}
.tool-wrapper.dimmed{{opacity:0.3;pointer-events:none}}
.tool-wrapper img{{max-width:100%;max-height:100%;object-fit:contain;display:block}}
.tool-info-icon{{position:absolute;top:6px;right:6px;width:22px;height:22px;border-radius:50%;
  background:rgba(0,0,0,0.6);color:#fff;font-size:0.75rem;font-weight:700;
  display:flex;align-items:center;justify-content:center;
  border:1px solid rgba(255,255,255,0.4);z-index:21;cursor:pointer;user-select:none}}
.tool-tooltip{{position:absolute;bottom:calc(100% + 8px);right:0;
  background:rgba(0,0,0,0.85);color:#fff;padding:6px 10px;border-radius:6px;
  font-size:0.8rem;white-space:nowrap;direction:rtl;
  opacity:0;transition:opacity 150ms;pointer-events:none;z-index:50}}
.tool-tooltip.visible,.tool-info-icon:hover + .tool-tooltip,
.tool-info-icon:focus + .tool-tooltip{{opacity:1}}
.points-popup{{position:fixed;font-size:1.5rem;font-weight:700;
  text-shadow:0 1px 4px rgba(0,0,0,0.9);pointer-events:none;z-index:200;
  transition:transform 800ms cubic-bezier(0.25,0.46,0.45,0.94),opacity 800ms ease}}

/* Checkpoint text (overlay near scene bottom, fades in late) */
#checkpoint-text{{position:fixed;left:50%;bottom:25vh;transform:translateX(-50%);
  width:70%;text-align:center;direction:rtl;
  font-size:clamp(0.85rem,2.2vw,1rem);font-weight:600;line-height:1.4;color:#fff;
  background:rgba(0,0,0,0.7);padding:10px 18px;border-radius:8px;
  text-shadow:0 1px 3px rgba(0,0,0,0.9);z-index:35;
  opacity:0;transition:opacity 400ms;pointer-events:none}}
#checkpoint-text.visible{{opacity:1}}

/* Transition overlay (crossfade out) */
#transition-overlay{{position:fixed;inset:0;background:#000;opacity:0;
  pointer-events:none;z-index:300;transition:opacity 800ms}}
#transition-overlay.active{{opacity:1}}
</style>
</head>
<body>
  <!-- ZONE A -->
  <div id="zone-a">
    <span class="score" id="score">ניקוד: 0</span>
    <div class="progress-bar"><div class="progress-fill" id="progress-fill"></div></div>
    <span class="score" id="mission-counter">{mission}</span>
  </div>

  <!-- ZONE B -->
  <div id="zone-b">
    <video id="bg-video" autoplay muted playsinline preload="auto" src="{bg_src}"></video>
{scenery_html}
    <video id="player-source" muted playsinline preload="auto"></video>
    <canvas id="player-canvas"></canvas>
    <div id="checkpoint-text"></div>
  </div>

  <!-- ZONE C -->
  <div id="zone-c">
    <p id="mission-text"></p>
  </div>

  <!-- ZONE D -->
  <div id="zone-d"></div>

  <div id="transition-overlay"></div>

<script>
"use strict";

const SCENE = {scene_js};
const POSE  = {pose_js};
const TOOLS = {tools_js};

// ── helpers ──
const $ = (sel) => document.querySelector(sel);
const delay = (ms) => new Promise((r) => setTimeout(r, ms));

// ── Background segment loop (NO video.loop=true) ──
function startBgLoop() {{
  const v = $("#bg-video");
  v.addEventListener("loadedmetadata", () => {{
    const end = v.duration;
    v.currentTime = 0;
    v.play().catch(() => {{}});
    v.addEventListener("timeupdate", () => {{
      if (v.currentTime >= end - 0.05) v.currentTime = 0;
    }});
  }});
}}

// ── Player chroma key on canvas ──
function setupPlayer() {{
  const v = $("#player-source");
  const c = $("#player-canvas");
  const ctx = c.getContext("2d", {{ willReadFrequently: true }});
  v.src = POSE.file;

  v.addEventListener("loadedmetadata", () => {{
    c.width = v.videoWidth;
    c.height = v.videoHeight;
    if (POSE.isOneShot) {{
      v.currentTime = 0;
    }} else {{
      v.currentTime = POSE.loopStart;
    }}
    v.play().catch(() => {{}});
  }});

  v.addEventListener("timeupdate", () => {{
    if (!POSE.isOneShot && v.currentTime >= POSE.loopEnd - 0.03) {{
      v.currentTime = POSE.loopStart;
    }}
  }});

  function processFrame() {{
    if (v.paused || v.ended) {{
      requestAnimationFrame(processFrame);
      return;
    }}
    if (v.videoWidth === 0) {{
      requestAnimationFrame(processFrame);
      return;
    }}
    ctx.drawImage(v, 0, 0, c.width, c.height);
    const frame = ctx.getImageData(0, 0, c.width, c.height);
    const d = frame.data;
    for (let i = 0; i < d.length; i += 4) {{
      const r = d[i], g = d[i+1], b = d[i+2];
      // chroma threshold: green dominant + bright
      if (g > 100 && g > r * 1.4 && g > b * 1.4) d[i+3] = 0;
    }}
    ctx.putImageData(frame, 0, 0);
    requestAnimationFrame(processFrame);
  }}
  requestAnimationFrame(processFrame);
}}

// ── Tools ──
let SCORE = 0;
function updateScore(pts) {{
  SCORE += pts;
  $("#score").textContent = `ניקוד: ${{SCORE}}`;
}}

function buildTools() {{
  const container = $("#zone-d");
  // Each tool fits within Zone D (24vh ~ 192px on a 800px screen).
  // Cap to keep readable across resolutions.
  TOOLS.forEach((tool, idx) => {{
    const wrapper = document.createElement("div");
    wrapper.className = "tool-wrapper";
    wrapper.style.width = "min(22vw, 18vh, 140px)";
    wrapper.style.height = "min(22vw, 18vh, 140px)";
    wrapper.dataset.slot = tool.slot;

    const img = document.createElement("img");
    img.src = tool.file;
    img.alt = tool.label;

    const icon = document.createElement("div");
    icon.className = "tool-info-icon";
    icon.textContent = "i";
    icon.tabIndex = 0;
    icon.setAttribute("aria-label", "מידע על הכלי");

    const tooltip = document.createElement("div");
    tooltip.className = "tool-tooltip";
    tooltip.textContent = `${{tool.label}}  ·  +${{tool.points}}`;

    // mobile tap reveals for 2s; desktop hover handled in CSS
    icon.addEventListener("click", (e) => {{
      e.stopPropagation();
      tooltip.classList.add("visible");
      setTimeout(() => tooltip.classList.remove("visible"), 2000);
    }});

    img.addEventListener("click", () => handleToolSelection(tool, wrapper, img));

    wrapper.append(img, icon, tooltip);
    container.appendChild(wrapper);
  }});
}}

// ── Gear toss + per-type consequence ──
function gearToss(toolEl, playerCanvas) {{
  return new Promise((resolve) => {{
    const pr = playerCanvas.getBoundingClientRect();
    const tr = toolEl.getBoundingClientRect();
    const toX = (pr.left + pr.width * 0.55) - tr.left;
    const toY = (pr.top + pr.height * 0.35) - tr.top;
    const arcY = Math.min(tr.top, pr.top) - 80 - tr.top;
    toolEl.animate([
      {{ transform: "translate(0,0) scale(1)", offset: 0 }},
      {{ transform: `translate(${{toX/2}}px,${{arcY}}px) scale(1.1)`, offset: 0.45 }},
      {{ transform: `translate(${{toX}}px,${{toY}}px) scale(0.85)`, offset: 1 }}
    ], {{ duration: 380, easing: "cubic-bezier(0.25,0.46,0.45,0.94)", fill: "forwards" }})
      .finished.then(() => resolve());
  }});
}}

function applyHold(toolEl, ms = 1800) {{ return delay(ms); }}

function applyUse(toolEl) {{
  return toolEl.animate([
    {{ transform: "rotate(0deg) scale(0.85)", offset: 0 }},
    {{ transform: "rotate(-35deg) scale(1.0)", offset: 0.3 }},
    {{ transform: "rotate(25deg) scale(0.9)", offset: 0.7 }},
    {{ transform: "rotate(0deg) scale(0.85)", offset: 1 }}
  ], {{ duration: 600, easing: "ease-in-out", fill: "forwards" }}).finished;
}}

function applyWear(toolEl, playerCanvas) {{
  const pr = playerCanvas.getBoundingClientRect();
  const tr = toolEl.getBoundingClientRect();
  const bodyX = (pr.left + pr.width * 0.40) - tr.left;
  const bodyY = (pr.top + pr.height * 0.50) - tr.top;
  return toolEl.animate([
    {{ transform: toolEl.style.transform || "translate(0,0) scale(0.85)", offset: 0 }},
    {{ transform: `translate(${{bodyX}}px,${{bodyY}}px) scale(1.15)`, offset: 1 }}
  ], {{ duration: 400, easing: "ease-out", fill: "forwards" }}).finished;
}}

function applyDeploy(toolEl, playerCanvas) {{
  const pr = playerCanvas.getBoundingClientRect();
  const tr = toolEl.getBoundingClientRect();
  const dX = (pr.left + pr.width * 0.5) - tr.left;
  const dY = (pr.top - pr.height * 0.25) - tr.top;
  toolEl.style.zIndex = "9";
  return toolEl.animate([
    {{ transform: (toolEl.style.transform || "") + " scale(0.85)", offset: 0 }},
    {{ transform: `translate(${{dX}}px,${{dY}}px) scale(2.2)`, offset: 0.6 }},
    {{ transform: `translate(${{dX}}px,${{dY - 20}}px) scale(2.0)`, offset: 1 }}
  ], {{ duration: 700, easing: "cubic-bezier(0.34,1.56,0.64,1)", fill: "forwards" }}).finished;
}}

async function handleToolSelection(tool, wrapper, img) {{
  // dim other tools
  document.querySelectorAll("#zone-d .tool-wrapper").forEach((w) => {{
    if (w !== wrapper) w.classList.add("dimmed");
  }});

  updateScore(tool.points);
  spawnPointsPopup(tool, wrapper);

  const canvas = $("#player-canvas");
  await gearToss(wrapper, canvas);

  switch (tool.consequence) {{
    case "hold":   await applyHold(wrapper); break;
    case "use":    await applyUse(wrapper); await applyHold(wrapper, 1200); break;
    case "wear":   await applyWear(wrapper, canvas); await applyHold(wrapper, 1500); break;
    case "deploy": await applyDeploy(wrapper, canvas); await applyHold(wrapper, 1500); break;
    default:       await applyHold(wrapper);
  }}

  showCheckpoint();
  await delay(2200);
  transitionOut();
}}

function spawnPointsPopup(tool, wrapper) {{
  const r = wrapper.getBoundingClientRect();
  const target = $("#score").getBoundingClientRect();
  const popup = document.createElement("div");
  popup.className = "points-popup";
  popup.textContent = `+${{tool.points}}`;
  popup.style.color = tool.points >= 3 ? "#E94B3C"
                      : tool.points === 2 ? "#7FB069" : "#4A90E2";
  popup.style.left = `${{r.left + r.width / 2}}px`;
  popup.style.top  = `${{r.top}}px`;
  document.body.appendChild(popup);
  requestAnimationFrame(() => {{
    popup.style.transform = `translate(${{target.left - r.left}}px,${{target.top - r.top}}px) scale(0.7)`;
    popup.style.opacity = "0";
  }});
  setTimeout(() => popup.remove(), 900);
}}

function showMissionText() {{
  $("#mission-text").textContent = SCENE.missionText;
  requestAnimationFrame(() => $("#mission-text").classList.add("visible"));
}}

function showCheckpoint() {{
  if (!SCENE.checkpointText) return;
  const el = $("#checkpoint-text");
  el.textContent = SCENE.checkpointText;
  el.classList.add("visible");
}}

function transitionOut() {{
  const o = $("#transition-overlay");
  o.classList.add("active");
}}

document.addEventListener("DOMContentLoaded", () => {{
  startBgLoop();
  setupPlayer();
  buildTools();
  setTimeout(showMissionText, 700);
  // progress placeholder — Builder will receive real flow from main game
  $("#progress-fill").style.width = "20%";
}});
</script>
</body>
</html>
"""

    out_path = OUT_DIR / f"{mission}.html"
    out_path.write_text(html, encoding="utf-8")
    return {
        "mission": mission,
        "out": str(out_path.relative_to(PROJECT)).replace("\\", "/"),
        "bg": bg_src,
        "pose": pose_src,
        "tools": [t["slot"] + ":" + t["label"] for t in tools],
        "scenery_count": len(scenery),
        "skipped_scenery_loops": skipped_scenery,
        "duration_ms": duration_ms,
    }


def main(argv: list[str]) -> int:
    arg = argv[1] if len(argv) > 1 else "all"
    if arg == "all":
        missions = [f"M{i}" for i in range(1, 16)]
    else:
        missions = [m.strip() for m in arg.split(",") if m.strip()]

    cl = json.loads((PROJECT / "content_lock.json").read_text("utf-8"))
    per_tool = (cl.get("tool_consequence_types") or {}).get("per_tool") or {}
    pose_map = json.loads((PROJECT / "pipeline" / "pose_map.json")
                          .read_text("utf-8"))

    print(f"building HTML for {len(missions)} mission(s)...")
    results = []
    failures = 0
    for m in missions:
        try:
            r = build_one(m, per_tool, pose_map)
            print(f"  {m}: OK  bg={Path(r['bg']).name}  pose={Path(r['pose']).name}  scenery={r['scenery_count']}")
        except Exception as e:
            failures += 1
            r = {"mission": m, "status": "ERROR", "error": f"{type(e).__name__}: {e}"}
            print(f"  {m}: FAIL {e}")
            import traceback
            traceback.print_exc()
        results.append(r)

    summary = {
        "_built_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "results": results,
        "summary": {"ok": len([r for r in results if "out" in r]),
                    "fail": failures},
    }
    (OUT_DIR / "_index.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nindex: pipeline/builder_html/_index.json")
    print(f"built: {summary['summary']['ok']}/{len(missions)}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
