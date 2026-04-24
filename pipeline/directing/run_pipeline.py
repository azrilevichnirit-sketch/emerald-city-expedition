"""Orchestrator — runs stages 4 -> 5 -> 6 -> 7 -> 8 -> 9 for each mission.

Sequential per Nirit's iron rule: each stage finishes before next starts.

Usage (CI):
  python pipeline/directing/run_pipeline.py all
  python pipeline/directing/run_pipeline.py M1,M2,M3
  python pipeline/directing/run_pipeline.py M1 --stages 4,5,6
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

STAGES = [
    (4, "assembly",    "agent_04_assembly.py"),
    (5, "continuity",  "agent_05_continuity.py"),
    (6, "timing",      "agent_06_timing.py"),
    (7, "interaction", "agent_07_interaction.py"),
    (8, "storyboard",  "agent_08_storyboard.py"),
    (9, "harmony",     "agent_09_harmony.py"),
]


def parse_stages(arg: str | None) -> list[int]:
    if not arg:
        return [s[0] for s in STAGES]
    return [int(x.strip()) for x in arg.split(",") if x.strip()]


def run_stage(stage_num: int, mission: str) -> int:
    script = next(s[2] for s in STAGES if s[0] == stage_num)
    cmd = [sys.executable, str(HERE / script), mission]
    print(f"\n>>> stage {stage_num} for {mission} <<<")
    r = subprocess.run(cmd, cwd=str(PROJECT))
    return r.returncode


def main(argv: list[str]) -> int:
    args = argv[1:]
    missions_arg = args[0] if args else "all"
    stages_arg = None
    if "--stages" in args:
        i = args.index("--stages")
        stages_arg = args[i + 1] if i + 1 < len(args) else None

    if missions_arg == "all":
        missions = [f"M{i}" for i in range(1, 16)]
    else:
        missions = [m.strip() for m in missions_arg.split(",") if m.strip()]

    stages = parse_stages(stages_arg)

    print("=" * 70)
    print(f"Directing Pipeline — missions={missions} stages={stages}")
    print("=" * 70)

    summary = {"started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "missions": {}}
    t0 = time.time()

    # Sequential per mission OR sequential per stage?
    # Nirit's architecture: each mission passes through 4->9 before next mission
    # starts, because continuity reads the PREVIOUS mission's outputs.
    for m in missions:
        m_summary = {"stages": {}}
        for stage_num in stages:
            stage_name = next(s[1] for s in STAGES if s[0] == stage_num)
            start = time.time()
            rc = run_stage(stage_num, m)
            m_summary["stages"][stage_name] = {
                "returncode": rc,
                "elapsed_sec": round(time.time() - start, 1),
            }
            if rc != 0:
                print(f"!! stage {stage_num} failed for {m}, continuing to next mission")
                break
        summary["missions"][m] = m_summary

    summary["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    summary["total_elapsed_sec"] = round(time.time() - t0, 1)

    log_path = PROJECT / "pipeline" / "directing" / "_run_log.json"
    log_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), "utf-8")

    print("\n" + "=" * 70)
    print(f"Pipeline done in {summary['total_elapsed_sec']}s. Log: {log_path.relative_to(PROJECT)}")

    # Exit non-zero if any mission had any stage fail
    any_fail = any(any(st.get("returncode") for st in ms["stages"].values())
                   for ms in summary["missions"].values())
    return 1 if any_fail else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
