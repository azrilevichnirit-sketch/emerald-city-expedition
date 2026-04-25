"""harmony_retry — re-runs the stages flagged by harmony_auditor for FAIL missions.

For each mission with harmony.status == FAIL:
  1. Read harmony.json checks_failed[]
  2. For each unique responsible_stage, build a feedback string
  3. Re-run that stage by writing a sidecar `_harmony_feedback.txt` the agent
     can pick up via context. The simplest path: delete the stale stage output
     and re-run, but this loses the feedback. Instead, we write the feedback
     to a sibling file the agent reads.

Approach used here: rather than touching agent code, we just delete the failing
stage outputs (and downstream stage outputs which depend on them), then re-run
the stages — relying on today_state.json being more authoritative now to
naturally produce a passing version.

Cap: 2 retry rounds per mission. After that, leave the FAIL standing for human
review.

Usage:
  python pipeline/directing/harmony_retry.py
  python pipeline/directing/harmony_retry.py M6,M8
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent.parent

STAGE_NAME = {4: "assembly", 5: "continuity", 6: "timing", 7: "interaction",
              8: "storyboard", 9: "harmony"}
STAGE_NUM = {v: k for k, v in STAGE_NAME.items()}
STAGE_SCRIPT = {
    "assembly": "agent_04_assembly.py",
    "continuity": "agent_05_continuity.py",
    "timing": "agent_06_timing.py",
    "interaction": "agent_07_interaction.py",
    "storyboard": "agent_08_storyboard.py",
    "harmony": "agent_09_harmony.py",
}
DOWNSTREAM = {
    "assembly":   ["assembly", "continuity", "timing", "interaction", "storyboard", "harmony"],
    "continuity": ["continuity", "timing", "interaction", "storyboard", "harmony"],
    "timing":     ["timing", "interaction", "storyboard", "harmony"],
    "interaction":["interaction", "storyboard", "harmony"],
    "storyboard": ["storyboard", "harmony"],
}


def find_fail_missions() -> list[str]:
    fails = []
    for m_dir in sorted(HERE.glob("M*")):
        h = m_dir / "harmony.json"
        if h.exists():
            try:
                d = json.loads(h.read_text("utf-8"))
                if d.get("status") == "FAIL":
                    fails.append(m_dir.name)
            except Exception:
                pass
    return fails


def write_feedback(mission: str, stage: str, fixes: list[str]) -> None:
    """Write feedback the agent can read via _lib (we'll add this)."""
    fb_path = HERE / mission / f"_harmony_feedback_{stage}.json"
    fb_path.parent.mkdir(parents=True, exist_ok=True)
    fb_path.write_text(json.dumps({
        "stage": stage,
        "feedback_round": 1,
        "fixes": fixes,
        "_written_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }, ensure_ascii=False, indent=2), encoding="utf-8")


def run_stage(mission: str, stage_name: str) -> int:
    script = STAGE_SCRIPT[stage_name]
    print(f"  -> {mission} stage {STAGE_NUM[stage_name]} ({stage_name})")
    proc = subprocess.run(
        [sys.executable, str(HERE / script), mission],
        cwd=str(PROJECT),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=240,
    )
    print(f"  <- rc={proc.returncode}")
    return proc.returncode


def retry_one(mission: str) -> str:
    """Returns final harmony status: PASS, FAIL, or ERROR."""
    h_path = HERE / mission / "harmony.json"
    if not h_path.exists():
        return "ERROR"
    h = json.loads(h_path.read_text("utf-8"))
    if h.get("status") != "FAIL":
        return h.get("status", "?")

    failures = h.get("checks_failed", [])
    # Group fixes by responsible stage
    stage_fixes: dict[str, list[str]] = {}
    for f in failures:
        rs = f.get("responsible_stage")
        if rs and rs in STAGE_SCRIPT:
            stage_fixes.setdefault(rs, []).append(
                f"- {f.get('description', '')}\n  fix: {f.get('required_fix', '')}"
            )

    if not stage_fixes:
        print(f"  {mission}: FAIL but no responsible_stage routing — leaving for human review")
        return "FAIL"

    # Find earliest stage to re-run (others downstream of it must follow)
    earliest = min(stage_fixes.keys(), key=lambda s: STAGE_NUM[s])
    print(f"  {mission}: earliest broken stage = {earliest}")
    print(f"  {mission}: {len(failures)} failures across stages "
           f"{[s for s in stage_fixes]}")

    # Write feedback for the earliest stage
    write_feedback(mission, earliest, stage_fixes[earliest])

    # Delete downstream stage outputs (forces regeneration)
    for s in DOWNSTREAM.get(earliest, []):
        sp = HERE / mission / f"{s}.json"
        if sp.exists():
            sp.unlink()

    # Re-run from earliest forward
    for s in DOWNSTREAM.get(earliest, []):
        rc = run_stage(mission, s)
        if rc != 0:
            return "ERROR"

    # Re-read harmony
    if h_path.exists():
        new_h = json.loads(h_path.read_text("utf-8"))
        return new_h.get("status", "?")
    return "ERROR"


def main(argv: list[str]) -> int:
    arg = argv[1] if len(argv) > 1 else "all"
    if arg == "all":
        missions = find_fail_missions()
    else:
        missions = [m.strip() for m in arg.split(",") if m.strip()]

    print(f"harmony_retry — {len(missions)} mission(s) to retry: {missions}")

    results: dict[str, str] = {}
    for m in missions:
        print(f"\n=== retry {m} ===")
        try:
            results[m] = retry_one(m)
        except Exception as e:
            print(f"  {m}: EXC {e}")
            results[m] = "ERROR"

    print("\n=== RETRY RESULTS ===")
    for m, v in results.items():
        print(f"  {m}: {v}")

    pass_now = sum(1 for v in results.values() if v == "PASS")
    print(f"\n{pass_now}/{len(results)} now PASS")

    log_path = HERE / "_harmony_retry_log.json"
    log_path.write_text(json.dumps({
        "_run_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "results": results,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"log: {log_path.relative_to(PROJECT)}")

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
