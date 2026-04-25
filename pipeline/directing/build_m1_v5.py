"""build_m1_v5.py — Studio Emerald M1 v5 builder.

Final attempt at the interactive-movie path. Emits
C:/emerald/pipeline/builder_html/M1.html.

Reads ground truth from (all v5):
  pipeline/scene_briefs/scene_M1.json
  pipeline/scene_scripts/script_M1.json
  pipeline/set_lists/set_list_M1.json
  pipeline/sound_design_M1.json
  pipeline/pose_composition_map.json
  pipeline/tool_consequence_map.json

The 4 Nirit v4 rejections this build fixes:
  1. "היא רצה עם רקע בלי כלום, זה לא שמיים, זה לא מטוס, זה סתם רקע כחול וזהוב"
     -> Phase 1 uses bg_airplane.mp4 (real aerial). Phase 2 uses bg_jungle_clearing.mp4.
        Both rendered as <video autoplay loop muted>. NO CSS gradient.
  2. "היא רצה בלופים"
     -> pose_04 is one_shot. Plays exactly once 2.0-3.5 (1500ms) ending precisely
        at scene_entry+1500ms (= mission_text_shown). NEVER loops.
  3. "רצה את כל הסרטון של הpose"
     -> RAF-clamped strict segment enforcement. No video.loop=true. No timeupdate.
        Every track has a from_sec/to_sec; the RAF tick clamps currentTime.
  4. "ולאחר בחירת הכלי, היא עוד פעם מופיעה בתוך המסגרת ואז רואים את כל הרקע של
      הג'ונגל זז והיא מרחפת לה שם כמה שניות טובות, בעמידה מוחלטת"
     -> catch (2500ms) -> 600ms CSS jump -> pose_03 landing IMMEDIATELY at jump_apex.
        NO idle/standing window between catch and landing. Single CSS-translate of
        the player wrapper at jump_apex over 2000ms. No double position shift.

Editor's blocker resolved: POSE_BASE_DIR='C:/emerald/assets/player/' is hardcoded.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# UTF-8 stdout (Hebrew labels in print)
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT = Path(r"C:/emerald")
OUT_DIR = PROJECT / "pipeline" / "builder_html"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# === EDITOR BLOCKER FIX: hardcode pose base dir (issue_01) ===
POSE_BASE_DIR = "C:/emerald/assets/player/"

# === SWAPPABLE CONSTANTS (Human Review fallbacks) ===
# pose_05 segment 1.0-2.0 floaty re-validation:
#   default = (1.0, 2.0) loop
#   fallback A = (1.0, 1.5)  shorten
#   fallback B = is_pose_hold @ 1.0 (set POSE_05_HOLD = True)
POSE_05_SEGMENT = (1.0, 2.0)
POSE_05_HOLD = False  # If True, freeze at frame from_sec, no looping.
# pose_04 stride seam blend: bump from 200 -> 300 if seam visible.
POSE_04_BLEND_OUT_MS = 200


def main() -> None:
    """Read upstream v5 specs and emit the M1 HTML."""
    sb = json.loads((PROJECT / "pipeline" / "scene_briefs" / "scene_M1.json").read_text("utf-8"))
    sc = json.loads((PROJECT / "pipeline" / "scene_scripts" / "script_M1.json").read_text("utf-8"))
    sl = json.loads((PROJECT / "pipeline" / "set_lists" / "set_list_M1.json").read_text("utf-8"))
    sd = json.loads((PROJECT / "pipeline" / "sound_design_M1.json").read_text("utf-8"))
    pc = json.loads((PROJECT / "pipeline" / "pose_composition_map.json").read_text("utf-8"))
    tc = json.loads((PROJECT / "pipeline" / "tool_consequence_map.json").read_text("utf-8"))

    # ---------- Pose tracks (resolved with POSE_BASE_DIR) ----------
    raw_tracks = pc["missions"]["M1"]["tracks"]
    tracks = []
    for tr in raw_tracks:
        t = dict(tr)
        # Resolve pose_file -> absolute file:// URL.
        t["src"] = "file:///" + POSE_BASE_DIR + t["pose_file"]
        tracks.append(t)

    # Apply pose_05 swappable settings (Human Review fallbacks).
    for t in tracks:
        if t.get("phase") == "standing_wait":
            t["from_sec"] = POSE_05_SEGMENT[0]
            t["to_sec"] = POSE_05_SEGMENT[1]
            if POSE_05_HOLD:
                t["loop_until_event"] = None
                t["one_shot"] = True
                t["is_pose_hold"] = True
                t["to_sec"] = POSE_05_SEGMENT[0]
        if t.get("phase") == "running_entry":
            t["blend_out_ms"] = POSE_04_BLEND_OUT_MS

    # Unique pose files for preload (each as its own hidden <video>).
    pose_files = sorted({t["pose_file"] for t in tracks})  # e.g. pose_03.mp4..pose_06.mp4

    # ---------- Backgrounds (already absolute paths in spec) ----------
    bg_phase_1 = sb["background"]["phase_1"]["file"]  # bg_airplane.mp4
    bg_phase_2 = sb["background"]["phase_2"]["file"]  # bg_jungle_clearing.mp4

    # ---------- Scenery overlays (chroma-keyed PNGs) ----------
    rivals = sb["rivals"][0]  # competitors_in_air.png
    trees = sb["scenery"]["phase_2"][0]  # two_jungle_trees.png
    dust = sb["scenery"]["phase_2"][1]  # dust_clouds.png

    # ---------- Tools (from script, paths from scene_brief tool tracks) ----------
    tool_tracks = [t for t in sb["tracks"] if t.get("role") == "tool"]
    tool_tracks_by_slot = {t["slot"]: t for t in tool_tracks}
    consequences_M1 = tc["missions"]["M1"]
    tools = []
    for st in sc["tools"]:
        slot = st["slot"]
        cdef = consequences_M1[f"slot_{slot}"]
        tt = tool_tracks_by_slot[slot]
        tools.append({
            "slot": slot,
            "label": st["label"],
            "file": "file:///" + tt["file"].replace("\\", "/"),
            "type": cdef["type"],  # deploy | wear
            "in_ms": tt["in_ms"],
            "stagger_offset_ms": tt.get("stagger_offset_ms", 0),
            "attach_at_catch": cdef["attach_at_catch"],
            "attach_at_landing": cdef["attach_at_landing"],
        })

    # ---------- Texts ----------
    mission_text = sc["mission_text"]
    checkpoint_text = sc["checkpoint_text"]

    # ---------- Pose tracks for client (JSON) ----------
    client_tracks = []
    for t in tracks:
        client_tracks.append({
            "pose_file": t["pose_file"],
            "phase": t["phase"],
            "from_sec": t["from_sec"],
            "to_sec": t["to_sec"],
            "trigger": t["trigger"],
            "loop_until_event": t.get("loop_until_event"),
            "one_shot": t.get("one_shot", False),
            "is_pose_hold": t.get("is_pose_hold", False),
            "is_landing": t.get("is_landing", False),
            "duration_ms": t.get("duration_ms"),
            "blend_in_ms": t.get("blend_in_ms", 0),
            "blend_out_ms": t.get("blend_out_ms", 0),
        })

    # ---------- Sound events (silent fallback per builder contract) ----------
    sound_ambients = sd.get("ambient_phases", {})
    sound_events = sd.get("events", [])

    html = build_html(
        bg_phase_1=bg_phase_1,
        bg_phase_2=bg_phase_2,
        rivals=rivals,
        trees=trees,
        dust=dust,
        pose_files=pose_files,
        tracks=client_tracks,
        tools=tools,
        mission_text=mission_text,
        checkpoint_text=checkpoint_text,
        sound_ambients=sound_ambients,
        sound_events=sound_events,
    )

    out_path = OUT_DIR / "M1.html"
    out_path.write_text(html, encoding="utf-8")
    print(f"[builder_v5] wrote {out_path} ({len(html):,} bytes)")

    # Pre-flight asset existence check.
    asset_paths = [
        bg_phase_1, bg_phase_2,
        rivals["file"], trees["file"], dust["file"],
        *(POSE_BASE_DIR + p for p in pose_files),
        *(t["file"].replace("file:///", "") for t in tools),
    ]
    missing = [p for p in asset_paths if not Path(p).exists()]
    if missing:
        print("[builder_v5] MISSING FILES:")
        for p in missing:
            print(f"  - {p}")
        raise SystemExit(2)
    print(f"[builder_v5] pre-flight: {len(asset_paths)} assets verified on disk")


def build_html(*, bg_phase_1, bg_phase_2, rivals, trees, dust,
               pose_files, tracks, tools, mission_text, checkpoint_text,
               sound_ambients, sound_events) -> str:
    """Compose the full HTML document."""
    # Convert local paths -> file:// URLs for browser playback.
    def f(p): return "file:///" + p.replace("\\", "/")
    bg1_url = f(bg_phase_1)
    bg2_url = f(bg_phase_2)
    rivals_url = f(rivals["file"])
    trees_url = f(trees["file"])
    dust_url = f(dust["file"])

    # JSON payloads embedded for the client.
    payload = {
        "tracks": tracks,
        "tools": [
            {
                "slot": t["slot"],
                "label": t["label"],
                "file": t["file"],
                "type": t["type"],
                "in_ms": t["in_ms"],
                "stagger_offset_ms": t["stagger_offset_ms"],
                "attach_at_catch": t["attach_at_catch"],
                "attach_at_landing": t["attach_at_landing"],
            } for t in tools
        ],
        "missionText": mission_text,
        "checkpointText": checkpoint_text,
        "poseBaseFiles": pose_files,
        "soundAmbients": sound_ambients,
        "soundEvents": sound_events,
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
    payload_json = json.dumps(payload, ensure_ascii=False)

    # Pose video elements (one hidden <video> per file — never reassign src).
    pose_video_tags = "\n".join(
        f'  <video id="pose-{p.replace("pose_", "").replace(".mp4", "")}" '
        f'src="file:///{POSE_BASE_DIR}{p}" muted playsinline preload="auto" '
        f'crossorigin="anonymous"></video>'
        for p in pose_files
    )

    return f"""<!DOCTYPE html>
<html dir="rtl" lang="he">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">
<title>M1 — משלחת אל עיר האזמרגד</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
html, body {{ width:100vw; height:100vh; overflow:hidden; background:#000;
  font-family:'Heebo','Assistant',sans-serif; color:#fff; }}

/* === ZONES (design_system.md) === */
#zone-a {{ position:fixed; top:0; left:0; width:100%; height:6vh; min-height:28px;
  z-index:100; background:#1a1a1a; }}
#zone-b {{ position:fixed; top:6vh; left:0; width:100%; height:54vh; z-index:1;
  overflow:hidden; }}
#zone-c {{ position:fixed; top:60vh; left:0; width:100%; height:16vh; z-index:30;
  display:flex; align-items:center; justify-content:center; padding:0 5%; }}
#zone-d {{ position:fixed; bottom:0; left:0; width:100%; height:24vh; min-height:120px;
  z-index:20; background:rgba(0,0,0,0.65);
  border-top:1px solid rgba(255,255,255,0.15);
  display:flex; align-items:center; justify-content:space-evenly; padding:0 5%; }}

/* === BACKGROUND VIDEOS (always in DOM, opacity-toggled) === */
.bg-video {{ position:absolute; inset:0; width:100%; height:100%;
  object-fit:cover; z-index:0; transition:opacity 400ms ease-in-out; }}
#bg-phase-1 {{ opacity:1; }}
#bg-phase-2 {{ opacity:0; }}

/* === SCENERY CANVASES (chroma-keyed PNGs) === */
.scenery-canvas {{ position:absolute; pointer-events:none;
  transition:opacity 400ms ease-in-out; }}
#rivals-canvas  {{ top:6%; left:5%; width:90%; height:60%; opacity:0.78; z-index:3;
  filter:blur(0.4px); animation:rivalsDriftA 18s linear infinite; }}
#trees-canvas   {{ bottom:0; left:-5%; width:35%; height:80%; opacity:0; z-index:4; }}
#dust-canvas    {{ bottom:8%; right:30%; width:18%; height:25%; opacity:0; z-index:15; }}

@keyframes rivalsDriftA {{
  0% {{ transform:translateX(0); }}
  50% {{ transform:translateX(2vw); }}
  100% {{ transform:translateX(0); }}
}}

/* === PLAYER WRAPPER (single position anchor before landing) === */
#player-wrapper {{
  position:absolute;
  bottom:6%; right:55%; height:54%;
  z-index:10;
  transform:scaleX(-1);  /* pose_04 facing left */
  transition:none;
  will-change:transform, bottom, right, height;
  pointer-events:none;
}}
#player-wrapper.facing-frontal {{ transform:scaleX(1); }}
#player-wrapper.jumping {{
  animation:player-jump 600ms cubic-bezier(0.16,1,0.3,1) forwards;
}}
#player-wrapper.landing-anchor {{
  bottom:5%; right:30%; height:55%;
  transition:bottom 2000ms cubic-bezier(0.4,0,0.2,1),
             right 2000ms cubic-bezier(0.4,0,0.2,1),
             height 2000ms cubic-bezier(0.4,0,0.2,1);
}}
@keyframes player-jump {{
  0%   {{ transform:scaleX(1) translateY(0)     scale(1)    rotate(0); }}
  50%  {{ transform:scaleX(1) translateY(-12vh) scale(1.04) rotate(-2deg); }}
  100% {{ transform:scaleX(1) translateY(-6vh)  scale(1.02) rotate(-1deg); }}
}}

#player-canvas {{
  width:100%; height:100%; object-fit:contain; opacity:0;
  transition:opacity 200ms linear;
}}
#player-canvas.visible {{ opacity:1; }}

/* === HIDDEN POSE VIDEOS === */
.hidden-video {{ display:none; }}

/* === MISSION TEXT === */
#mission-text {{
  color:#fff; direction:rtl; text-align:center;
  font-size:clamp(0.95rem, 2.5vw, 1.15rem); font-weight:600; line-height:1.5;
  text-shadow:0 1px 3px rgba(0,0,0,0.9), 0 2px 8px rgba(0,0,0,0.7);
  opacity:0; transition:opacity 400ms ease-in-out;
  max-width:64%;
}}
#mission-text.visible {{ opacity:1; }}

/* === TOOLS === */
.tool-wrapper {{
  position:relative;
  width:min(28vw, 20vh, 140px);
  height:min(28vw, 20vh, 140px);
  cursor:pointer;
  opacity:0; transform:translateY(20px);
  transition:opacity 350ms ease-out, transform 350ms ease-out;
  pointer-events:none;
}}
.tool-wrapper.visible {{ opacity:1; transform:translateY(0); pointer-events:auto; }}
.tool-wrapper.dimmed {{ opacity:0.3; pointer-events:none; }}
.tool-wrapper.flying {{ position:fixed; left:0; top:0; pointer-events:none;
  transition:none; z-index:25; }}
.tool-wrapper.attached {{ position:absolute; left:0; top:0; pointer-events:none;
  transition:none; z-index:20; }}
.tool-wrapper img {{ width:100%; height:100%; object-fit:contain; user-select:none;
  -webkit-user-drag:none; }}
.tool-info-icon {{
  position:absolute; top:6px; right:6px; width:22px; height:22px;
  border-radius:50%; background:rgba(0,0,0,0.6); color:#fff;
  font-size:0.75rem; font-weight:700; display:flex; align-items:center;
  justify-content:center; border:1px solid rgba(255,255,255,0.4);
  z-index:21; cursor:pointer;
}}
.tool-tooltip {{
  position:absolute; bottom:calc(100% + 8px); right:0;
  background:rgba(0,0,0,0.85); color:#fff; padding:5px 10px; border-radius:6px;
  font-size:0.85rem; white-space:nowrap; direction:rtl;
  opacity:0; transition:opacity 150ms; pointer-events:none; z-index:50;
}}
.tool-tooltip.visible {{ opacity:1; }}

/* === CHECKPOINT TEXT === */
#checkpoint-text {{
  position:fixed; bottom:26vh; left:0; width:100%; text-align:center;
  color:#fff; direction:rtl; font-size:clamp(0.95rem, 2.2vw, 1.05rem);
  font-weight:500;
  text-shadow:0 1px 3px rgba(0,0,0,0.9), 0 2px 8px rgba(0,0,0,0.7);
  opacity:0; transition:opacity 400ms ease-in-out;
  z-index:30; padding:0 5%;
}}
#checkpoint-text.visible {{ opacity:1; }}

/* === FADE-TO-BLACK OVERLAY === */
#fade-overlay {{ position:fixed; inset:0; background:#000; opacity:0;
  transition:opacity 600ms linear; z-index:200; pointer-events:none; }}
#fade-overlay.visible {{ opacity:1; }}
</style>
</head>
<body>

<!-- ZONE A: progress bar -->
<div id="zone-a"></div>

<!-- ZONE B: scene -->
<div id="zone-b">
  <!-- BG videos: BOTH in DOM, opacity-toggled at jump_apex (NO src reassignment) -->
  <video id="bg-phase-1" class="bg-video" src="{bg1_url}"
         autoplay loop muted playsinline></video>
  <video id="bg-phase-2" class="bg-video" src="{bg2_url}"
         autoplay loop muted playsinline></video>

  <!-- Hidden source images for chroma key (drawn into canvases) -->
  <img id="rivals-img" src="{rivals_url}" style="display:none" alt="">
  <img id="trees-img"  src="{trees_url}"  style="display:none" alt="">
  <img id="dust-img"   src="{dust_url}"   style="display:none" alt="">

  <!-- Chroma-keyed scenery canvases -->
  <canvas id="rivals-canvas" class="scenery-canvas"></canvas>
  <canvas id="trees-canvas"  class="scenery-canvas"></canvas>
  <canvas id="dust-canvas"   class="scenery-canvas"></canvas>

  <!-- Hidden pose videos (preloaded, never .src reassigned) -->
  <div class="hidden-video">
{pose_video_tags}
  </div>

  <!-- Player wrapper (single position anchor) -->
  <div id="player-wrapper">
    <canvas id="player-canvas"></canvas>
  </div>
</div>

<!-- ZONE C: mission text -->
<div id="zone-c">
  <p id="mission-text"></p>
</div>

<!-- ZONE D: tools -->
<div id="zone-d"></div>

<!-- Checkpoint text overlay -->
<p id="checkpoint-text"></p>

<!-- Fade overlay -->
<div id="fade-overlay"></div>

<script>
"use strict";

const PAYLOAD = {payload_json};
const POSE_BASE = "{POSE_BASE_DIR}";

// ───────────────────────── Event bus ─────────────────────────
const sceneBus = new EventTarget();
const PLAYER = {{ awaitingEvent: null }};
function emit(name, detail) {{
  // console.log('[evt]', name, detail || '');
  sceneBus.dispatchEvent(new CustomEvent(name, {{ detail }}));
  document.dispatchEvent(new CustomEvent(name, {{ detail }}));
}}

// ───────────────────────── Sound (silent fallback) ───────────
const SOUND = {{ enabled: true, ambientNodes: {{}} }};
function tryPlayAudio(file, volume) {{
  if (!file || file.startsWith('placeholder:')) return null;
  try {{
    const a = new Audio(file);
    a.volume = volume != null ? volume : 0.6;
    a.play().catch(() => {{}});
    return a;
  }} catch (e) {{ return null; }}
}}
function bindSoundEvents() {{
  for (const ev of PAYLOAD.soundEvents || []) {{
    sceneBus.addEventListener(ev.trigger, (e) => {{
      if (ev.trigger_filter && ev.trigger_filter.slot
          && (!e.detail || e.detail.slot !== ev.trigger_filter.slot)) return;
      const delay = ev.delay_after_trigger_ms || 0;
      setTimeout(() => tryPlayAudio(ev.audio_file, ev.volume), delay);
    }});
  }}
  // Ambient phases: phase_1 starts at scene_entry; phase_2 at jump_apex.
  const a1 = (PAYLOAD.soundAmbients || {{}}).phase_1_sky;
  const a2 = (PAYLOAD.soundAmbients || {{}}).phase_2_jungle;
  if (a1) sceneBus.addEventListener('scene_entry', () =>
    SOUND.ambientNodes.a1 = tryPlayAudio(a1.audio_file, a1.volume));
  if (a2) sceneBus.addEventListener('jump_apex', () => {{
    if (SOUND.ambientNodes.a1) {{ try {{ SOUND.ambientNodes.a1.pause(); }} catch (e) {{}} }}
    SOUND.ambientNodes.a2 = tryPlayAudio(a2.audio_file, a2.volume);
  }});
}}

// ───────────────────────── Chroma key ─────────────────────────
function chromaCanvasFromVideo(canvasEl, getActiveVideo) {{
  const ctx = canvasEl.getContext('2d');
  function tick() {{
    const v = getActiveVideo();
    if (v && v.readyState >= 2 && !v.paused) {{
      if (canvasEl.width !== v.videoWidth || canvasEl.height !== v.videoHeight) {{
        canvasEl.width = v.videoWidth;
        canvasEl.height = v.videoHeight;
      }}
      try {{
        ctx.drawImage(v, 0, 0, canvasEl.width, canvasEl.height);
        const frame = ctx.getImageData(0, 0, canvasEl.width, canvasEl.height);
        const d = frame.data;
        for (let i = 0; i < d.length; i += 4) {{
          const r = d[i], g = d[i+1], b = d[i+2];
          if (g > 100 && g > r * 1.4 && g > b * 1.4) d[i+3] = 0;
        }}
        ctx.putImageData(frame, 0, 0);
        canvasEl.classList.add('visible');
      }} catch (e) {{ /* cross-origin tainting fallback: just leave canvas */ }}
    }}
    requestAnimationFrame(tick);
  }}
  requestAnimationFrame(tick);
}}

function chromaCanvasFromImage(canvasEl, imgEl) {{
  function bake() {{
    if (!imgEl.complete || !imgEl.naturalWidth) return;
    canvasEl.width = imgEl.naturalWidth;
    canvasEl.height = imgEl.naturalHeight;
    const ctx = canvasEl.getContext('2d');
    try {{
      ctx.drawImage(imgEl, 0, 0);
      const frame = ctx.getImageData(0, 0, canvasEl.width, canvasEl.height);
      const d = frame.data;
      for (let i = 0; i < d.length; i += 4) {{
        const r = d[i], g = d[i+1], b = d[i+2];
        if (g > 100 && g > r * 1.4 && g > b * 1.4) d[i+3] = 0;
      }}
      ctx.putImageData(frame, 0, 0);
    }} catch (e) {{ /* tainted fallback */ }}
  }}
  if (imgEl.complete) bake();
  else imgEl.addEventListener('load', bake, {{ once: true }});
}}

// ───────────────────────── Pose manager (RAF-clamped) ─────────
const POSES = {{}}; // pose_03 -> <video> ; pose_04 -> <video> ; ...
let activePoseVideo = null;
let currentTrack = null;
let currentTrackIndex = -1;

function getPoseVideo(filename) {{
  // 'pose_04.mp4' -> 'pose-04'
  const id = 'pose-' + filename.replace('pose_', '').replace('.mp4', '');
  return document.getElementById(id);
}}

function preloadAllPoses() {{
  const ids = (PAYLOAD.poseBaseFiles || []).map(f =>
    'pose-' + f.replace('pose_', '').replace('.mp4', ''));
  return Promise.all(ids.map(id => new Promise(resolve => {{
    const v = document.getElementById(id);
    POSES[id] = v;
    if (!v) return resolve();
    v.loop = false; // CRITICAL: never .loop=true
    v.muted = true;
    v.playsInline = true;
    if (v.readyState >= 2) return resolve();
    const onReady = () => {{ v.removeEventListener('loadedmetadata', onReady); resolve(); }};
    v.addEventListener('loadedmetadata', onReady);
    v.addEventListener('canplay', onReady, {{ once: true }});
    // safety timeout — never block forever
    setTimeout(resolve, 1500);
  }})));
}}

function startTrack(track) {{
  // Pause previous video.
  if (activePoseVideo && activePoseVideo !== getPoseVideo(track.pose_file)) {{
    try {{ activePoseVideo.pause(); }} catch (e) {{}}
  }}
  currentTrack = track;
  const v = getPoseVideo(track.pose_file);
  activePoseVideo = v;
  if (!v) return;
  v.loop = false;
  // Set currentTime, then play.
  const startSeek = () => {{
    try {{ v.currentTime = track.from_sec; }} catch (e) {{}}
    if (track.is_pose_hold && track.from_sec === track.to_sec) {{
      v.pause();
    }} else {{
      v.play().catch(() => {{}});
    }}
  }};
  if (v.readyState >= 1) startSeek();
  else v.addEventListener('loadedmetadata', startSeek, {{ once: true }});

  // facing flip handling
  const wrapper = document.getElementById('player-wrapper');
  if (track.phase === 'running_entry') {{
    wrapper.classList.remove('facing-frontal');
  }} else {{
    wrapper.classList.add('facing-frontal');
  }}
}}

// Single global pose RAF loop — clamps to_sec strictly.
function poseRafTick() {{
  const v = activePoseVideo;
  const t = currentTrack;
  if (v && t && !v.paused && v.readyState >= 2) {{
    if (v.currentTime >= t.to_sec - 0.005) {{
      const isLoop = !!t.loop_until_event && PLAYER.awaitingEvent === t.loop_until_event;
      if (isLoop) {{
        try {{ v.currentTime = t.from_sec; }} catch (e) {{}}
      }} else if (t.is_pose_hold) {{
        try {{ v.currentTime = t.to_sec; }} catch (e) {{}}
        v.pause();
      }} else if (t.is_landing) {{
        try {{ v.currentTime = t.to_sec; }} catch (e) {{}}
        v.pause();
        const justEnded = t;
        currentTrack = null;
        emit('landing_complete', {{ phase: justEnded.phase }});
      }} else if (t.one_shot) {{
        try {{ v.currentTime = t.to_sec; }} catch (e) {{}}
        v.pause();
        const justEnded = t;
        currentTrack = null;
        emitTrackComplete(justEnded);
      }}
    }}
  }}
  requestAnimationFrame(poseRafTick);
}}

function emitTrackComplete(track) {{
  if (track.phase === 'running_entry') {{
    // pose_04 finished — but mission_text_shown also fires from its own timer.
    // Nothing to emit here; pose_05 starts on mission_text_shown.
  }} else if (track.phase === 'catch_one_shot') {{
    emit('catch_complete', {{}});
  }}
  // jump_css_overlay & landing emit their own events elsewhere.
}}

// ───────────────────────── Bg phase swap ─────────────────────
function setupBgPhaseSwap() {{
  sceneBus.addEventListener('jump_apex', () => {{
    document.getElementById('bg-phase-1').style.opacity = '0';
    document.getElementById('bg-phase-2').style.opacity = '1';
  }});
}}

// ───────────────────────── Tool flight (bezier arc) ───────────
function getRect(el) {{ return el.getBoundingClientRect(); }}

function flyToolToPalm(toolEl, slot) {{
  const wrapper = document.getElementById('player-wrapper');
  const wRect = getRect(wrapper);
  // palm anchor 0.40 X / 0.32 Y of player wrapper at frame 4.5
  const palmX = wRect.left + wRect.width * 0.40;
  const palmY = wRect.top + wRect.height * 0.32;

  const startRect = getRect(toolEl);
  const startX = startRect.left;
  const startY = startRect.top;
  const startW = startRect.width;
  const startH = startRect.height;

  // Take tool out of zone-D flow.
  toolEl.classList.add('flying');
  toolEl.style.left = startX + 'px';
  toolEl.style.top = startY + 'px';
  toolEl.style.width = startW + 'px';
  toolEl.style.height = startH + 'px';

  const peakY = Math.min(startY, palmY) - 80;
  const targetW = startW * 0.50;
  const targetH = startH * 0.50;
  const targetX = palmX - targetW / 2;
  const targetY = palmY - targetH / 2;

  const duration = PAYLOAD.timing.toolFlightMs;
  const startTime = performance.now();

  // Custom bezier (parabolic-ish); we precompute a y-arc via parametric quadratic.
  function tick(now) {{
    const linear = Math.min(1, (now - startTime) / duration);
    // overshoot ease (cubic-bezier(0.34,1.56,0.64,1)) ≈ approximation:
    const c1 = 0.34, c2 = 0.64;
    // cubic-bezier solver crude approx via cubic-out + small overshoot
    const t = linear;
    // bezier ease (overshoot) — simple polynomial approx of cubic-bezier(.34,1.56,.64,1):
    let eased = 1 - Math.pow(1 - t, 3);
    if (t < 0.85) eased += Math.sin(t * Math.PI) * 0.08;
    eased = Math.max(0, Math.min(1.05, eased));

    // Quadratic vertical arc through peak.
    const yArc = (1 - t) * (1 - t) * startY + 2 * (1 - t) * t * peakY + t * t * (palmY - targetH / 2);
    const x = startX + (targetX - startX) * eased;
    const w = startW + (targetW - startW) * eased;
    const h = startH + (targetH - startH) * eased;

    toolEl.style.left = x + 'px';
    toolEl.style.top = yArc + 'px';
    toolEl.style.width = w + 'px';
    toolEl.style.height = h + 'px';

    if (linear < 1) requestAnimationFrame(tick);
    else attachToolToWrapper(toolEl, slot);
  }}
  requestAnimationFrame(tick);
}}

function attachToolToWrapper(toolEl, slot) {{
  // Reparent tool into the player wrapper using percentage anchors so it
  // follows the wrapper through the CSS jump and the landing translate.
  const wrapper = document.getElementById('player-wrapper');
  toolEl.classList.remove('flying');
  toolEl.classList.add('attached');
  // Move into wrapper.
  wrapper.appendChild(toolEl);
  const tool = PAYLOAD.tools.find(t => t.slot === slot);
  const a = tool.attach_at_catch;
  // anchor relative to wrapper bounds.
  toolEl.style.left = `calc(${{a.point_on_player_pct.x}}% - ${{(a.scale_factor * 100) / 2}}%)`;
  toolEl.style.top  = `calc(${{a.point_on_player_pct.y}}% - ${{(a.scale_factor * 100) / 2}}%)`;
  toolEl.style.width  = `${{a.scale_factor * 100}}%`;
  toolEl.style.height = `${{a.scale_factor * 100}}%`;
  toolEl.style.zIndex = '20';
}}

function applyToolUnfurl(slot) {{
  // During first 400ms of CSS jump rise, animate tool from
  // attach_at_catch -> attach_at_landing (per production_designer v5).
  const tool = PAYLOAD.tools.find(t => t.slot === slot);
  if (!tool) return;
  const wrapper = document.getElementById('player-wrapper');
  const toolEl = wrapper.querySelector('.tool-wrapper.attached');
  if (!toolEl) return;
  const a = tool.attach_at_catch;
  const b = tool.attach_at_landing;
  const dur = 400;
  const start = performance.now();

  // z-index switch on unfurl-start (deploy/wear -> behind player at z=9).
  if (tool.type === 'deploy' || tool.type === 'wear') {{
    toolEl.style.zIndex = '9';
  }}

  function step(now) {{
    const t = Math.min(1, (now - start) / dur);
    const e = 1 - Math.pow(1 - t, 2);
    const x = a.point_on_player_pct.x + (b.point_on_player_pct.x - a.point_on_player_pct.x) * e;
    const y = a.point_on_player_pct.y + (b.point_on_player_pct.y - a.point_on_player_pct.y) * e;
    const s = a.scale_factor + (b.scale_factor - a.scale_factor) * e;
    toolEl.style.left = `calc(${{x}}% - ${{(s * 100) / 2}}%)`;
    toolEl.style.top  = `calc(${{y}}% - ${{(s * 100) / 2}}%)`;
    toolEl.style.width  = `${{s * 100}}%`;
    toolEl.style.height = `${{s * 100}}%`;
    if (t < 1) requestAnimationFrame(step);
  }}
  requestAnimationFrame(step);
}}

// ───────────────────────── Tool UI (zone D) ──────────────────
function buildTools() {{
  const container = document.getElementById('zone-d');
  for (const tool of PAYLOAD.tools) {{
    const wrap = document.createElement('div');
    wrap.className = 'tool-wrapper';
    wrap.dataset.slot = tool.slot;

    const img = document.createElement('img');
    img.src = tool.file;
    img.alt = tool.label;
    img.draggable = false;
    wrap.appendChild(img);

    const ic = document.createElement('div');
    ic.className = 'tool-info-icon';
    ic.textContent = 'i';
    wrap.appendChild(ic);

    const tip = document.createElement('div');
    tip.className = 'tool-tooltip';
    tip.textContent = tool.label;
    wrap.appendChild(tip);

    ic.addEventListener('mouseenter', () => tip.classList.add('visible'));
    ic.addEventListener('mouseleave', () => tip.classList.remove('visible'));
    ic.addEventListener('click', (e) => {{
      e.stopPropagation();
      tip.classList.add('visible');
      setTimeout(() => tip.classList.remove('visible'), 2000);
    }});

    wrap.addEventListener('click', (e) => {{
      if (e.target === ic) return;
      onToolClicked(tool.slot, wrap);
    }});

    container.appendChild(wrap);
  }}

  // Stagger entry per tool in_ms.
  for (const tool of PAYLOAD.tools) {{
    setTimeout(() => {{
      const w = document.querySelector(`.tool-wrapper[data-slot="${{tool.slot}}"]`);
      if (w) w.classList.add('visible');
    }}, tool.in_ms);
  }}
}}

// ───────────────────────── Tool click handler ────────────────
let toolHasBeenClicked = false;
function onToolClicked(slot, wrapEl) {{
  if (toolHasBeenClicked) return;
  toolHasBeenClicked = true;
  PLAYER.awaitingEvent = null; // break pose_05 loop
  emit('tool_clicked', {{ slot }});

  // Dim other tools.
  document.querySelectorAll('.tool-wrapper').forEach(el => {{
    if (el !== wrapEl) el.classList.add('dimmed');
  }});
  // Click feedback pulse.
  wrapEl.animate([
    {{ transform: 'scale(1)' }},
    {{ transform: 'scale(1.1)' }},
    {{ transform: 'scale(1)' }}
  ], {{ duration: 200, easing: 'ease-out' }});

  // Mission text fade out.
  document.getElementById('mission-text').classList.remove('visible');

  // Fly tool to palm.
  flyToolToPalm(wrapEl, slot);

  // pose_06 catch starts now.
  const catchTrack = PAYLOAD.tracks.find(t => t.phase === 'catch_one_shot');
  startTrack(catchTrack);
}}

// ───────────────────────── Catch -> Jump -> Apex -> Land ─────
function setupSequence() {{
  const tracks = PAYLOAD.tracks;
  const T = id => tracks.find(t => t.phase === id);

  // catch_complete -> start CSS jump on wrapper, jump_apex 300ms in
  sceneBus.addEventListener('catch_complete', () => {{
    const wrapper = document.getElementById('player-wrapper');
    // stay on pose_06 frame 5.5 hold.
    const jumpHold = T('jump_css_overlay');
    startTrack(jumpHold);
    wrapper.classList.add('jumping');
    const slot = currentClickedSlot;
    if (slot) applyToolUnfurl(slot);
    setTimeout(() => emit('jump_apex', {{}}),
      PAYLOAD.timing.jumpApexOffsetFromCatchCompleteMs);
  }});

  // jump_apex -> start landing pose, translate wrapper to landing anchor,
  // bg/scenery swap, dust trigger 1800ms later.
  sceneBus.addEventListener('jump_apex', () => {{
    const wrapper = document.getElementById('player-wrapper');
    wrapper.classList.add('landing-anchor');
    // Start pose_03 landing.
    const landTrack = T('landing');
    startTrack(landTrack);

    // Rivals fade out, trees fade in.
    const rivals = document.getElementById('rivals-canvas');
    const trees  = document.getElementById('trees-canvas');
    if (rivals) rivals.style.opacity = '0';
    if (trees)  trees.style.opacity  = '0.95';

    // Dust puff at +1800ms.
    setTimeout(() => {{
      const dust = document.getElementById('dust-canvas');
      dust.style.opacity = '0.6';
      dust.style.transform = 'scale(1.0)';
      setTimeout(() => {{
        dust.style.opacity = '0';
        dust.style.transform = 'scale(1.2)';
      }}, 270);
    }}, PAYLOAD.timing.dustOffsetFromJumpApexMs);
  }});

  // landing_complete -> checkpoint text +200ms, fade-to-black later.
  sceneBus.addEventListener('landing_complete', () => {{
    setTimeout(() => {{
      const cp = document.getElementById('checkpoint-text');
      cp.textContent = PAYLOAD.checkpointText;
      cp.classList.add('visible');
      emit('checkpoint_text_shown', {{}});
    }}, PAYLOAD.timing.checkpointOffsetAfterLandingMs);
    setTimeout(() => {{
      document.getElementById('fade-overlay').classList.add('visible');
    }}, PAYLOAD.timing.checkpointOffsetAfterLandingMs
       + PAYLOAD.timing.checkpointHoldMs + 200);
  }});
}}

// Track which slot was clicked (for tool unfurl).
let currentClickedSlot = null;
sceneBus.addEventListener('tool_clicked', (e) => {{
  currentClickedSlot = e.detail && e.detail.slot;
}});

// ───────────────────────── Mission text + pose timeline ──────
function setupTimeline() {{
  const tracks = PAYLOAD.tracks;
  const T = id => tracks.find(t => t.phase === id);

  // Set up pose-05 loop awaiting tool_clicked via PLAYER.awaitingEvent.
  // pose_04 (running_entry) fires on scene_entry.
  // pose_05 (standing_wait) fires on mission_text_shown.

  sceneBus.addEventListener('scene_entry', () => {{
    PLAYER.awaitingEvent = null;
    startTrack(T('running_entry'));
  }});

  // Mission text fade-in at +1500ms, emits mission_text_shown.
  setTimeout(() => {{
    const mt = document.getElementById('mission-text');
    mt.textContent = PAYLOAD.missionText;
    mt.classList.add('visible');
    emit('mission_text_shown', {{}});
  }}, PAYLOAD.timing.missionTextAppearsMs);

  sceneBus.addEventListener('mission_text_shown', () => {{
    PLAYER.awaitingEvent = 'tool_clicked';
    startTrack(T('standing_wait'));
  }});
}}

// ───────────────────────── Init ─────────────────────────────
async function init() {{
  // Bind sound listeners early.
  bindSoundEvents();

  // Wire bg phase swap.
  setupBgPhaseSwap();

  // Set up player chroma key — reads from activePoseVideo.
  chromaCanvasFromVideo(document.getElementById('player-canvas'),
    () => activePoseVideo);

  // Scenery chroma keys (one-shot bake from <img>).
  chromaCanvasFromImage(document.getElementById('rivals-canvas'),
    document.getElementById('rivals-img'));
  chromaCanvasFromImage(document.getElementById('trees-canvas'),
    document.getElementById('trees-img'));
  chromaCanvasFromImage(document.getElementById('dust-canvas'),
    document.getElementById('dust-img'));

  // Preload all 4 pose videos to readyState >= 2.
  await preloadAllPoses();

  // Build tool UI.
  buildTools();

  // Wire sequence listeners.
  setupSequence();

  // Wire timeline.
  setupTimeline();

  // Start global pose RAF.
  requestAnimationFrame(poseRafTick);

  // Force-play bg videos (some browsers need a kick).
  const bg1 = document.getElementById('bg-phase-1');
  const bg2 = document.getElementById('bg-phase-2');
  bg1.play().catch(()=>{{}});
  bg2.play().catch(()=>{{}});

  // Fire scene_entry.
  emit('scene_entry', {{}});
}}

document.addEventListener('DOMContentLoaded', init);
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
