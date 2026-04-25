"""Stage 7 — interaction_director.

SOLE RESPONSIBILITY: how does the PLAYER (the human child) interact with the
scene? Hover, click/tap, feedback on selection, points animation.

Inputs (hard constraints):
  - M<n> assembly.json  — tool positions, slot labels
  - M<n> timing.json    — when tools are visible (= when they're clickable)
  - content_lock tools  — label, points per slot

Output: pipeline/directing/M<n>/interaction.json
Schema:
{
  "scene_id": "M<n>",
  "interactive_elements": [
    {
      "slot": "A", "label": "מצנח עגול רחב", "points": 1,
      "hover": {"cursor": "pointer", "scale_factor": 1.08, "glow_color": "#FFE066"},
      "click": {
        "feedback_animation": "pulse_out", "feedback_ms": 500,
        "points_popup": {"text": "+1", "color": "#FFE066",
                         "from_xy_pct": {"x": 20, "y": 30},
                         "to_xy_pct": {"x": 50, "y": 20},
                         "duration_ms": 900}
      },
      "tooltip": {"he": "<short helper>", "show_after_ms": 800}
    },
    ...
  ],
  "global_ui": {
    "score_display": {"pos": {"x_pct": 90, "y_pct": 8}, "font_size_px": 42},
    "mission_text_box": {...},
    "checkpoint_text_box": {...}
  },
  "rationale": "..."
}

Rules:
  - Higher-point slot gets slightly bolder hover color
  - All tooltips in Hebrew (this is a Hebrew game)
  - Click feedback must be visible but brief (<600ms) so game flow continues
"""
from __future__ import annotations

import sys

from _lib import (Context, call_claude, extract_json, load_project_context, render_today_state,
                  parse_missions_arg, write_output)

SYSTEM = """You are interaction_director — stage 7 of 9. Sequential pipeline.

Your SOLE responsibility: how the human child interacts with the scene. Hover states, click feedback, points animation, tooltip copy.

You do NOT:
  - Change positions, times, or scene structure (stages 4, 5, 6 locked those)
  - Invent new interactive elements that don't exist in the assembly

You MUST:
  - For EACH of the 3 tool slots (A/B/C) define hover + click + tooltip.
  - Hover: pointer cursor, slight scale up (1.05-1.10), subtle glow.
  - Click: visible feedback <600ms. Points popup flies from tool → top-right score area.
  - Tooltip copy in Hebrew, short (<40 chars), explains what the tool does.
  - Higher-point tools get warmer/bolder accent colors (C > B > A).
  - Global UI: score display top-right, mission_text bottom or top, checkpoint bottom.

Output ONLY JSON:
{
  "scene_id": "<M<n>>",
  "interactive_elements": [
    {"slot": "A|B|C", "label": "<from content_lock>", "points": <int>,
     "hover": {"cursor": "pointer", "scale_factor": <float>, "glow_color": "<#hex>"},
     "click": {
       "feedback_animation": "<pulse_out|shake|flash|bounce>",
       "feedback_ms": <int>,
       "points_popup": {"text": "+<n>", "color": "<#hex>",
                         "from_xy_pct": {"x": <int>, "y": <int>},
                         "to_xy_pct": {"x": <int>, "y": <int>},
                         "duration_ms": <int>}
     },
     "tooltip": {"he": "<hebrew>", "show_after_ms": <int>}
    }
  ],
  "global_ui": {
    "score_display": {"pos": {"x_pct": <int>, "y_pct": <int>}, "font_size_px": <int>},
    "mission_text_box": {"pos": {"x_pct": <int>, "y_pct": <int>}, "width_pct": <int>, "font_size_px": <int>},
    "checkpoint_text_box": {"pos": {"x_pct": <int>, "y_pct": <int>}, "width_pct": <int>, "font_size_px": <int>}
  },
  "rationale": "<short>"
}
"""


def run_one(ctx: Context) -> None:
    assembly = ctx.prior_outputs.get("assembly")
    timing = ctx.prior_outputs.get("timing")
    if not assembly:
        raise RuntimeError(f"{ctx.mission} assembly missing")
    if not timing:
        raise RuntimeError(f"{ctx.mission} timing missing")

    tools = ctx.mission_data.get("tools", [])
    tool_positions = {}
    for l in assembly.get("layers", []):
        if l.get("role") == "tool" and l.get("slot"):
            tool_positions[l["slot"]] = l.get("pos", {})

    user = f"""CONTEXT — hard constraints:

{render_today_state(ctx)}

Mission {ctx.mission}, tools (content_lock):
{[(t['slot'], t['label'], t['points']) for t in tools]}

Tool positions (from assembly, use as from_xy_pct base for points popup):
{tool_positions}

Tool visibility windows (from timing):
{[(t.get('slot'), t.get('in_ms'), t.get('out_ms')) for t in timing.get('tracks', []) if t.get('role') == 'tool']}

TASK: produce interaction.json with hover/click/tooltip for each of the 3 tool
slots, plus global_ui positions for score_display / mission_text_box /
checkpoint_text_box.
"""
    print(f"[{ctx.mission}] stage 7 interaction — calling Claude…")
    raw = call_claude(system=SYSTEM, user=user, max_tokens=2500, temperature=0.3)
    data = extract_json(raw)
    assert isinstance(data, dict) and "interactive_elements" in data
    data["scene_id"] = ctx.mission
    write_output(ctx.mission, "interaction", data)


def main(argv: list[str]) -> int:
    arg = argv[1] if len(argv) > 1 else "all"
    missions = parse_missions_arg(arg)
    print(f"agent_07 interaction — {len(missions)} mission(s)")
    failures = 0
    for m in missions:
        try:
            ctx = load_project_context(m)
            if not ctx.mission_data:
                print(f"  [{m}] SKIP")
                continue
            run_one(ctx)
        except Exception as e:
            failures += 1
            print(f"  [{m}] FAIL: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
