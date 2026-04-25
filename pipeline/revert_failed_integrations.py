"""Revert the 9 false-positive integrations from _v3_backup/.

Strict 2nd-pass QA flagged 9 of the 13 integrated rescues as visually
unusable (slivers, fragments, isolated rocks, ambiguous blobs).

For each REVERT slug:
  1) move current assets/scenery/<slug>.png -> _failed_rescue/<slug>.png  (audit trail)
  2) restore _v3_backup/<slug>.png -> assets/scenery/<slug>.png
  3) update recovery map: chroma_state -> back to original (FAKE_CLEAN etc),
                          action -> "needs_veo" (re-generate via Veo),
                          rescue_failed_at -> timestamp,
                          rescue_failed_reason -> from strict_qa_pass2.json
  4) remove from _buckets.ship_as_is, add to _buckets.needs_veo
"""
import sys
import json
import time
import shutil
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT = Path(r"C:\emerald")
SCENERY = PROJECT / "assets" / "scenery"
V3_BACKUP = SCENERY / "_v3_backup"
FAILED_DIR = SCENERY / "_failed_rescue"
FAILED_DIR.mkdir(parents=True, exist_ok=True)

STRICT = json.loads((PROJECT / "pipeline" / "review" / "strict_qa_pass2.json")
                    .read_text(encoding="utf-8"))
RECOVERY_PATH = PROJECT / "pipeline" / "review" / "asset_recovery_map.json"
recovery = json.loads(RECOVERY_PATH.read_text(encoding="utf-8"))

now = time.strftime("%Y-%m-%d %H:%M:%S")
revert_slugs = STRICT.get("_revert", [])

print("=" * 78)
print(f"REVERTING {len(revert_slugs)} false-positive rescues")
print("=" * 78)

revert_log = {"_run_at": now, "items": {}}

for slug in revert_slugs:
    active = SCENERY / f"{slug}.png"
    backup = V3_BACKUP / f"{slug}.png"
    failed_dst = FAILED_DIR / f"{slug}.png"

    if not backup.exists():
        print(f"  MISSING backup: {slug}  (cannot revert)")
        revert_log["items"][slug] = {"status": "no_backup"}
        continue

    # 1) move current rescued -> _failed_rescue/
    if active.exists():
        shutil.move(str(active), str(failed_dst))

    # 2) restore from v3 backup
    shutil.copy2(backup, active)

    # 3) update recovery map for this slug
    rec = recovery["items"].get(slug, {})
    rec["chroma_state"] = "FAKE_CLEAN"  # back to original problem
    rec["action"] = "needs_veo"
    rec["next_step"] = "rescue_failed_strict_qa — generate via Veo (motion loop) or bake_into_bg"
    rec["rescue_failed_at"] = now
    rec["rescue_failed_reason"] = "; ".join(
        STRICT["items"].get(slug, {}).get("fail_reasons", [])
    )[:200]
    recovery["items"][slug] = rec

    print(f"  REVERTED  {slug:<35}  -> needs_veo")
    revert_log["items"][slug] = {
        "status": "reverted",
        "failed_copy_at": str(failed_dst),
        "fail_reasons": STRICT["items"].get(slug, {}).get("fail_reasons", []),
    }

# 4) update buckets
buckets = recovery.setdefault("_buckets", {})
ship = buckets.setdefault("ship_as_is", [])
needs_veo = buckets.setdefault("needs_veo", [])

for slug in revert_slugs:
    if slug in ship:
        ship.remove(slug)
    if slug not in needs_veo:
        needs_veo.append(slug)

ship.sort()
needs_veo.sort()
recovery["_summary"]["ship_as_is"] = len(ship)
recovery["_summary"]["needs_veo"] = len(needs_veo)

recovery.setdefault("_decisions_log", []).append({
    "date": now,
    "decision": (f"Reverted {len(revert_slugs)} rescued integrations after strict 2nd-pass QA "
                 f"(naming + slug_match tests + subject area %). "
                 f"Kept 4: {', '.join(STRICT.get('_keep', []))}. "
                 f"Routed {len(revert_slugs)} to needs_veo bucket."),
})

RECOVERY_PATH.write_text(json.dumps(recovery, ensure_ascii=False, indent=2), encoding="utf-8")
(PROJECT / "pipeline" / "review" / "revert_log.json").write_text(
    json.dumps(revert_log, ensure_ascii=False, indent=2), encoding="utf-8"
)

print()
print("=" * 78)
print("RECOVERY MAP UPDATED")
print(f"  ship_as_is now:    {recovery['_summary']['ship_as_is']}")
print(f"  needs_veo now:     {recovery['_summary'].get('needs_veo', 0)}")
print(f"  KEEP from rescue:  {len(STRICT.get('_keep', []))}  ({', '.join(STRICT.get('_keep', []))})")
print("=" * 78)
