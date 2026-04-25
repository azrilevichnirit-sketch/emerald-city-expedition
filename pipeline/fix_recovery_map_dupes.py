"""Quick cleanup of recovery map:
  - overgrown_path: was merge_to_bg, but rescue PASSED strict QA. -> ship_as_is
  - fresh_footprints_m8: appeared in BOTH drop_use_other AND builder_css. Keep only builder_css.
  - rebuild summary counts.
"""
import sys
import json
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT = Path(r"C:\emerald")
PATH = PROJECT / "pipeline" / "review" / "asset_recovery_map.json"
m = json.loads(PATH.read_text(encoding="utf-8"))

now = time.strftime("%Y-%m-%d %H:%M:%S")

# 1) overgrown_path: rescue passed strict QA -> move from merge_to_bg to ship_as_is
buckets = m.setdefault("_buckets", {})
mtb = buckets.setdefault("merge_to_bg", [])
ship = buckets.setdefault("ship_as_is", [])
if "overgrown_path" in mtb:
    mtb.remove("overgrown_path")
if "overgrown_path" not in ship:
    ship.append("overgrown_path")
    rec = m["items"].get("overgrown_path", {})
    rec["action"] = "SHIP"
    rec["next_step"] = "rescue passed strict 2nd-pass QA (subject_area=66%, slug_match=PASS)"
    m["items"]["overgrown_path"] = rec

# 2) fresh_footprints_m8: dedupe across drop_use_other and builder_css; keep builder_css
duo = buckets.setdefault("drop_use_other", [])
css = buckets.setdefault("builder_css", [])
if "fresh_footprints_m8" in duo:
    duo.remove("fresh_footprints_m8")
if "fresh_footprints_m8" not in css:
    css.append("fresh_footprints_m8")

# Sort all buckets
for k in buckets:
    buckets[k].sort()

# Rebuild summary
m["_summary"] = {
    "ship_as_is": len(ship),
    "merge_to_bg": len(mtb),
    "replace_with_mp4_loop": len(buckets.get("replace_with_mp4_loop", [])),
    "needs_shutterstock": len(buckets.get("needs_shutterstock", [])),
    "drop_use_other": len(duo),
    "needs_review": len(buckets.get("needs_review", [])),
    "needs_veo": len(buckets.get("needs_veo", [])),
    "builder_css": len(css),
}
m.setdefault("_decisions_log", []).append({
    "date": now,
    "decision": "Cleanup: overgrown_path moved to ship (rescue passed); fresh_footprints_m8 deduped (keep only builder_css).",
})
PATH.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
print("FIXED. Final summary:")
for k, v in m["_summary"].items():
    print(f"  {k:<22} {v}")
