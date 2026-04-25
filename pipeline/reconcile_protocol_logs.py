"""Reconcile protocol logs with actual disk state.

The print-arrow bug (U+2192 crashing cp1252 stdout) masked many successful
write_bytes() calls as errors. Any file that exists on disk is delivered — so
re-stamp the log to match reality. Idempotent.
"""
import json
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
PROPS = PROJECT / "pipeline" / "debates" / "scenery" / "_props_structured.json"


def _prop_mission_map():
    if not PROPS.exists(): return {}
    return {p["slug"]: p["mission"] for p in json.loads(PROPS.read_text("utf-8"))}


def fix_log(log_path: Path, assets_dir: Path, ext: str, mission_map=None):
    if not log_path.exists():
        print(f"  no log at {log_path}")
        return
    log = json.loads(log_path.read_text("utf-8"))
    changed = 0
    mission_map = mission_map or {}
    for slug, entry in log.items():
        # backfill mission from external map when missing
        if not entry.get("mission") and slug in mission_map:
            entry["mission"] = mission_map[slug]
        asset = assets_dir / f"{slug}.{ext}"
        err = (entry.get("error") or "").lower()
        is_arrow_mask = "charmap" in err and "\\u2192" in err
        if asset.exists() and entry.get("status") != "delivered" and is_arrow_mask:
            entry["status"] = "delivered"
            entry["final_path"] = str(asset)
            entry.pop("error", None)
            entry["reconciled"] = "arrow-bug-masked-success"
            changed += 1
    log_path.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
    delivered = sum(1 for v in log.values() if v.get("status") == "delivered")
    print(f"  {log_path.name}: +{changed} reconciled. total delivered={delivered}/{len(log)}")


def main():
    fix_log(
        PROJECT / "pipeline" / "review" / "scenery" / "_protocol_log.json",
        PROJECT / "assets" / "scenery",
        "png",
        _prop_mission_map(),
    )
    fix_log(
        PROJECT / "pipeline" / "review" / "backgrounds" / "_protocol_log.json",
        PROJECT / "assets" / "backgrounds",
        "mp4",
    )


if __name__ == "__main__":
    main()
