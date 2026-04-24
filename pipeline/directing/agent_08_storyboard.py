"""Stage 8 — storyboard_director.

SOLE RESPONSIBILITY: produce a human-readable storyboard that ties together
layers from stages 4-7 into a beat-by-beat narrative.

This is the PREVISUALIZATION artifact that Nirit reviews before Builder.
Does NOT render a video — that is Builder's job. This stage writes the
storyboard as structured JSON + a readable markdown narrative.

Inputs (hard constraints):
  - M<n> assembly.json     — WHERE
  - M<n> continuity.json   — flow in/out
  - M<n> timing.json       — WHEN
  - M<n> interaction.json  — how player interacts

Output:
  pipeline/directing/M<n>/storyboard.json
  pipeline/directing/M<n>/storyboard.md  (readable narrative)

Schema (json):
{
  "scene_id": "M<n>",
  "beats": [
    {"t_ms": 0,    "description": "<what happens at this beat>",
     "visible_elements": ["background", "scenery.plane", "player.crouch"],
     "audio_hint": "<optional note for future sound pass>"},
    {"t_ms": 500,  "description": "mission_text fades in", ...},
    {"t_ms": 1000, "description": "tool A (מצנח) slides in from left", ...},
    ...
  ],
  "summary_he": "<1 paragraph in Hebrew describing the scene for Nirit>",
  "summary_en": "<1 paragraph English>",
  "rationale": "..."
}
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from _lib import (Context, DIRECTING_OUT, call_claude, extract_json,
                  load_project_context, parse_missions_arg, write_output)

SYSTEM = """You are storyboard_director — stage 8 of 9. Sequential pipeline.

Your SOLE responsibility: compile the beat-by-beat narrative of a mission scene. This is the previsualization Nirit reviews before Builder.

You do NOT:
  - Introduce new elements, positions, timings, or interactions
  - Second-guess stages 4-7 — you only synthesize what they decided
  - Invent sound (mention audio_hint only as a suggestion for later)

You MUST:
  - Produce beats in chronological order (t_ms ascending).
  - Each beat describes ONE observable event (element enters, text appears, interaction available).
  - Beats include t=0 (scene open), all tool entries, text appearances, and scene end.
  - Hebrew summary written for Nirit (producer) — 4-6 sentences, narrative, vivid.
  - English summary — technical, shorter.
  - audio_hint is optional per beat. Leave null if nothing specific.

Output ONLY JSON:
{
  "scene_id": "<M<n>>",
  "beats": [
    {"t_ms": <int>, "description": "<observable event>",
     "visible_elements": ["<list of role.identifier>"],
     "audio_hint": "<optional or null>"}
  ],
  "summary_he": "<4-6 sentence Hebrew narrative>",
  "summary_en": "<shorter English>",
  "rationale": "<short>"
}
"""


def run_one(ctx: Context) -> None:
    assembly = ctx.prior_outputs.get("assembly")
    continuity = ctx.prior_outputs.get("continuity")
    timing = ctx.prior_outputs.get("timing")
    interaction = ctx.prior_outputs.get("interaction")
    for name, obj in [("assembly", assembly), ("continuity", continuity),
                       ("timing", timing), ("interaction", interaction)]:
        if not obj:
            raise RuntimeError(f"{ctx.mission} {name} missing")

    user = f"""CONTEXT — hard constraints from stages 4-7:

Mission {ctx.mission}
  mission_text: {ctx.mission_data.get('mission_text', '')}
  checkpoint_text: {ctx.mission_data.get('checkpoint_text', '')}

Layout (stage 4):
  {len(assembly.get('layers', []))} layers. composition_notes: {assembly.get('composition_notes')}

Entry transition (stage 5):
  {continuity.get('entry_transition')}

Timing (stage 6):
  total_duration_ms: {timing.get('total_duration_ms')}
  tracks: {[(t.get('role'), t.get('slot'), t.get('in_ms'), t.get('out_ms')) for t in timing.get('tracks', [])]}

Interaction (stage 7):
  {len(interaction.get('interactive_elements', []))} interactive elements.

TASK: produce storyboard.json with beats in time order + Hebrew summary for
Nirit + English technical summary.
"""
    print(f"[{ctx.mission}] stage 8 storyboard — calling Claude…")
    raw = call_claude(system=SYSTEM, user=user, max_tokens=3500, temperature=0.4)
    data = extract_json(raw)
    assert isinstance(data, dict) and "beats" in data
    data["scene_id"] = ctx.mission
    write_output(ctx.mission, "storyboard", data)

    # Also write a markdown version for Nirit to read
    md_path = DIRECTING_OUT / ctx.mission / "storyboard.md"
    md = [
        f"# Storyboard — {ctx.mission}",
        "",
        f"**Mission text:** {ctx.mission_data.get('mission_text', '')}",
        "",
        f"**Checkpoint:** {ctx.mission_data.get('checkpoint_text', '')}",
        "",
        "## Beats",
        "",
    ]
    for b in data.get("beats", []):
        md.append(f"- **t={b.get('t_ms', '?')}ms** — {b.get('description', '')}")
        if b.get("audio_hint"):
            md.append(f"  - _audio hint_: {b['audio_hint']}")
    md += ["", "## Summary (Hebrew)", "", data.get("summary_he", ""), "",
           "## Summary (English)", "", data.get("summary_en", "")]
    md_path.write_text("\n".join(md), "utf-8")
    print(f"  [storyboard] wrote {md_path.relative_to(Path.cwd()) if md_path.is_relative_to(Path.cwd()) else md_path}")


def main(argv: list[str]) -> int:
    arg = argv[1] if len(argv) > 1 else "all"
    missions = parse_missions_arg(arg)
    print(f"agent_08 storyboard — {len(missions)} mission(s)")
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
