"""Stage 9 — harmony_auditor.

SOLE RESPONSIBILITY: cross-layer consistency check. This agent produces NO
content. It reports PASS or FAIL with specific pointers to which prior stage
agent must fix what.

Checks (non-exhaustive, the agent can flag others):
  - Every layer in assembly has a matching track in timing (or is explicitly static bg).
  - Every tool slot A/B/C in assembly has an interactive_element in interaction.
  - Tool in_ms in timing >= entry_transition_ms (tools don't appear during cut-in).
  - Total mission duration >= mission_text visible duration + checkpoint_text visible duration.
  - Storyboard beats time-range within [0, total_duration_ms].
  - Continuity entry_transition.duration_ms matches timing.entry_transition_ms.
  - No element positioned outside canvas (x_pct/y_pct within [0, 100] with anchor sanity).

Output: pipeline/directing/M<n>/harmony.json
Schema:
{
  "scene_id": "M<n>",
  "status": "PASS|FAIL",
  "checks_passed": [<list of check ids>],
  "checks_failed": [
    {"id": "tool_timing_before_transition",
     "description": "Tool A in_ms=300 but entry_transition_ms=500 — tool appears during cut-in",
     "responsible_stage": "timing",
     "required_fix": "Set tool A in_ms >= 500"}
  ],
  "summary": "..."
}
"""
from __future__ import annotations

import sys

from _lib import (Context, call_claude, extract_json, load_project_context,
                  parse_missions_arg, write_output)

SYSTEM = """You are harmony_auditor — stage 9 of 9. FINAL gate before Builder.

Your SOLE responsibility: verify that the 5 prior stages (assembly, continuity, timing, interaction, storyboard) for a mission are mutually consistent.

You do NOT:
  - Write new content
  - Suggest creative improvements
  - Give aesthetic opinions

You ONLY:
  - Check concrete cross-layer constraints
  - Mark PASS if all pass, FAIL if any fail
  - For each failure, name the RESPONSIBLE stage (assembly|continuity|timing|interaction|storyboard) and the REQUIRED FIX in one sentence

Consistency checks to run (not exhaustive — flag additional issues you see):

1. ASSEMBLY ↔ TIMING:
   - Every layer role/slot in assembly has at least one matching track in timing.
   - Tracks don't reference files not in assembly.

2. ASSEMBLY ↔ INTERACTION:
   - For each tool slot A/B/C in assembly layers, there's a matching interactive_element in interaction.

3. CONTINUITY ↔ TIMING:
   - timing.entry_transition_ms == continuity.entry_transition.duration_ms (exact match or within ±50ms).

4. TIMING internal:
   - background in_ms == 0, out_ms == total_duration_ms, loop=true.
   - All tool in_ms >= entry_transition_ms (tools don't appear during scene cut-in).
   - mission_text appears in first 30% of scene.
   - checkpoint_text appears in last 25% of scene.
   - total_duration_ms between 8000 and 18000.

5. STORYBOARD:
   - All beats t_ms within [0, total_duration_ms].
   - Beats cover scene open (t=0) and scene end.

6. ASSEMBLY positions:
   - All x_pct and y_pct within [0, 100] inclusive.

Output ONLY JSON:
{
  "scene_id": "<M<n>>",
  "status": "PASS|FAIL",
  "checks_passed": ["<id1>", "<id2>", ...],
  "checks_failed": [
    {"id": "<short_id>", "description": "<one sentence>",
     "responsible_stage": "assembly|continuity|timing|interaction|storyboard",
     "required_fix": "<one sentence>"}
  ],
  "summary": "<1-2 sentence overall>"
}
"""


def run_one(ctx: Context) -> None:
    needed = ("assembly", "continuity", "timing", "interaction", "storyboard")
    for s in needed:
        if s not in ctx.prior_outputs:
            raise RuntimeError(f"{ctx.mission} {s}.json missing")

    user = f"""CONTEXT — mission {ctx.mission}. Five prior-stage JSON documents follow.

=== ASSEMBLY ===
{dict_compact(ctx.prior_outputs['assembly'])}

=== CONTINUITY ===
{dict_compact(ctx.prior_outputs['continuity'])}

=== TIMING ===
{dict_compact(ctx.prior_outputs['timing'])}

=== INTERACTION ===
{dict_compact(ctx.prior_outputs['interaction'])}

=== STORYBOARD ===
{dict_compact(ctx.prior_outputs['storyboard'])}

TASK: run all consistency checks. Output JSON with PASS/FAIL verdict and any
failures pointing at the responsible stage.
"""
    print(f"[{ctx.mission}] stage 9 harmony — calling Claude…")
    raw = call_claude(system=SYSTEM, user=user, max_tokens=2500, temperature=0.1)
    data = extract_json(raw)
    assert isinstance(data, dict) and "status" in data
    data["scene_id"] = ctx.mission
    write_output(ctx.mission, "harmony", data)
    verdict = data.get("status", "?")
    failures = len(data.get("checks_failed", []))
    print(f"  [harmony] {verdict} ({failures} failure(s))")


def dict_compact(d: dict) -> str:
    """Render dict for Claude without wasting tokens on whitespace."""
    import json
    return json.dumps(d, ensure_ascii=False, separators=(",", ":"))[:6000]


def main(argv: list[str]) -> int:
    arg = argv[1] if len(argv) > 1 else "all"
    missions = parse_missions_arg(arg)
    print(f"agent_09 harmony — {len(missions)} mission(s)")
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
