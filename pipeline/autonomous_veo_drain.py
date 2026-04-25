"""Autonomous Veo queue drain — runs without supervision.

Loops until every pending bg/transition is delivered. Strategy:
  1. Try non-fast model (veo-3.0-generate-001) — independent quota bucket, fresh.
  2. If quota cap on non-fast on BOTH keys, sleep 5 min and try again.
  3. Once 00:00 PT passes (~next midnight Pacific = 09:00-10:00 IDT), the FAST
     bucket also unlocks; we keep using non-fast (better quality) but if
     non-fast hits a cap mid-run we retry with fast.
  4. Status file at pipeline/review/_autonomous_status.json updated every loop.
  5. Stops when no pending items.

Run with: python pipeline/autonomous_veo_drain.py &
Then: tail status from pipeline/review/_autonomous_status.json
"""
import sys
import os
import json
import time
import subprocess
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT = Path(r"C:\emerald")
STATUS = PROJECT / "pipeline" / "review" / "_autonomous_status.json"
LOG = PROJECT / "pipeline" / "review" / "_autonomous_drain.log"

PENDING_TRANSITIONS = ["T_M7", "T_M13", "T_M14"]
PENDING_BACKGROUNDS = ["bg_M9", "bg_M11", "bg_M12", "bg_06", "bg_07", "bg_01"]


def write_status(state: dict):
    state["_updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    STATUS.write_text(json.dumps(state, ensure_ascii=False, indent=2),
                      encoding="utf-8")


def log(msg: str):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def pending_now():
    """Return list of items still missing from assets/."""
    pending_t = [t for t in PENDING_TRANSITIONS
                 if not (PROJECT / "assets" / "transitions" / f"{t}.mp4").exists()]
    pending_b = [b for b in PENDING_BACKGROUNDS
                 if not (PROJECT / "assets" / "backgrounds" / f"{b}.mp4").exists()]
    return pending_t, pending_b


def run_script(script: str) -> tuple[int, str]:
    """Run a python script, return (returncode, last_lines_of_output)."""
    log(f"-> launch {script}")
    proc = subprocess.run(
        [sys.executable, str(PROJECT / "pipeline" / script)],
        cwd=str(PROJECT),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=3600,  # 1h hard cap per invocation
    )
    tail = "\n".join(proc.stdout.splitlines()[-15:])
    log(f"<- {script} rc={proc.returncode}")
    return proc.returncode, tail


def archive_failed_veo_outputs():
    """Copy any Veo videos sitting in candidate dirs (review/transitions/_candidates,
    review/backgrounds/_candidates) into a permanent archive — even if they failed
    QA. Sometimes failed videos are usable for B-roll, alt cuts, or reference.

    Source dirs:
      pipeline/review/transitions/_candidates/*.mp4
      pipeline/review/backgrounds/*.mp4 (anything not yet in assets/backgrounds/)

    Destination:
      pipeline/review/_veo_archive/<source_dir>/<filename>
    """
    import shutil
    archive = PROJECT / "pipeline" / "review" / "_veo_archive"
    archive.mkdir(parents=True, exist_ok=True)

    sources = [
        PROJECT / "pipeline" / "review" / "transitions" / "_candidates",
        PROJECT / "pipeline" / "review" / "backgrounds",
    ]
    delivered_b = {p.name for p in (PROJECT / "assets" / "backgrounds").glob("*.mp4")}
    delivered_t = {p.name for p in (PROJECT / "assets" / "transitions").glob("*.mp4")}

    archived = 0
    for src in sources:
        if not src.exists():
            continue
        sub = archive / src.name
        sub.mkdir(parents=True, exist_ok=True)
        for mp4 in src.glob("*.mp4"):
            # don't archive if already delivered (it's already in assets/)
            if mp4.name in delivered_b or mp4.name in delivered_t:
                continue
            dst = sub / mp4.name
            if not dst.exists() or dst.stat().st_size != mp4.stat().st_size:
                shutil.copy2(mp4, dst)
                archived += 1
    if archived:
        log(f"archived {archived} non-delivered Veo videos to _veo_archive/")
    return archived


def set_model(name: str):
    """Patch generate_backgrounds.VEO_MODEL by env override (we use a sentinel
    file because the constant is read at module import; simpler: edit the file
    only when switching is needed). For now: write through env var that the
    module checks if present."""
    # Implement by editing the file directly — Python doesn't reload modules.
    # We do the edit inline.
    bg_py = PROJECT / "pipeline" / "generate_backgrounds.py"
    txt = bg_py.read_text(encoding="utf-8")
    # Replace the VEO_MODEL = "..."  line, regardless of current value.
    import re
    new_txt = re.sub(
        r'VEO_MODEL = "veo-3\.0-(?:fast-)?generate-001"',
        f'VEO_MODEL = "{name}"',
        txt, count=1,
    )
    if new_txt != txt:
        bg_py.write_text(new_txt, encoding="utf-8")
        log(f"VEO_MODEL switched to {name}")


def main():
    LOG.write_text("", encoding="utf-8")  # reset log
    log("=" * 60)
    log("AUTONOMOUS VEO DRAIN started")
    log("=" * 60)

    cycle = 0
    last_progress_at = time.time()
    current_model = "veo-3.0-generate-001"
    set_model(current_model)

    while True:
        cycle += 1
        pt, pb = pending_now()
        state = {
            "cycle": cycle,
            "current_model": current_model,
            "pending_transitions": pt,
            "pending_backgrounds": pb,
            "total_pending": len(pt) + len(pb),
        }
        write_status(state)

        if not pt and not pb:
            log("ALL DELIVERED. shutting down autonomously.")
            state["status"] = "DONE"
            write_status(state)
            return

        log(f"cycle {cycle}: pending T={pt} B={pb} model={current_model}")

        # Try transitions first (smaller, faster wins)
        if pt:
            rc, tail = run_script("generate_transitions.py")
            if "exhausted" in tail.lower() or "RESOURCE_EXHAUSTED" in tail:
                log(f"transitions hit quota on {current_model}")
        # Then backgrounds
        if pb:
            rc, tail = run_script("generate_backgrounds.py")
            if "RESOURCE_EXHAUSTED" in tail:
                log(f"backgrounds hit quota on {current_model}")

        pt_after, pb_after = pending_now()
        delta = (len(pt) - len(pt_after)) + (len(pb) - len(pb_after))
        if delta > 0:
            log(f"progress: +{delta} delivered this cycle")
            last_progress_at = time.time()
        else:
            log(f"no progress this cycle. last progress {int(time.time()-last_progress_at)}s ago")

        # Decide whether to switch models or wait
        if not pt_after and not pb_after:
            continue  # next loop will detect DONE

        idle_for = time.time() - last_progress_at
        if idle_for > 600:  # 10 min no progress
            # Toggle to fast model (its quota may have reset by now)
            other = "veo-3.0-fast-generate-001" if current_model == "veo-3.0-generate-001" else "veo-3.0-generate-001"
            log(f"10 min no progress — toggle model {current_model} -> {other}")
            current_model = other
            set_model(current_model)
            last_progress_at = time.time()  # reset clock for new model
            time.sleep(30)
            continue

        # Sleep 3 min between cycles to avoid thrash
        log("sleeping 180s before next cycle")
        time.sleep(180)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("interrupted")
    except Exception as e:
        log(f"FATAL: {e}")
        import traceback
        log(traceback.format_exc())
        write_status({"status": "FATAL", "error": str(e)})
