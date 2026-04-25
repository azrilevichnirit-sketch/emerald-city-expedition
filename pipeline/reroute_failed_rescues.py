"""Re-route the 9 rescue-failed scenery props out of needs_veo bucket.

Nirit clarified: Veo is for backgrounds + transitions ONLY — not for
individual scenery props. So the 9 failed rescues need a different home.

Routing logic:
  Environmental (sky/forest/water/rocks/distant figures) -> merge_to_bg
    These get baked into the mission's bg video by Veo.
    bg_M11 (waterfall+escape_boat+riverbank) absorbs:
      escape_boat_distant, churning_water_pool, river_shore_bank
    bg_M12 (twilight cave+rival boat) absorbs:
      rival_team_disappearing
    bg_M9 (subterranean keypad corridor) absorbs:
      (none of the failures map here)
    Generic missions absorb:
      darkening_sky, forest_far_side, jungle_trees

  Small interactive details (footprints) -> builder_css
    fresh_footprints_m8, wet_footprints_trail
    Builder animates with CSS in code; no asset needed.

Output:
  - asset_recovery_map.json updated:
      action -> "merge_to_bg" or "builder_css"
      empties needs_veo bucket
      adds to merge_to_bg or builder_css buckets
  - reroute_log.json with per-slug new disposition
"""
import sys
import json
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT = Path(r"C:\emerald")
RECOVERY_PATH = PROJECT / "pipeline" / "review" / "asset_recovery_map.json"
recovery = json.loads(RECOVERY_PATH.read_text(encoding="utf-8"))

now = time.strftime("%Y-%m-%d %H:%M:%S")

ROUTE = {
    # environmental -> bake into mission bg
    "darkening_sky":           ("merge_to_bg",   "absorbed by mission bg (sky element)"),
    "forest_far_side":         ("merge_to_bg",   "absorbed by mission bg (distant forest)"),
    "jungle_trees":            ("merge_to_bg",   "absorbed by mission bg (jungle backdrop)"),
    "river_shore_bank":        ("merge_to_bg",   "absorbed by bg_M11 (riverbank already in scene)"),
    "churning_water_pool":     ("merge_to_bg",   "absorbed by bg_M11 (waterfall already in scene)"),
    "escape_boat_distant":     ("merge_to_bg",   "absorbed by bg_M11 (escape boat already in scene)"),
    "rival_team_disappearing": ("merge_to_bg",   "absorbed by bg_M12 (cave entrance has team in scene)"),
    # small interactive details -> CSS
    "fresh_footprints_m8":     ("builder_css",   "M8 footprints animated via CSS in player layer"),
    "wet_footprints_trail":    ("builder_css",   "wet trail animated via CSS sequence in player layer"),
}

print("=" * 78)
print(f"RE-ROUTING {len(ROUTE)} rescue-failed props out of needs_veo")
print("=" * 78)

reroute_log = {"_run_at": now, "items": {}}

# Update items
for slug, (new_action, why) in ROUTE.items():
    rec = recovery["items"].get(slug, {})
    rec["action"] = new_action
    rec["next_step"] = why
    rec["rerouted_at"] = now
    recovery["items"][slug] = rec
    print(f"  {slug:<28}  -> {new_action:<14}  ({why[:55]})")
    reroute_log["items"][slug] = {"new_action": new_action, "reason": why}

# Update buckets
buckets = recovery.setdefault("_buckets", {})
needs_veo = buckets.setdefault("needs_veo", [])
merge_to_bg = buckets.setdefault("merge_to_bg", [])
builder_css = buckets.setdefault("builder_css", [])

for slug, (new_action, _) in ROUTE.items():
    if slug in needs_veo:
        needs_veo.remove(slug)
    if new_action == "merge_to_bg" and slug not in merge_to_bg:
        merge_to_bg.append(slug)
    elif new_action == "builder_css" and slug not in builder_css:
        builder_css.append(slug)

merge_to_bg.sort()
builder_css.sort()

recovery["_summary"]["needs_veo"] = len(needs_veo)
recovery["_summary"]["merge_to_bg"] = len(merge_to_bg)
recovery["_summary"]["builder_css"] = len(builder_css)

recovery.setdefault("_decisions_log", []).append({
    "date": now,
    "decision": (
        "Re-routed 9 rescue-failed props OUT of needs_veo. "
        "Per Nirit: Veo is for backgrounds + transitions only (short videos), "
        "not for individual scenery props. "
        f"merge_to_bg += 7 environmental: {', '.join(s for s, (a, _) in ROUTE.items() if a == 'merge_to_bg')}. "
        f"builder_css += 2 footprints: {', '.join(s for s, (a, _) in ROUTE.items() if a == 'builder_css')}."
    ),
})

RECOVERY_PATH.write_text(json.dumps(recovery, ensure_ascii=False, indent=2), encoding="utf-8")
(PROJECT / "pipeline" / "review" / "reroute_log.json").write_text(
    json.dumps(reroute_log, ensure_ascii=False, indent=2), encoding="utf-8"
)

print()
print("=" * 78)
print("RECOVERY MAP UPDATED:")
print(f"  ship_as_is:    {recovery['_summary'].get('ship_as_is', 0)}")
print(f"  merge_to_bg:   {recovery['_summary'].get('merge_to_bg', 0)}")
print(f"  builder_css:   {recovery['_summary'].get('builder_css', 0)}")
print(f"  mp4_loop:      {recovery['_summary'].get('replace_with_mp4_loop', 0)}")
print(f"  drop_use_other:{recovery['_summary'].get('drop_use_other', 0)}")
print(f"  needs_review:  {recovery['_summary'].get('needs_review', 0)}")
print(f"  needs_veo:     {recovery['_summary'].get('needs_veo', 0)}  (should be 0)")
print(f"  needs_shutterstock: {recovery['_summary'].get('needs_shutterstock', 0)}")
print("=" * 78)
