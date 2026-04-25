"""build_m1_poc — POC for M1 only, v4 (Nirit's cumulative critiques fully addressed).

Reads ground truth from:
  pipeline/scene_briefs/scene_M1.json   (v4 — sky bg, run-catch-jump-land sequence)
  pipeline/pose_composition_map.json    (v4 — pose_04 -> pose_06 -> pose_03)
  pipeline/tool_consequence_map.json    (v4 — post_pose=pose_03 landing)
  content_lock.json                     (mission_text, checkpoint_text, tool labels)

v4 fixes vs v3 build (every Nirit critique answered):
  1. NO plane interior — phase_1 bg is CSS sky gradient + drifting cloud streaks (not bg_M1.mp4).
  2. NO idle floaty pose — entry is pose_04 RUNNING (profile, looped 2.0-4.0).
  3. NO infinite idle loop — running loop is purposeful motion, breaks on click.
  4. NO square frame around player — wrapper div + transparent inner canvas + first-frame-gate (canvas hidden until first chroma-keyed frame is drawn, opacity:0->1).
  5. NO premature hand-raise — pose_06 starts ONLY on click. Before click: only pose_04. Latest critical fix per Nirit:
     'היא מרימה יד לקבל את הכלי רק ברגע שהשחקן בוחר כלי ולא שנייה אחת לפני'.
  6. NO parachute/falling pose — pose_07 dropped entirely.
  7. Real GRAB animation — tool flies on cubic-bezier curved arc from its zone-D button to player palm,
     1500ms duration, arrives at palm at the EXACT pose_06 frame 4.5 (= peak palm-forward) for visual sync.
  8. Real LANDING pose — pose_03 #3.0-5.0 plays after CSS jump, ending with hands on jungle floor.
  9. Checkpoint text appears ONLY AFTER landing visual completes (= pose_03 frame 5.0 + 200ms).

v4 timeline (post-click):
  click+0      → pose_06 starts at frame 3.0 (hand at rest)
                  + tool launches from clicked button on cubic-bezier arc
  click+1500   → pose_06 at frame 4.5 (peak raise) + tool reaches palm (palm contact)
  click+1700   → pose_06 advances to frame 5.5 (peak grip hold)
  click+2500   → CATCH_COMPLETE. Player canvas CSS-jumps (-12vh + scale + rotate, 600ms).
                  Bg cross-fade sky→bg_M5 starts (500ms).
  click+2800   → JUMP_APEX. pose switches to pose_03 frame 3.0 (upright).
                  Player canvas CSS-translates down to bottom:5% (1700ms).
  click+4800   → LANDING_COMPLETE. pose_03 frame 5.0 (hands-on-ground).
  click+5000   → Checkpoint text fades in (400ms).
  click+6900   → Fade-to-black starts (600ms).
  click+7500   → Scene end.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# UTF-8 stdout (Hebrew labels in print)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT = Path(__file__).resolve().parent.parent.parent
OUT_DIR = PROJECT / "pipeline" / "builder_html"
OUT_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(PROJECT / "pipeline" / "directing"))
from build_mission_html import (  # noqa: E402
    _list_mission_tools, _assign_tools_optimally
)


def main():
    mission = "M1"
    cl = json.loads((PROJECT / "content_lock.json").read_text("utf-8"))
    pc = json.loads((PROJECT / "pipeline" / "pose_composition_map.json").read_text("utf-8"))
    tc = json.loads((PROJECT / "pipeline" / "tool_consequence_map.json").read_text("utf-8"))
    sb = json.loads((PROJECT / "pipeline" / "scene_briefs" / f"scene_{mission}.json").read_text("utf-8"))
    mission_data = cl["missions"][mission]

    # Composition tracks (v4)
    tracks = pc["missions"][mission]["tracks"]
    consequences = tc["missions"][mission]

    # Resolve pose video paths
    for tr in tracks:
        tr["src"] = f"../../assets/player/{tr['pose_file']}"

    # Resolve tools
    script_tools = []
    for t in mission_data.get("tools", []):
        script_tools.append({
            "slot": t.get("slot"),
            "label": t.get("label"),
            "file": t.get("file"),
        })
    candidates = _list_mission_tools(mission)
    assignment = _assign_tools_optimally(script_tools, candidates)
    tools = []
    for t in script_tools:
        slot = t["slot"]
        chosen = assignment.get(slot)
        src = f"../../assets/tools/{chosen.name}" if chosen else ""
        cons = consequences.get(f"slot_{slot}", {})
        tools.append({
            "slot": slot,
            "label": t["label"],
            "src": src,
            "type": cons.get("type", "hold"),
            "entry_ms": cons.get("entry", {}).get("duration_ms", 1500),
            # Catch attach: tool snaps to palm
            "catch_x": cons.get("attach_at_catch", {}).get("point_on_player_pct", {}).get("x", 52),
            "catch_y": cons.get("attach_at_catch", {}).get("point_on_player_pct", {}).get("y", 38),
            "catch_scale": cons.get("attach_at_catch", {}).get("scale_factor", 0.55),
            # Landing attach: tool settles on body
            "land_x": cons.get("attach_at_landing", {}).get("point_on_player_pct", {}).get("x", 50),
            "land_y": cons.get("attach_at_landing", {}).get("point_on_player_pct", {}).get("y", 60),
            "land_scale": cons.get("attach_at_landing", {}).get("scale_factor", 1.4),
            "land_behind": cons.get("attach_at_landing", {}).get("behind_player", False),
        })

    # Phase 2 bg (jungle) — phase 1 is CSS gradient (no video)
    bg2_src = f"../../assets/backgrounds/{sb['background']['phase_2']['file'].split('/')[-1]}"
    bg_swap_ms = sb["background"].get("bg_swap_duration_ms", 500)

    # Rivals dots
    rivals = sb.get("rivals", [{}])[0].get("specs", [])

    # Texts
    mission_text = mission_data.get("mission_text", "")
    checkpoint_text = mission_data.get("checkpoint_text", "")

    scene_js = json.dumps({
        "missionId": mission,
        "missionText": mission_text,
        "checkpointText": checkpoint_text,
        "bgSwapMs": bg_swap_ms,
        "missionTextAppearMs": sb["timing"].get("mission_text_appears_ms", 1500),
        "toolsFirstAppearMs": sb["timing"].get("tools_first_appear_ms", 2000),
        "toolStaggerMs": sb["timing"].get("tool_stagger_ms", 120),
        "catchOneShotMs": sb["timing"].get("catch_one_shot_duration_ms", 2500),
        "toolFlightMs": sb["timing"].get("tool_flight_duration_ms", 1500),
        "postCatchHoldMs": sb["timing"].get("post_catch_hold_ms", 200),
        "jumpDurationMs": sb["timing"].get("jump_duration_ms", 600),
        "landingDurationMs": sb["timing"].get("landing_duration_ms", 2000),
        "checkpointOffsetAfterLandingMs": sb["timing"].get("checkpoint_offset_after_landing_complete_ms", 200),
        "checkpointHoldMs": sb["timing"].get("checkpoint_text_hold_ms", 1500),
        "fadeToBlackMs": sb["timing"].get("fade_to_black_ms", 600),
    }, ensure_ascii=False, indent=2)
    tracks_js = json.dumps(tracks, ensure_ascii=False, indent=2)
    tools_js = json.dumps(tools, ensure_ascii=False, indent=2)
    rivals_js = json.dumps(rivals, ensure_ascii=False, indent=2)

    html = f"""<!DOCTYPE html>
<html dir="rtl" lang="he">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0,maximum-scale=1.0">
<title>{mission}</title>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Heebo:wght@400;600;700&display=swap" rel="stylesheet">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:100vw;height:100vh;overflow:hidden;background:#000;color:#fff;
  font-family:'Heebo','Assistant',sans-serif}}

#zone-a{{position:fixed;top:0;left:0;width:100%;height:6vh;min-height:28px;z-index:100;
  pointer-events:none}}
#progress-bar{{height:6px;background:rgba(255,255,255,0.12);
  margin:calc(3vh - 3px) 5%;border-radius:3px;overflow:hidden}}
#progress-fill{{height:100%;background:#4A90E2;width:6%;transition:width 600ms}}

#zone-b{{position:fixed;top:6vh;left:0;width:100%;height:54vh;z-index:1;
  overflow:hidden;background:#000}}

/* === PHASE 1: CSS sky + clouds === */
#bg-phase1{{position:absolute;inset:0;width:100%;height:100%;z-index:0;
  background:linear-gradient(180deg,#6FBEEB 0%,#A8D7F0 45%,#DCEFFA 75%,#B5D4A8 95%,#82A06B 100%);
  transition:opacity 500ms ease-in-out}}
#bg-phase1.hidden{{opacity:0}}
.cloud-streak{{position:absolute;left:-40%;width:180%;pointer-events:none;
  background:linear-gradient(90deg,transparent 0%,rgba(255,255,255,0.55) 35%,rgba(255,255,255,0.35) 55%,transparent 90%);
  filter:blur(2px)}}
.cloud-streak.a{{top:18%;height:13%;animation:cloudDriftA 22s linear infinite}}
.cloud-streak.b{{top:33%;height:10%;animation:cloudDriftB 28s linear infinite;
  background:linear-gradient(90deg,transparent 0%,rgba(255,255,255,0.42) 30%,rgba(255,255,255,0.55) 60%,transparent 95%)}}
.cloud-streak.c{{top:48%;height:11%;animation:cloudDriftA 32s linear infinite;
  background:linear-gradient(90deg,transparent 0%,rgba(255,255,255,0.32) 40%,rgba(255,255,255,0.5) 65%,transparent 95%)}}
@keyframes cloudDriftA{{
  0%{{transform:translateX(0)}}
  100%{{transform:translateX(28%)}}
}}
@keyframes cloudDriftB{{
  0%{{transform:translateX(0)}}
  100%{{transform:translateX(-22%)}}
}}

/* === PHASE 2: jungle video bg === */
#bg-phase2{{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;z-index:0;
  opacity:0;transition:opacity 500ms ease-in-out}}
#bg-phase2.shown{{opacity:1}}

/* === Rivals (CSS dots) === */
.rival-dot{{position:absolute;border-radius:50%;
  background:radial-gradient(circle at 50% 40%,rgba(40,50,65,0.85) 0%,rgba(20,28,40,0.55) 60%,rgba(10,15,22,0) 100%);
  pointer-events:none;z-index:6;transition:opacity 800ms}}
.rival-dot.dim{{opacity:0.15}}

/* === PLAYER FRAME (the square-frame fix) === */
/* Wrapper div sets the frame; inner canvas fills it transparently */
#player-frame{{position:absolute;z-index:10;pointer-events:none;
  background:transparent;
  /* Default = running entry */
  right:30%;bottom:8%;height:60%;width:auto;aspect-ratio:9/16;
  transition:right 800ms cubic-bezier(0.25,0.46,0.45,0.94),
             bottom 1700ms cubic-bezier(0.34,1.16,0.64,1),
             height 1700ms cubic-bezier(0.34,1.16,0.64,1),
             transform 600ms cubic-bezier(0.16,1,0.3,1)}}
#player-frame.jumping{{transform:translateY(-12vh) scale(1.04) rotate(-2deg)}}
#player-frame.landing{{bottom:5%;height:55%}}
#player-canvas{{position:absolute;inset:0;width:100%;height:100%;
  background:transparent;display:block;
  opacity:0;transition:opacity 200ms}}
#player-canvas.ready{{opacity:1}}

/* Hidden source videos for player chroma-key pipeline */
.player-source{{display:none}}

/* === Tool overlay (the catch animation) === */
.tool-overlay{{position:fixed;z-index:11;pointer-events:none;
  will-change:transform,left,top,width,height,opacity}}
.tool-overlay.behind{{z-index:9}}

#zone-c{{position:fixed;top:60vh;left:0;width:100%;height:16vh;z-index:30;
  display:flex;align-items:center;justify-content:center;padding:0 5%}}
#mission-text{{direction:rtl;text-align:center;font-size:clamp(0.95rem,2.6vw,1.15rem);
  font-weight:600;line-height:1.5;color:#fff;
  text-shadow:0 1px 3px rgba(0,0,0,0.95),0 2px 8px rgba(0,0,0,0.75);
  opacity:0;transition:opacity 400ms}}
#mission-text.visible{{opacity:1}}
#mission-text.fade-out{{opacity:0}}

#zone-d{{position:fixed;bottom:0;left:0;width:100%;height:24vh;min-height:120px;z-index:20;
  display:flex;align-items:center;justify-content:space-evenly;padding:0 5%;
  background:rgba(0,0,0,0.65);border-top:1px solid rgba(255,255,255,0.15)}}
.tool-wrapper{{position:relative;cursor:pointer;display:flex;align-items:center;justify-content:center;
  min-width:44px;min-height:44px;width:min(22vw,18vh,140px);height:min(22vw,18vh,140px);
  opacity:0;transform:translateY(20px);
  transition:opacity 350ms ease-out, transform 350ms ease-out}}
.tool-wrapper.appeared{{opacity:1;transform:translateY(0)}}
.tool-wrapper:hover.appeared:not(.dimmed){{transform:translateY(0) scale(1.05)}}
.tool-wrapper.dimmed{{opacity:0.18;pointer-events:none;transform:translateY(0) scale(0.92)}}
.tool-wrapper.launched{{opacity:0;pointer-events:none}}
.tool-canvas{{width:100%;height:100%;display:block}}
.tool-info-icon{{position:absolute;top:6px;right:6px;width:22px;height:22px;border-radius:50%;
  background:rgba(0,0,0,0.6);color:#fff;font-size:0.75rem;font-weight:700;
  display:flex;align-items:center;justify-content:center;
  border:1px solid rgba(255,255,255,0.4);z-index:21;cursor:pointer;user-select:none}}
.tool-tooltip{{position:absolute;bottom:calc(100% + 8px);right:0;
  background:rgba(0,0,0,0.85);color:#fff;padding:6px 10px;border-radius:6px;
  font-size:0.8rem;white-space:nowrap;direction:rtl;
  opacity:0;transition:opacity 150ms;pointer-events:none;z-index:50}}
.tool-info-icon:hover + .tool-tooltip,.tool-info-icon:focus + .tool-tooltip,
.tool-tooltip.visible{{opacity:1}}

#checkpoint-text{{position:fixed;left:50%;bottom:25vh;transform:translateX(-50%);
  width:70%;text-align:center;direction:rtl;
  font-size:clamp(0.9rem,2.3vw,1.05rem);font-weight:600;line-height:1.4;color:#fff;
  background:rgba(0,0,0,0.78);padding:12px 20px;border-radius:8px;
  text-shadow:0 1px 3px rgba(0,0,0,0.95);z-index:35;
  opacity:0;transition:opacity 500ms;pointer-events:none}}
#checkpoint-text.visible{{opacity:1}}

#fade-overlay{{position:fixed;inset:0;background:#000;opacity:0;
  pointer-events:none;z-index:300;transition:opacity 800ms}}
#fade-overlay.active{{opacity:1}}
</style>
</head>
<body>
<div id="zone-a"><div id="progress-bar"><div id="progress-fill"></div></div></div>

<div id="zone-b">
  <!-- Phase 1: CSS sky + clouds -->
  <div id="bg-phase1">
    <div class="cloud-streak a"></div>
    <div class="cloud-streak b"></div>
    <div class="cloud-streak c"></div>
  </div>
  <!-- Phase 2: video jungle -->
  <video id="bg-phase2" muted playsinline preload="auto" loop src="{bg2_src}"></video>

  <!-- Hidden pose source videos (chroma keyer reads from these) -->
  <video id="player-A" class="player-source" muted playsinline preload="auto"></video>
  <video id="player-B" class="player-source" muted playsinline preload="auto"></video>

  <!-- Player frame wrapper (kills the square-frame artifact) -->
  <div id="player-frame">
    <canvas id="player-canvas"></canvas>
  </div>

  <div id="checkpoint-text"></div>
</div>

<div id="zone-c"><p id="mission-text"></p></div>
<div id="zone-d"></div>
<div id="fade-overlay"></div>

<script>
"use strict";
const SCENE = {scene_js};
const TRACKS = {tracks_js};
const TOOLS = {tools_js};
const RIVALS = {rivals_js};

const $ = (sel) => document.querySelector(sel);
const delay = (ms) => new Promise((r) => setTimeout(r, ms));

// ───────────────────────────────────────────────────────────────
// Chroma key — handles ~#4DAA47 medium green
// greenness = g - max(r,b). >60: full transparent. 18-60: soft alpha + despill.
// 4-18: despill only.
// ───────────────────────────────────────────────────────────────
function chromaKeyFrame(ctx, w, h) {{
  const frame = ctx.getImageData(0, 0, w, h);
  const d = frame.data;
  for (let i = 0; i < d.length; i += 4) {{
    const r = d[i], g = d[i+1], b = d[i+2];
    const greenness = g - Math.max(r, b);
    if (greenness > 60) {{
      d[i+3] = 0;
    }} else if (greenness > 18) {{
      const t = (greenness - 18) / 42;
      d[i+3] = Math.round(255 * (1 - t));
      const avgRB = (r + b) / 2;
      d[i+1] = Math.round(g * (1 - t) + avgRB * t);
    }} else if (greenness > 4) {{
      d[i+1] = Math.max(g - (greenness - 4) * 0.6, 0);
    }}
  }}
  ctx.putImageData(frame, 0, 0);
}}

// ───────────────────────────────────────────────────────────────
// Bg phase swap (sky → jungle) — cross-fade
// ───────────────────────────────────────────────────────────────
function swapToPhase2() {{
  const v = $("#bg-phase2");
  v.currentTime = 0;
  const playPromise = v.play();
  if (playPromise && playPromise.catch) playPromise.catch(() => {{}});
  v.classList.add("shown");
  $("#bg-phase1").classList.add("hidden");

  // Dim the sky-only rival dots over the new bg (they're parachute silhouettes — wouldn't be in canopy view)
  document.querySelectorAll(".rival-dot").forEach((d) => d.classList.add("dim"));
}}

// ───────────────────────────────────────────────────────────────
// Rival dots
// ───────────────────────────────────────────────────────────────
function buildRivals() {{
  const zone = $("#zone-b");
  RIVALS.forEach((r) => {{
    const dot = document.createElement("div");
    dot.className = "rival-dot";
    dot.id = r.id;
    dot.style.cssText = r.css || "";
    if (r.drift_animation) dot.style.animation = r.drift_animation;
    const wMatch = (r.css || "").match(/width:\\s*([\\d.]+)%/);
    if (wMatch) dot.style.height = wMatch[1] + "%";
    zone.appendChild(dot);
  }});
}}

// ───────────────────────────────────────────────────────────────
// Player pose pipeline
// ───────────────────────────────────────────────────────────────
const PLAYER = {{
  videoA: null,
  videoB: null,
  active: "A",
  canvas: null,
  ctx: null,
  curTrack: null,
  curIdx: -1,
  awaitingClick: false,
  firstFramePainted: false,
  curPlaybackRate: 1.0,
}};

function initPlayer() {{
  PLAYER.videoA = $("#player-A");
  PLAYER.videoB = $("#player-B");
  PLAYER.canvas = $("#player-canvas");
  PLAYER.ctx = PLAYER.canvas.getContext("2d", {{ willReadFrequently: true }});
  loadTrackByIdx(0);
  requestAnimationFrame(playerTicker);
}}

function activeVideo() {{
  return PLAYER.active === "A" ? PLAYER.videoA : PLAYER.videoB;
}}

function playerTicker() {{
  const v = activeVideo();
  const c = PLAYER.canvas;
  if (v && v.readyState >= 2 && v.videoWidth > 0) {{
    if (c.width !== v.videoWidth) {{
      c.width = v.videoWidth;
      c.height = v.videoHeight;
    }}
    PLAYER.ctx.clearRect(0, 0, c.width, c.height);
    PLAYER.ctx.drawImage(v, 0, 0, c.width, c.height);
    chromaKeyFrame(PLAYER.ctx, c.width, c.height);
    if (!PLAYER.firstFramePainted) {{
      PLAYER.firstFramePainted = true;
      // Reveal canvas only after the first chroma-keyed frame (kills black-rect placeholder)
      c.classList.add("ready");
    }}
  }}
  requestAnimationFrame(playerTicker);
}}

function loadTrackByIdx(idx) {{
  if (idx < 0 || idx >= TRACKS.length) return;
  const tr = TRACKS[idx];
  PLAYER.curIdx = idx;
  PLAYER.curTrack = tr;
  PLAYER.awaitingClick = (tr.loop_until_event === "tool_clicked");
  PLAYER.curPlaybackRate = tr.playback_rate || 1.0;

  const v = activeVideo();
  const wantSrc = tr.src;
  const hasSrc = v.getAttribute("src") || "";
  const srcDiffers = !hasSrc.endsWith(tr.pose_file);

  const seek = () => {{
    try {{ v.currentTime = tr.from_sec || 0; }} catch (_) {{}}
    v.playbackRate = PLAYER.curPlaybackRate;
    const p = v.play();
    if (p && p.catch) p.catch(() => {{}});
  }};

  if (srcDiffers) {{
    v.src = wantSrc;
    v.addEventListener("loadedmetadata", seek, {{ once: true }});
    v.load();
  }} else {{
    seek();
  }}

  // For pose-hold tracks, just freeze the frame
  if (tr.is_pose_hold) {{
    v.ontimeupdate = null;
    setTimeout(() => {{
      try {{ v.currentTime = tr.from_sec; v.pause(); }} catch (_) {{}}
    }}, 30);
    return;
  }}

  v.ontimeupdate = () => {{
    const cur = v.currentTime;
    if (cur >= tr.to_sec - 0.03) {{
      if (tr.loop_until_event === "tool_clicked" && PLAYER.awaitingClick) {{
        try {{ v.currentTime = tr.from_sec; }} catch (_) {{}}
      }} else {{
        // One-shot or autoplay-once: stop time advance; explicit handlers move us forward.
        try {{ v.currentTime = tr.to_sec; v.pause(); }} catch (_) {{}}
        v.ontimeupdate = null;
      }}
    }}
  }};
}}

function findTrackByTrigger(trigger) {{
  for (let i = 0; i < TRACKS.length; i++) {{
    if (TRACKS[i].trigger === trigger) return i;
  }}
  return -1;
}}

// ───────────────────────────────────────────────────────────────
// Tool rendering (chroma-key PNG → canvas with alpha)
// ───────────────────────────────────────────────────────────────
function renderToolToCanvas(tool, canvasEl, sizePx) {{
  return new Promise((resolve, reject) => {{
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.onload = () => {{
      canvasEl.width = sizePx;
      canvasEl.height = sizePx;
      const ctx = canvasEl.getContext("2d", {{ willReadFrequently: true }});
      const ratio = Math.min(sizePx / img.width, sizePx / img.height);
      const drawW = img.width * ratio, drawH = img.height * ratio;
      const dx = (sizePx - drawW) / 2, dy = (sizePx - drawH) / 2;
      ctx.clearRect(0, 0, sizePx, sizePx);
      ctx.drawImage(img, dx, dy, drawW, drawH);
      chromaKeyFrame(ctx, sizePx, sizePx);
      resolve();
    }};
    img.onerror = reject;
    img.src = tool.src;
  }});
}}

function buildTools() {{
  const container = $("#zone-d");
  const sizePx = Math.min(window.innerWidth * 0.22, window.innerHeight * 0.18, 140);
  TOOLS.forEach((tool, i) => {{
    const wrapper = document.createElement("div");
    wrapper.className = "tool-wrapper";
    wrapper.dataset.slot = tool.slot;

    const canvas = document.createElement("canvas");
    canvas.className = "tool-canvas";
    renderToolToCanvas(tool, canvas, Math.round(sizePx * 1.5));

    const icon = document.createElement("div");
    icon.className = "tool-info-icon";
    icon.textContent = "i";
    icon.tabIndex = 0;
    icon.setAttribute("aria-label", "מידע");

    const tooltip = document.createElement("div");
    tooltip.className = "tool-tooltip";
    tooltip.textContent = tool.label;  // verbatim, NO points

    icon.addEventListener("click", (e) => {{
      e.stopPropagation();
      tooltip.classList.add("visible");
      setTimeout(() => tooltip.classList.remove("visible"), 2000);
    }});

    canvas.addEventListener("click", () => handleToolSelection(tool, wrapper, canvas));

    wrapper.append(canvas, icon, tooltip);
    container.appendChild(wrapper);

    setTimeout(() => wrapper.classList.add("appeared"),
               SCENE.toolsFirstAppearMs + i * SCENE.toolStaggerMs);
  }});
}}

// ───────────────────────────────────────────────────────────────
// THE CATCH ANIMATION — Nirit's core demand
// ───────────────────────────────────────────────────────────────
async function handleToolSelection(tool, wrapper, canvasEl) {{
  if (!PLAYER.awaitingClick) return;
  PLAYER.awaitingClick = false;

  // Visual feedback: dim others
  document.querySelectorAll("#zone-d .tool-wrapper").forEach((w) => {{
    if (w !== wrapper) w.classList.add("dimmed");
  }});
  $("#mission-text").classList.add("fade-out");

  // 1. POSE_06 STARTS NOW — only on click. Hand begins at frame 3.0 (rest).
  const catchIdx = findTrackByTrigger("tool_clicked");
  if (catchIdx >= 0) loadTrackByIdx(catchIdx);

  // 2. Build the flying tool overlay from the tool's canvas bitmap
  const overlay = document.createElement("canvas");
  overlay.className = "tool-overlay";
  overlay.width = canvasEl.width;
  overlay.height = canvasEl.height;
  overlay.getContext("2d").drawImage(canvasEl, 0, 0);

  const startRect = wrapper.getBoundingClientRect();
  const startX = startRect.left + startRect.width / 2;
  const startY = startRect.top + startRect.height / 2;

  // Predict palm position at the catch moment
  // (player frame is fixed during catch — read its current position)
  const frameRect = $("#player-frame").getBoundingClientRect();
  const palmX = frameRect.left + frameRect.width * (tool.catch_x / 100);
  const palmY = frameRect.top + frameRect.height * (tool.catch_y / 100);
  const finalSize = Math.min(frameRect.width, frameRect.height) * tool.catch_scale;

  // Hide the source button (the tool 'launched' from it)
  wrapper.classList.add("launched");

  // Style overlay at start position
  overlay.style.left = (startX - startRect.width / 2) + "px";
  overlay.style.top = (startY - startRect.height / 2) + "px";
  overlay.style.width = startRect.width + "px";
  overlay.style.height = startRect.height + "px";
  document.body.appendChild(overlay);

  // 3. ARC FLIGHT — manual frame-by-frame animation for true bezier path
  // (CSS transitions only do straight lines; we want a curved arc)
  const flightMs = SCENE.toolFlightMs; // 1500
  const flightStart = performance.now();
  // Apex point: midway X, raised Y for the arc
  const apexX = (startX + palmX) / 2 + (palmX - startX) * 0.05;
  const apexY = Math.min(startY, palmY) - 80;

  return new Promise((resolveCatch) => {{
    function flightTick() {{
      const t = Math.min(1, (performance.now() - flightStart) / flightMs);
      // Ease: cubic-bezier-like (0.34, 1.16, 0.64, 1) approximation
      const eased = t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
      // Quadratic bezier: P = (1-t)^2*A + 2(1-t)t*B + t^2*C
      const u = eased;
      const x = (1 - u) * (1 - u) * startX + 2 * (1 - u) * u * apexX + u * u * palmX;
      const y = (1 - u) * (1 - u) * startY + 2 * (1 - u) * u * apexY + u * u * palmY;
      // Size lerp
      const w = startRect.width + (finalSize - startRect.width) * eased;
      const h = startRect.height + (finalSize - startRect.height) * eased;
      // Rotate slightly during flight
      const rot = (1 - eased) * -15;
      overlay.style.left = (x - w / 2) + "px";
      overlay.style.top = (y - h / 2) + "px";
      overlay.style.width = w + "px";
      overlay.style.height = h + "px";
      overlay.style.transform = `rotate(${{rot}}deg)`;

      if (t < 1) {{
        requestAnimationFrame(flightTick);
      }} else {{
        // 4. PALM CONTACT — pose_06 is at frame ~4.5 right now (timed sync)
        // Tiny "snap-to-palm" pulse
        overlay.style.transition = "transform 120ms ease-out";
        overlay.style.transform = "rotate(0deg) scale(1.08)";
        setTimeout(() => {{ overlay.style.transform = "rotate(0deg) scale(1.0)"; }}, 120);
        resolveCatch();
      }}
    }}
    requestAnimationFrame(flightTick);
  }}).then(async () => {{
    // 5. POST-CATCH HOLD (200ms) + remainder of pose_06 reaching frame 5.5
    const elapsed = SCENE.toolFlightMs;
    const catchTotal = SCENE.catchOneShotMs;
    const remaining = Math.max(0, catchTotal - elapsed);
    await delay(remaining);

    // 6. CATCH_COMPLETE → Player canvas CSS-jumps. BG cross-fades sky → jungle.
    $("#progress-fill").style.width = "10%";
    const jumpIdx = findTrackByTrigger("catch_complete");
    if (jumpIdx >= 0) loadTrackByIdx(jumpIdx);
    $("#player-frame").classList.add("jumping");
    swapToPhase2();

    // Tool overlay rides the player up — recompute target relative to jumped frame
    await delay(50);
    const f2 = $("#player-frame").getBoundingClientRect();
    const overlayX = f2.left + f2.width * (tool.catch_x / 100) - finalSize / 2;
    const overlayY = f2.top + f2.height * (tool.catch_y / 100) - finalSize / 2;
    overlay.style.transition = "left 600ms cubic-bezier(0.16,1,0.3,1), top 600ms cubic-bezier(0.16,1,0.3,1)";
    overlay.style.left = overlayX + "px";
    overlay.style.top = overlayY + "px";

    // 7. JUMP_APEX (after 300ms = peak of the jump curve)
    await delay(300);
    const landIdx = findTrackByTrigger("jump_apex");
    if (landIdx >= 0) loadTrackByIdx(landIdx);
    $("#player-frame").classList.remove("jumping");
    $("#player-frame").classList.add("landing");

    // Tool overlay transitions to landing attach point as player descends
    const landingMs = SCENE.landingDurationMs;
    setTimeout(() => {{
      const f3 = $("#player-frame").getBoundingClientRect();
      const newSize = Math.min(f3.width, f3.height) * tool.land_scale;
      const newX = f3.left + f3.width * (tool.land_x / 100) - newSize / 2;
      const newY = f3.top + f3.height * (tool.land_y / 100) - newSize / 2;
      overlay.style.transition = `left ${{landingMs}}ms cubic-bezier(0.34,1.16,0.64,1),`
                              + ` top ${{landingMs}}ms cubic-bezier(0.34,1.16,0.64,1),`
                              + ` width ${{landingMs}}ms ease-out,`
                              + ` height ${{landingMs}}ms ease-out`;
      overlay.style.left = newX + "px";
      overlay.style.top = newY + "px";
      overlay.style.width = newSize + "px";
      overlay.style.height = newSize + "px";
      if (tool.land_behind) overlay.classList.add("behind");
    }}, 50);

    // 8. LANDING_COMPLETE (after pose_03 reaches frame 5.0 = landing duration elapsed)
    await delay(landingMs);
    $("#progress-fill").style.width = "12%";

    // 9. CHECKPOINT TEXT — only AFTER landing is visually complete
    await delay(SCENE.checkpointOffsetAfterLandingMs);
    $("#checkpoint-text").textContent = SCENE.checkpointText;
    $("#checkpoint-text").classList.add("visible");

    // 10. Hold then fade
    await delay(SCENE.checkpointHoldMs + 200);
    $("#fade-overlay").classList.add("active");
  }});
}}

// ───────────────────────────────────────────────────────────────
// Init
// ───────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {{
  // Phase-1 bg is pure CSS — no setup needed
  buildRivals();
  initPlayer();
  buildTools();

  // Mission text fade-in
  setTimeout(() => {{
    $("#mission-text").textContent = SCENE.missionText;
    $("#mission-text").classList.add("visible");
  }}, SCENE.missionTextAppearMs);

  // Initial progress bump
  setTimeout(() => {{ $("#progress-fill").style.width = "8%"; }}, 1000);
}});
</script>
</body>
</html>
"""

    out = OUT_DIR / "M1.html"
    out.write_text(html, encoding="utf-8")
    print(f"M1 POC v4 -> {out.relative_to(PROJECT)}")
    print(f"  bg phase_1: CSS sky gradient + 3 cloud streaks (no plane interior)")
    print(f"  bg phase_2: {bg2_src}  (jungle landing surface)")
    print(f"  rivals:     {len(rivals)} CSS dots")
    print(f"  tracks:     {len(tracks)} pose segments")
    for i, tr in enumerate(tracks):
        loop = tr.get("loop_until_event") or tr.get("trigger") or "auto"
        hold = " [HOLD]" if tr.get("is_pose_hold") else ""
        print(f"    [{i}] {tr['pose_file']} {tr['from_sec']}-{tr['to_sec']}s  phase={tr['phase']}{hold}  trigger={loop}")
    print(f"  tools:")
    for t in tools:
        print(f"    {t['slot']}: {t['label']:30} {Path(t['src']).name:30} type={t['type']} land_behind={t['land_behind']}")
    print(f"")
    print(f"v4 critical fixes addressed:")
    print(f"  [x] No plane interior — CSS sky + clouds")
    print(f"  [x] No idle floaty pose — pose_04 running entry")
    print(f"  [x] No square frame — wrapper div + ready-gate on canvas")
    print(f"  [x] Hand raises ONLY on click — pose_06 starts on tool_clicked, never before")
    print(f"  [x] Real grab animation — bezier arc 1500ms, palm contact synced to frame 4.5")
    print(f"  [x] No parachute — pose_07 dropped entirely")
    print(f"  [x] Real landing — pose_03 #3.0-5.0 hands-to-ground")
    print(f"  [x] Checkpoint AFTER landing — fires at landing_complete+200ms")
    return 0


if __name__ == "__main__":
    sys.exit(main())
