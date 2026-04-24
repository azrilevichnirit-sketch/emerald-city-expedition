"""Cross-asset audit. For each mission M1..M15, report:
  - bg video(s) delivered through current protocol
  - scenery props delivered vs planned
  - pose video coverage

Output: pipeline/review/integrated_audit.json + terminal table.
"""
import json
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
BG_LOG = PROJECT / "pipeline" / "review" / "backgrounds" / "_protocol_log.json"
SC_LOG = PROJECT / "pipeline" / "review" / "scenery" / "_protocol_log.json"
PROPS_STRUCTURED = PROJECT / "pipeline" / "debates" / "scenery" / "_props_structured.json"
BG_SUMMARY = PROJECT / "pipeline" / "debates" / "backgrounds" / "_summary.json"
BG_MISSION_MAP = PROJECT / "pipeline" / "bg_mission_map.json"
POSE_MAP = PROJECT / "pipeline" / "pose_map.json"
ASSETS_BG = PROJECT / "assets" / "backgrounds"
ASSETS_SC = PROJECT / "assets" / "scenery"
ASSETS_POSE = PROJECT / "assets" / "player"
LOCK = json.loads((PROJECT / "content_lock.json").read_text("utf-8"))
OUT = PROJECT / "pipeline" / "review" / "integrated_audit.json"


def load(p, default):
    return json.loads(p.read_text("utf-8")) if p.exists() else default


def main():
    bg_log = load(BG_LOG, {})
    sc_log = load(SC_LOG, {})
    bg_summary_raw = load(BG_SUMMARY, {})
    bg_summary = bg_summary_raw.get("items", bg_summary_raw.get("by_bg", {}))
    if isinstance(bg_summary, list):
        bg_summary = {it.get("slug") or it.get("bg"): it for it in bg_summary if isinstance(it, dict)}
    props = load(PROPS_STRUCTURED, [])
    pose_map = load(POSE_MAP, {})

    bg_mmap = load(BG_MISSION_MAP, {}).get("map", {})
    bg_by_mission = {}
    # delivered via new protocol
    for slug, entry in bg_log.items():
        if entry.get("status") == "delivered":
            mid = entry.get("mission") or bg_mmap.get(slug)
            bg_by_mission.setdefault(mid, []).append(slug)
    # existing older passing bgs per canonical mission map
    pass_from_summary = set()
    for it in (bg_summary.values() if isinstance(bg_summary, dict) else []):
        if isinstance(it, dict) and it.get("decision") == "pass":
            pass_from_summary.add(it.get("slug"))
    for slug, mid in bg_mmap.items():
        if slug in bg_log and bg_log[slug].get("status") == "delivered":
            continue  # already counted
        if slug in pass_from_summary and (ASSETS_BG / f"{slug}.mp4").exists():
            bg_by_mission.setdefault(mid, []).append(slug)

    props_by_mission = {}
    for p in props:
        props_by_mission.setdefault(p["mission"], []).append(p["slug"])

    scenery_delivered_by_mission = {}
    for slug, entry in sc_log.items():
        if entry.get("status") == "delivered":
            mid = entry.get("mission")
            scenery_delivered_by_mission.setdefault(mid, []).append(slug)

    poses = pose_map.get("poses", {})
    pose_usage = {}
    for fname, p in poses.items():
        sem = p.get("semantic_name") or p.get("semantic") or fname
        for m in p.get("use_in", []):
            pose_usage.setdefault(m, []).append(sem)

    report = {}
    for mid in sorted(LOCK["missions"].keys(), key=lambda x: int(x[1:])):
        planned_props = props_by_mission.get(mid, [])
        delivered_props = scenery_delivered_by_mission.get(mid, [])
        report[mid] = {
            "mission_label": LOCK["missions"][mid].get("checkpoint_label", ""),
            "bg_delivered": bg_by_mission.get(mid, []),
            "scenery_planned": planned_props,
            "scenery_delivered": delivered_props,
            "scenery_missing": [s for s in planned_props if s not in delivered_props],
            "poses_used": pose_usage.get(mid, []),
        }

    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"audit saved: {OUT}\n")
    print(f"{'mission':<6} {'bg_ok':<6} {'scenery':<12} {'missing':<8} {'poses'}")
    print("-" * 70)
    total_missing = 0
    total_bg_ok = 0
    for mid, r in report.items():
        bg_ok = "Y" if r["bg_delivered"] else "N"
        if r["bg_delivered"]: total_bg_ok += 1
        sc = f"{len(r['scenery_delivered'])}/{len(r['scenery_planned'])}"
        miss = len(r["scenery_missing"])
        total_missing += miss
        poses = ",".join(r["poses_used"]) or "-"
        print(f"{mid:<6} {bg_ok:<6} {sc:<12} {miss:<8} {poses}")
    print("-" * 70)
    print(f"total: bg_covered_missions={total_bg_ok}/15  scenery_missing={total_missing}")


if __name__ == "__main__":
    main()
