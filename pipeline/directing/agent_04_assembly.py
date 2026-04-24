"""Stage 4 — scene_assembly_director.

SOLE RESPONSIBILITY: for mission M<n>, decide WHERE each visible element sits
on the frame. Layout only. No timing. No sound. No interaction logic.

Inputs (READ-ONLY constraints, not opinions to revisit):
  - content_lock.json[M<n>]     — mission_text, tools (A/B/C), checkpoint
  - asset_manifest.json         — what files exist
  - pose_map.json               — which player pose files are available
  - bg director brief            — 3-layer depth bg design (foreground/mid/bg)

Output: pipeline/directing/M<n>/assembly.json
Schema:
{
  "scene_id": "M1",
  "canvas": {"w": 1920, "h": 1080, "aspect": "16:9"},
  "layers": [
    {"z": 0, "role": "background", "file": "backgrounds/bg_M1.mp4",
     "fit": "cover", "anchor": "center"},
    {"z": 10, "role": "scenery", "file": "scenery/plane_fuselage.png",
     "pos": {"x_pct": 10, "y_pct": 55}, "scale": 0.6, "rot_deg": 0,
     "anchor": "bottom-left"},
    {"z": 20, "role": "player", "pose_candidates": ["anim_crouch", "anim_look_around"],
     "pos": {"x_pct": 50, "y_pct": 70}, "scale": 0.4, "anchor": "bottom-center"},
    {"z": 30, "role": "tool", "slot": "A", "file": "tools/מצנח_מ01.png",
     "pos": {"x_pct": 20, "y_pct": 30}, "scale": 0.2, "rot_deg": -5,
     "anchor": "center", "points": 1},
    ...
  ],
  "composition_notes": "...",
  "rationale": "..."
}

Positions as percentages (0-100) so composition is resolution-agnostic.
"""
from __future__ import annotations

import sys

from _lib import (Context, call_claude, extract_json, load_project_context,
                  parse_missions_arg, render_bg_brief_summary,
                  render_content_lock_mission, write_output)

SYSTEM = """You are scene_assembly_director — stage 4 of 9 in a sequential directing pipeline for a Hebrew children's financial-literacy game.

Your SOLE responsibility: decide the static LAYOUT of a mission scene. WHERE does each element sit on the frame. Nothing else.

You do NOT decide:
  - Timing (stage 6 handles that)
  - Sound (not your job)
  - Interaction / hover-click (stage 7)
  - Narrative transitions to adjacent scenes (stage 5)

You MUST:
  - Place the 3 tool icons (slots A/B/C) in a visually balanced triangle or row that matches the scene's dramatic tension.
  - Place scenery props to reinforce the 3-depth layers from the bg brief (foreground / midground / background).
  - Pick a player pose position that makes sense for the mission_text action (e.g. M1 = post-landing = crouch/look; M4 = crossing chasm = reaching forward).
  - Use z-index: 0=bg video, 10-19=scenery behind player, 20=player, 30-39=tools/UI, 40+=overlays.
  - Use percentages (0-100) for x/y. NEVER pixel values.
  - Tools must be READABLE — each at least 15% canvas width, non-overlapping.
  - Player faces into frame (not out of frame).
  - Canvas is 16:9 (1920×1080).

Output ONLY a JSON object matching this schema (no markdown, no prose):
{
  "scene_id": "<mission>",
  "canvas": {"w": 1920, "h": 1080, "aspect": "16:9"},
  "layers": [
    {"z": <int>, "role": "background|scenery|player|tool|overlay",
     "file": "<path or null>",
     "slot": "<A|B|C|null>",
     "pos": {"x_pct": <0-100>, "y_pct": <0-100>},
     "scale": <0.0-1.0>,
     "rot_deg": <int>,
     "anchor": "center|top-left|top-right|bottom-left|bottom-right|bottom-center|top-center",
     "fit": "cover|contain|null",
     "pose_candidates": [<pose_name>, ...]  // only for role=player
    }
  ],
  "composition_notes": "<1-3 sentences on why this layout>",
  "rationale": "<short explanation tying layout to mission_text drama>"
}
"""


def run_one(ctx: Context) -> None:
    user = f"""CONTEXT — read as hard constraints, don't revisit:

{render_content_lock_mission(ctx)}

{render_bg_brief_summary(ctx)}

Available player poses (pose_map.json keys):
{sorted(ctx.pose_map.get('poses', {}).keys())}

Asset manifest summary:
  backgrounds: {ctx.asset_manifest.get('summary', {}).get('backgrounds', '?')}
  tools: {ctx.asset_manifest.get('summary', {}).get('tools', '?')}
  scenery: {ctx.asset_manifest.get('summary', {}).get('scenery', '?')}

TASK: produce the assembly.json for mission {ctx.mission}.
"""
    print(f"[{ctx.mission}] stage 4 assembly — calling Claude…")
    raw = call_claude(system=SYSTEM, user=user, max_tokens=3000, temperature=0.4)
    data = extract_json(raw)
    # Validate minimal schema
    assert isinstance(data, dict), "assembly.json root must be object"
    assert "layers" in data and isinstance(data["layers"], list), \
        "assembly.json must have layers[]"
    data["scene_id"] = ctx.mission
    write_output(ctx.mission, "assembly", data)


def main(argv: list[str]) -> int:
    arg = argv[1] if len(argv) > 1 else "all"
    missions = parse_missions_arg(arg)
    print(f"agent_04 assembly — {len(missions)} mission(s): {missions}")
    for m in missions:
        try:
            ctx = load_project_context(m)
            if not ctx.mission_data:
                print(f"  [{m}] SKIP: no mission data in content_lock")
                continue
            run_one(ctx)
        except Exception as e:
            print(f"  [{m}] FAIL: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
