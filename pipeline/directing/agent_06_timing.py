"""Stage 6 — timing_director.

SOLE RESPONSIBILITY: when does each element appear / disappear / loop / hold?
How long is the mission? What are the pose cues and checkpoint text timing?

Inputs (hard constraints):
  - M<n> assembly.json     — layout (static WHERE)
  - M<n> continuity.json   — entry transition duration, mood pacing
  - pose_map.json          — loop/one_shot durations per pose

Output: pipeline/directing/M<n>/timing.json
Schema:
{
  "scene_id": "M<n>",
  "total_duration_ms": 12000,
  "entry_transition_ms": <from continuity>,
  "tracks": [
    {"role": "background", "file": "...", "in_ms": 0, "out_ms": 12000, "loop": true},
    {"role": "player", "pose": "anim_crouch", "in_ms": 500, "out_ms": 12000,
     "loop_segment_ms": [0, 8000]},
    {"role": "scenery", "file": "...", "in_ms": 0, "out_ms": 12000},
    {"role": "tool", "slot": "A", "in_ms": 1000, "out_ms": 12000,
     "appear_animation": "fade_in", "appear_ms": 300},
    {"role": "tool", "slot": "B", "in_ms": 1400, ...},
    {"role": "tool", "slot": "C", "in_ms": 1800, ...},
    {"role": "mission_text", "in_ms": 500, "out_ms": 4500, "fade_in_ms": 400},
    {"role": "checkpoint_text", "in_ms": 10000, "out_ms": 12000}
  ],
  "rationale": "..."
}

Rules:
  - Tools enter staggered by ~300-500ms so user can see each arriving
  - mission_text visible early (reading time)
  - checkpoint_text appears AFTER user-implied decision point
  - Typical mission duration 10-15s
"""
from __future__ import annotations

import sys

from _lib import (Context, call_claude, extract_json, load_project_context,
                  parse_missions_arg, write_output)

SYSTEM = """You are timing_director — stage 6 of 9. Sequential pipeline.

Your SOLE responsibility: the time axis of a mission. When each element enters, exits, loops, holds. Total mission duration.

You do NOT:
  - Change positions (stage 4 locked those)
  - Change transitions between scenes (stage 5 locked the entry transition duration)
  - Add sound cues (not your job)
  - Define hover/click interaction (stage 7)

You MUST:
  - Total mission duration 10-15 seconds unless the action clearly demands otherwise.
  - Background track starts at 0 and runs the full duration, loop=true (videos loop).
  - Player pose aligned to pose_map.json (respect loop_segment / one_shot from that file).
  - Tools enter staggered (~300-500ms apart), with a fade_in or slide_in animation (200-400ms).
  - mission_text visible for 3-5 seconds starting ~500ms after scene open.
  - checkpoint_text appears ~1.5-2.5 seconds before scene end (narrator wrap-up).
  - All in_ms / out_ms are absolute times in the scene (not deltas).
  - entry_transition_ms matches continuity.entry_transition.duration_ms.

Output ONLY JSON matching this schema:
{
  "scene_id": "<M<n>>",
  "total_duration_ms": <int>,
  "entry_transition_ms": <int>,
  "tracks": [
    {"role": "background|scenery|player|tool|mission_text|checkpoint_text|overlay",
     "file": "<optional>", "slot": "<A|B|C|null>", "pose": "<optional>",
     "in_ms": <int>, "out_ms": <int>,
     "loop": <bool>, "loop_segment_ms": [<s>, <e>],
     "appear_animation": "<fade_in|slide_left|slide_up|pop|null>",
     "appear_ms": <int>,
     "disappear_animation": "<fade_out|slide_out|null>",
     "disappear_ms": <int>
    }
  ],
  "rationale": "<short>"
}
"""


def run_one(ctx: Context) -> None:
    assembly = ctx.prior_outputs.get("assembly")
    continuity = ctx.prior_outputs.get("continuity")
    if not assembly:
        raise RuntimeError(f"{ctx.mission} assembly missing")
    if not continuity:
        raise RuntimeError(f"{ctx.mission} continuity missing")

    # Compact pose summaries
    poses_summary = {}
    for name, info in ctx.pose_map.get("poses", {}).items():
        poses_summary[info.get("semantic_name", name)] = {
            "duration_sec": info.get("duration_sec"),
            "loop_segment": info.get("loop_segment"),
            "one_shot": info.get("one_shot"),
            "hold_frame": info.get("hold_frame"),
        }

    layers_summary = [{
        "z": l.get("z"), "role": l.get("role"), "slot": l.get("slot"),
        "file": l.get("file"), "pose_candidates": l.get("pose_candidates"),
    } for l in assembly.get("layers", [])]

    user = f"""CONTEXT — hard constraints:

Mission {ctx.mission}
  mission_text: {ctx.mission_data.get('mission_text', '')}
  checkpoint_text: {ctx.mission_data.get('checkpoint_text', '')}

Layers placed by stage 4 (positions already fixed):
{layers_summary}

Entry transition from stage 5:
  type: {continuity.get('entry_transition', {{}}).get('type')}
  duration_ms: {continuity.get('entry_transition', {{}}).get('duration_ms')}

Available poses (name -> timing info):
{poses_summary}

TASK: produce timing.json. One track per layer (background, scenery items, player,
each tool A/B/C), plus mission_text track and checkpoint_text track.
"""
    print(f"[{ctx.mission}] stage 6 timing — calling Claude…")
    raw = call_claude(system=SYSTEM, user=user, max_tokens=3000, temperature=0.3)
    data = extract_json(raw)
    assert isinstance(data, dict) and "tracks" in data
    data["scene_id"] = ctx.mission
    write_output(ctx.mission, "timing", data)


def main(argv: list[str]) -> int:
    arg = argv[1] if len(argv) > 1 else "all"
    missions = parse_missions_arg(arg)
    print(f"agent_06 timing — {len(missions)} mission(s)")
    for m in missions:
        try:
            ctx = load_project_context(m)
            if not ctx.mission_data:
                print(f"  [{m}] SKIP")
                continue
            run_one(ctx)
        except Exception as e:
            print(f"  [{m}] FAIL: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
