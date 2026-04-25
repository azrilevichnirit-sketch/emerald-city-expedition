"""Stage 5 — continuity_director.

SOLE RESPONSIBILITY: ensure mission M<n> flows smoothly from M<n-1> and leaves
a clean handoff for M<n+1>. Transitions, mood arcs, visual callbacks.

Inputs (hard constraints):
  - M<n> assembly.json (stage 4 output)      — layout decisions already locked
  - M<n-1> assembly.json + continuity.json   — what the prior scene ended on
  - content_lock M<n> checkpoint_text        — what narratively ends the scene
  - bg briefs for M<n-1>, M<n>               — mood context

Output: pipeline/directing/M<n>/continuity.json
Schema:
{
  "from_mission": "M0 or M<n-1>",
  "to_mission": "M<n>",
  "entry_transition": {"type": "cross_dissolve|cut|wipe_left|fade_from_white|...",
                         "duration_ms": 500, "notes": "..."},
  "exit_handoff": {"leaves_on": "<mood/visual/prop>",
                    "next_scene_should_open_with": "<suggestion>"},
  "mood_arc": "<1-2 sentences on mood progression>",
  "visual_callbacks": ["<element from M<n-1> that reappears>", ...],
  "rationale": "..."
}

For M1 there is no M0; entry_transition.type = "open_sequence".
"""
from __future__ import annotations

import sys

from _lib import (Context, call_claude, extract_json, load_project_context,
                  load_prior_mission_output, parse_missions_arg, prev_mission,
                  render_bg_brief_summary, render_content_lock_mission,
                  render_today_state, write_output)

SYSTEM = """You are continuity_director — stage 5 of 9. Sequential pipeline, not a debate.

Your SOLE responsibility: the flow from mission M<n-1> to M<n> and the handoff to M<n+1>. Nothing else.

You do NOT:
  - Change layouts (stage 4 already locked those)
  - Decide individual element timing (stage 6)
  - Invent new assets (you work with what's placed)

You MUST:
  - Specify a transition IN to this mission from the prior one (or "open_sequence" for M1).
  - Name the visual/emotional anchor this mission LEAVES on so the next mission can pick up.
  - Flag up to 3 visual callbacks (elements from prior mission that reappear, reinforcing continuity).
  - Keep transitions short (300-700ms typical), except for "open_sequence" (can be 1200ms intro).

Output ONLY JSON:
{
  "from_mission": "<M<n-1> or null>",
  "to_mission": "<M<n>>",
  "entry_transition": {"type": "<cross_dissolve|cut|wipe_left|wipe_right|fade_from_white|fade_from_black|push_up|open_sequence>",
                        "duration_ms": <int>,
                        "notes": "<short>"},
  "exit_handoff": {
    "leaves_on": "<what the mission ends on visually/emotionally>",
    "next_scene_should_open_with": "<hint for stage 5 of next mission>"
  },
  "mood_arc": "<1-2 sentences>",
  "visual_callbacks": ["<item1>", "<item2>"],
  "rationale": "<short>"
}
"""


def run_one(ctx: Context) -> None:
    prev = prev_mission(ctx.mission)
    prev_assembly = load_prior_mission_output(prev, "assembly") if prev else None
    prev_continuity = load_prior_mission_output(prev, "continuity") if prev else None

    my_assembly = ctx.prior_outputs.get("assembly")
    if not my_assembly:
        raise RuntimeError(
            f"{ctx.mission} assembly.json missing — run stage 4 first"
        )

    # Prior mission context (truncated)
    prev_summary = "(M1 — no prior mission; this is open_sequence)"
    if prev:
        prev_cl = ctx.content_lock.get("missions", {}).get(prev, {})
        prev_summary = f"""Prior mission {prev}:
  checkpoint_text: {prev_cl.get('checkpoint_text', '')}
  checkpoint_label: {prev_cl.get('checkpoint_label', '')}
  layers ending (from assembly): {len((prev_assembly or {}).get('layers', []))} layers
  prior continuity hints exit_handoff: {(prev_continuity or {}).get('exit_handoff', 'n/a')}
"""

    user = f"""CONTEXT — hard constraints:

{render_today_state(ctx)}

CURRENT MISSION:
{render_content_lock_mission(ctx)}
{render_bg_brief_summary(ctx)}

Layout locked by stage 4 (don't revisit):
  {len(my_assembly.get('layers', []))} layers placed.
  composition_notes: {my_assembly.get('composition_notes', '')}

PRIOR MISSION:
{prev_summary}

TASK: produce continuity.json linking prior → current mission, and preparing
the handoff for the next mission.
"""
    print(f"[{ctx.mission}] stage 5 continuity — calling Claude…")
    raw = call_claude(system=SYSTEM, user=user, max_tokens=1500, temperature=0.3)
    data = extract_json(raw)
    assert isinstance(data, dict)
    data["from_mission"] = prev
    data["to_mission"] = ctx.mission
    write_output(ctx.mission, "continuity", data)


def main(argv: list[str]) -> int:
    arg = argv[1] if len(argv) > 1 else "all"
    missions = parse_missions_arg(arg)
    print(f"agent_05 continuity — {len(missions)} mission(s)")
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
