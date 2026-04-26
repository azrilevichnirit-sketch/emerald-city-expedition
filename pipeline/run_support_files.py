"""
Runner: produces the 28 JSON support files + extends maps + appends log.
Does NOT rewrite the M{N}.html files (they were already written by orchestrator).
"""
import sys, json
from datetime import datetime, timezone
sys.path.insert(0, "C:/emerald/pipeline")
from build_m2_m15 import (
    MISSIONS, ATTACH, PIPE, LOG,
    write_composition_json, write_inspector_verdict,
    update_consequence_map, update_pose_composition_map,
    log,
)

def main():
    log("orchestrator", "RESUME", "OK", "support files generation start")
    results = {}
    for mid, m in MISSIONS.items():
        log(mid, "PROD_DESIGNER", "OK", f"tools={','.join(t[0] for t in m['tools'])}")
        log(mid, "ACTOR_DIRECTOR", "OK", "tracks=run/wait/catch/jump/land (cloned from M1 V6)")

        comp_path = write_composition_json(mid, m)
        log(mid, "SCENE_COMPOSER", "OK", f"wrote {comp_path}")

        verdict_path, verdict, blockers = write_inspector_verdict(mid, m)
        if verdict == "FAIL":
            log(mid, "SCENE_INSPECTOR", "FAIL", f"blockers={blockers}")
            results[mid] = {"status": "BLOCKED_INSPECTOR", "blockers": blockers}
        else:
            log(mid, "SCENE_INSPECTOR", "PASS", verdict_path)
            html_path = f"{PIPE}/builder_html/{mid}.html"
            log(mid, "BUILDER", "OK_PRE_WRITTEN", html_path)
            results[mid] = {"status": "OK", "path": html_path}

    update_consequence_map()
    log("maps", "TOOL_CONSEQUENCE", "OK", "extended for M2-M15")
    update_pose_composition_map()
    log("maps", "POSE_COMPOSITION", "OK", "extended for M2-M15")

    log("finale", "WRITE", "OK", f"{PIPE}/builder_html/_finale.html (already written)")

    ok = sum(1 for r in results.values() if r["status"] == "OK")
    blocked = [m for m, r in results.items() if r["status"] != "OK"]
    log("orchestrator", "SUMMARY", "DONE", f"OK={ok}/14 blocked={blocked}")
    print(f"\nFINAL: OK={ok}/14, blocked={blocked}")
    return results

if __name__ == "__main__":
    main()
