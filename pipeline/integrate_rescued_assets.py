"""Integrate the 13 PASS+MILD rescued cutouts into assets/scenery/.

For each slug:
  1) backup current assets/scenery/<slug>.png to _v3_backup/<slug>.png
  2) copy pipeline/review/_for_nirit/<slug>.png -> assets/scenery/<slug>.png
  3) record in integration log

Updates pipeline/review/asset_recovery_map.json:
  for each integrated slug: chroma_state -> "RESCUED_CLEAN" or "RESCUED_MILD"
                            action -> "SHIP"
                            integrated_at -> timestamp
"""
import sys
import json
import time
import shutil
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT = Path(r"C:\emerald")
SCENERY = PROJECT / "assets" / "scenery"
BACKUP = SCENERY / "_v3_backup"
BACKUP.mkdir(parents=True, exist_ok=True)
FOR_NIRIT = PROJECT / "pipeline" / "review" / "_for_nirit"
RECOVERY_PATH = PROJECT / "pipeline" / "review" / "asset_recovery_map.json"
REVIEW_PATH = PROJECT / "pipeline" / "review" / "rescued_review.json"

review = json.loads(REVIEW_PATH.read_text(encoding="utf-8"))
recovery = json.loads(RECOVERY_PATH.read_text(encoding="utf-8"))

now = time.strftime("%Y-%m-%d %H:%M:%S")
integration_log = {"_run_at": now, "items": {}}

print("=" * 70)
print("INTEGRATING rescued cutouts -> assets/scenery/")
print("=" * 70)

count_pass = 0
count_mild = 0
for slug, info in review["items"].items():
    v = info["review"].get("verdict", "?")
    if v not in ("PASS", "MILD"):
        continue
    src = FOR_NIRIT / f"{slug}.png"
    dst = SCENERY / f"{slug}.png"
    if not src.exists():
        print(f"  MISSING source: {src}")
        continue

    # backup current
    backup_done = False
    if dst.exists():
        backup_dst = BACKUP / f"{slug}.png"
        if not backup_dst.exists():
            shutil.copy2(dst, backup_dst)
            backup_done = True

    # integrate
    shutil.copy2(src, dst)
    if v == "PASS":
        count_pass += 1
    else:
        count_mild += 1

    integration_log["items"][slug] = {
        "verdict": v,
        "source": str(src),
        "destination": str(dst),
        "backup_made": backup_done,
        "round": info.get("final_round", "r1"),
    }

    # update recovery map
    rec = recovery["items"].get(slug, {})
    rec["chroma_state"] = f"RESCUED_{v}"
    rec["action"] = "SHIP"
    rec["next_step"] = f"integrated as cutout from rescue ({info.get('final_round','r1')})"
    rec["integrated_at"] = now
    recovery["items"][slug] = rec

    print(f"  [{v:<4}]  {slug:<35}  -> {dst.name}")

print()
print("=" * 70)
print(f"INTEGRATED: {count_pass} PASS + {count_mild} MILD = {count_pass + count_mild} total")
print(f"Backups in: {BACKUP}")
print("=" * 70)

# Write logs
(PROJECT / "pipeline" / "review" / "integration_log.json").write_text(
    json.dumps(integration_log, ensure_ascii=False, indent=2), encoding="utf-8"
)

# Update recovery summary
buckets = recovery.setdefault("_buckets", {})
ship = buckets.setdefault("ship_as_is", [])
ss = buckets.setdefault("needs_shutterstock", [])
for slug in integration_log["items"]:
    if slug in ss:
        ss.remove(slug)
    if slug not in ship:
        ship.append(slug)
ship.sort()
recovery["_summary"]["ship_as_is"] = len(ship)
recovery["_summary"]["needs_shutterstock"] = len(ss)
recovery.setdefault("_decisions_log", []).append({
    "date": now,
    "decision": (f"Integrated {count_pass} PASS + {count_mild} MILD rescued cutouts "
                 "via subject_extractor (rembg + hard-edge chroma + human_review QA gate). "
                 "0 items remain on Shutterstock list."),
})
RECOVERY_PATH.write_text(json.dumps(recovery, ensure_ascii=False, indent=2), encoding="utf-8")

print(f"\nrecovery map updated.")
print(f"  ship_as_is now: {recovery['_summary']['ship_as_is']}")
print(f"  needs_shutterstock now: {recovery['_summary']['needs_shutterstock']}")
