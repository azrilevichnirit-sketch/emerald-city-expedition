"""Apply Nirit's decisions to the asset recovery map.

Decisions 2026-04-25:
  - fireworks      -> ship_as_is + builder-side CSS animation (chroma=CLEAN, fine)
  - walkie_talkie  -> ship_as_is, brief scene (receives, brings close, continues)

Both are removed from needs_shutterstock and added to ship_as_is with
a `builder_animation` note.
"""
import sys
import json
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PATH = Path(r"C:\emerald\pipeline\review\asset_recovery_map.json")

m = json.loads(PATH.read_text(encoding="utf-8"))

# Update individual items
m["items"]["fireworks"]["action"] = "SHIP"
m["items"]["fireworks"]["next_step"] = "ship as-is; builder adds CSS keyframe animation"
m["items"]["fireworks"]["builder_animation"] = "css_keyframes (burst/scale/opacity)"

m["items"]["walkie_talkie"]["action"] = "SHIP"
m["items"]["walkie_talkie"]["next_step"] = "ship as-is; brief scene (receive -> close -> continue)"
m["items"]["walkie_talkie"]["builder_animation"] = "css_translate_in (handoff only)"

# Move from needs_shutterstock to ship_as_is
ss = m["_buckets"]["needs_shutterstock"]
sa = m["_buckets"]["ship_as_is"]
for slug in ("fireworks", "walkie_talkie"):
    if slug in ss:
        ss.remove(slug)
    if slug not in sa:
        sa.append(slug)
sa.sort()

# Update summary counts
m["_summary"]["ship_as_is"] = len(sa)
m["_summary"]["needs_shutterstock"] = len(ss)

# Add a decisions log
m.setdefault("_decisions_log", []).append({
    "date": "2026-04-25",
    "decisions": [
        "fireworks -> ship_as_is + CSS animation in builder",
        "walkie_talkie -> ship_as_is, brief receive/close/continue scene",
    ],
})

PATH.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
print("UPDATED asset_recovery_map.json")
print(f"  ship_as_is now: {m['_summary']['ship_as_is']}")
print(f"  needs_shutterstock now: {m['_summary']['needs_shutterstock']}")
print(f"  remaining shutterstock list: {ss}")
