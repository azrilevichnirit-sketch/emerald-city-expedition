"""Parallel orchestrator — runs stages 4-9 across all missions in maximum parallelism.

Dependency graph PER MISSION:
    4 (assembly)
    └─> 5 (continuity)   [also needs M<n-1>.5 — cross-mission chain]
        └─> 6 (timing)
            └─> 7 (interaction)
                └─> 8 (storyboard) — needs 4,5,6,7 of same mission
                    └─> 9 (harmony) — needs 4,5,6,7,8 of same mission

Phases:
    A. Stage 4 in parallel for all 15 missions.
    B. Stage 5 sequential chain M1->M2->...->M15.
    C. Per-mission worker pool: each mission runs 6->7->8->9 sequentially;
       multiple missions run in parallel.

Concurrency cap: MAX_WORKERS workers (respect Claude API rate limits).
Skips stages whose output already exists.

Status file: pipeline/directing/_pipeline_status.json
Log file:    pipeline/directing/_pipeline.log
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent.parent
STATUS = HERE / "_pipeline_status.json"
LOG = HERE / "_pipeline.log"
MAX_WORKERS = 5

MISSIONS = [f"M{i}" for i in range(1, 16)]

STAGE_SCRIPT = {
    4: "agent_04_assembly.py",
    5: "agent_05_continuity.py",
    6: "agent_06_timing.py",
    7: "agent_07_interaction.py",
    8: "agent_08_storyboard.py",
    9: "agent_09_harmony.py",
}
STAGE_NAME = {4: "assembly", 5: "continuity", 6: "timing", 7: "interaction",
              8: "storyboard", 9: "harmony"}
PER_MISSION_CHAIN = [6, 7, 8, 9]


def log(msg: str):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def write_status(state: dict):
    state["_updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    STATUS.write_text(json.dumps(state, ensure_ascii=False, indent=2),
                      encoding="utf-8")


def already_done(mission: str, stage: int) -> bool:
    p = HERE / mission / f"{STAGE_NAME[stage]}.json"
    return p.exists() and p.stat().st_size > 100


def run_stage(mission: str, stage: int) -> tuple[str, int, int]:
    """Run a single stage for a single mission. Returns (mission, stage, rc).
    Considers it succeeded only if rc==0 AND output file exists."""
    script = STAGE_SCRIPT[stage]
    log(f"-> {mission} stage {stage} ({STAGE_NAME[stage]})")
    t0 = time.time()
    try:
        proc = subprocess.run(
            [sys.executable, str(HERE / script), mission],
            cwd=str(PROJECT),
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=300,
        )
        elapsed = int(time.time() - t0)
        rc = proc.returncode
        # Verify output exists — agents may print FAIL but still exit 0 (paranoia).
        if rc == 0 and not already_done(mission, stage):
            rc = 99
            log(f"<- {mission} stage {stage} rc=99 NO OUTPUT ({elapsed}s)")
            log(f"   stderr tail: {proc.stderr[-300:]}")
        else:
            log(f"<- {mission} stage {stage} rc={rc} ({elapsed}s)")
        return mission, stage, rc
    except subprocess.TimeoutExpired:
        log(f"!! {mission} stage {stage} TIMEOUT")
        return mission, stage, -1
    except Exception as e:
        log(f"!! {mission} stage {stage} EXC: {e}")
        return mission, stage, -2


def parallel_stage(stage: int, missions: list[str], state: dict) -> dict:
    """Run `stage` for missions in parallel. Skips already-done."""
    results: dict[str, int] = {}
    pending = [m for m in missions if not already_done(m, stage)]
    skipped = [m for m in missions if already_done(m, stage)]
    for m in skipped:
        results[m] = 0
        log(f"   {m} stage {stage} skip (already done)")
    if not pending:
        return results
    log(f"=== Stage {stage} ({STAGE_NAME[stage]}) parallel x{len(pending)} ===")
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        fut2m = {ex.submit(run_stage, m, stage): m for m in pending}
        for fut in as_completed(fut2m):
            m, s, rc = fut.result()
            results[m] = rc
            state.setdefault("stage_results", {}).setdefault(str(s), {})[m] = rc
            write_status(state)
    return results


def sequential_stage_5(state: dict) -> dict:
    """Stage 5 sequential chain M1 -> M15 (cross-mission dep)."""
    log(f"=== Stage 5 (continuity) sequential chain ===")
    results: dict[str, int] = {}
    for m in MISSIONS:
        if already_done(m, 5):
            results[m] = 0
            log(f"   {m} stage 5 skip (already done)")
            continue
        _, _, rc = run_stage(m, 5)
        results[m] = rc
        state.setdefault("stage_results", {}).setdefault("5", {})[m] = rc
        write_status(state)
    return results


def per_mission_chain(mission: str, stages: list[int], state: dict) -> dict:
    """Run a sequential chain of stages for one mission. Stops on first failure."""
    chain_results: dict[str, int] = {}
    for stage in stages:
        if already_done(mission, stage):
            log(f"   {mission} stage {stage} skip (already done)")
            chain_results[str(stage)] = 0
            continue
        _, _, rc = run_stage(mission, stage)
        chain_results[str(stage)] = rc
        state.setdefault("chain_results", {}).setdefault(mission, {})[str(stage)] = rc
        write_status(state)
        if rc != 0:
            log(f"!! {mission} chain BROKE at stage {stage} rc={rc}")
            break
    return chain_results


def main():
    LOG.write_text("", encoding="utf-8")
    log("=" * 60)
    log("DIRECTING PIPELINE — parallel orchestrator started")
    log(f"missions={MISSIONS} max_workers={MAX_WORKERS}")
    log("=" * 60)
    t0 = time.time()
    state = {"phase": "init", "stage_results": {}, "chain_results": {}}
    write_status(state)

    # Phase A
    state["phase"] = "A_stage4_parallel"; write_status(state)
    parallel_stage(4, MISSIONS, state)

    # Phase B (sequential chain)
    state["phase"] = "B_stage5_chain"; write_status(state)
    sequential_stage_5(state)

    # Phase C: per-mission chain 6->7->8->9 (parallel across missions)
    state["phase"] = "C_per_mission_chain_6_7_8_9"; write_status(state)
    log(f"=== Phase C: per-mission chain 6->7->8->9 (parallel x{MAX_WORKERS}) ===")
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        fut2m = {ex.submit(per_mission_chain, m, PER_MISSION_CHAIN, state): m
                 for m in MISSIONS}
        for fut in as_completed(fut2m):
            m = fut2m[fut]
            try:
                fut.result()
            except Exception as e:
                log(f"!! {m} chain crashed: {e}")

    # Summarize
    state["phase"] = "DONE"
    state["total_elapsed_sec"] = int(time.time() - t0)

    pass_count = 0; fail_count = 0
    per_mission_status = {}
    for m in MISSIONS:
        h = HERE / m / "harmony.json"
        if h.exists():
            try:
                d = json.loads(h.read_text("utf-8"))
                v = d.get("status", "?")
                per_mission_status[m] = v
                if v == "PASS":
                    pass_count += 1
                else:
                    fail_count += 1
            except Exception:
                fail_count += 1
                per_mission_status[m] = "PARSE_FAIL"
        else:
            per_mission_status[m] = "NO_HARMONY"
            fail_count += 1
    state["harmony_pass"] = pass_count
    state["harmony_fail"] = fail_count
    state["per_mission_status"] = per_mission_status
    write_status(state)
    log(f"DONE in {state['total_elapsed_sec']}s. harmony PASS={pass_count} FAIL={fail_count}")
    for m, v in per_mission_status.items():
        log(f"  {m}: {v}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("interrupted")
    except Exception as e:
        import traceback
        log(f"FATAL: {e}\n{traceback.format_exc()}")
        write_status({"phase": "FATAL", "error": str(e)})
