"""Cross-reference Q1/Q2/Q3 verdicts with the chroma-edge audit.

For each of the 52 props, we now know two things:
  A) Q1/Q2/Q3 verdict   : keep / merge_to_bg / move_to_sound / reuse_other / fix_frame / delete
  B) chroma audit       : CLEAN / MILD_HALO / FAKE_CLEAN / DIRTY / NO_CHROMA

Cross-reference logic:
  - merge_to_bg + ANY chroma   -> chroma irrelevant (goes into bg layer)
  - move_to_sound + ANY chroma -> chroma irrelevant (MP4 alpha loop replacement)
  - keep + CLEAN/MILD_HALO     -> ship as-is
  - keep + FAKE_CLEAN/DIRTY    -> NEEDS REPLACEMENT (route to Shutterstock isolated PNG search)
  - keep + NO_CHROMA           -> NEEDS REPLACEMENT
  - reuse_other + anything     -> drop, point to existing alt prop

Outputs C:\emerald\pipeline\review\asset_recovery_map.json — the master plan.
"""
import sys
import json
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT = Path(r"C:\emerald")
Q123 = PROJECT / "pipeline" / "review" / "scenery_audit_q123.json"
CHROMA = PROJECT / "pipeline" / "review" / "scenery_chroma_edges.json"
OLD = Path(r"C:\Users\azril\OneDrive\Desktop\fincail_game\old")
OUT = PROJECT / "pipeline" / "review" / "asset_recovery_map.json"

# Map move_to_sound props to existing animated MP4 loops in old/
SOUND_LOOP_MAP = {
    "scenery_bush_right":  "old/bg_extra_assets_video/bush_shaking_loop.mp4",
    "smoking_jeep":        "old/bg_extra_assets_video/engine_smoke_loop.mp4",
    "rain_effect":         "old/effects/rain_effect_loop.mp4",
    "rain_effect_m8":      "old/effects/rain_effect_loop.mp4",
    "fireworks":           None,   # Shutterstock animated/loop search
    "walkie_talkie":       None,   # Shutterstock isolated cutout
    "dust_clouds":         "old/bg_extra_assets_video/flare_smoke_loop.mp4",  # candidate
}

# Verify which loops actually exist
def loop_exists(rel):
    if rel is None:
        return False
    return (OLD / rel.replace("old/", "")).exists()


q123 = json.loads(Q123.read_text(encoding="utf-8"))
chroma = json.loads(CHROMA.read_text(encoding="utf-8"))

q_items = q123["items"]
c_items = chroma["items"]

all_slugs = sorted(set(q_items) | set(c_items))

plan = {}
buckets = {
    "ship_as_is":            [],
    "merge_to_bg":           [],
    "replace_with_mp4_loop": [],
    "needs_shutterstock":    [],
    "drop_use_other":        [],
    "needs_review":          [],
}

for slug in all_slugs:
    q = q_items.get(slug, {})
    c = c_items.get(slug, {})
    verdict = q.get("verdict", "_unknown")
    chroma_state = c.get("verdict", "_unknown")
    edge_lean = c.get("green_lean")

    entry = {
        "verdict_q123": verdict,
        "chroma_state": chroma_state,
        "green_lean": edge_lean,
    }

    # Decision tree
    if verdict == "merge_to_bg":
        action = "BAKE_INTO_BG"
        entry["next_step"] = "remove from active staging; bake into bg layer"
        buckets["merge_to_bg"].append(slug)

    elif verdict == "move_to_sound":
        loop = SOUND_LOOP_MAP.get(slug)
        if loop and loop_exists(loop):
            action = "REPLACE_WITH_MP4"
            entry["replacement"] = loop
            entry["next_step"] = f"replace static PNG with existing loop: {loop}"
            buckets["replace_with_mp4_loop"].append(slug)
        else:
            action = "NEEDS_LOOP_SOURCE"
            entry["next_step"] = "no existing loop in old/ — Shutterstock animated search"
            buckets["needs_shutterstock"].append(slug)

    elif verdict == "reuse_other":
        action = "USE_OTHER_PROP"
        entry["reuse_target"] = q.get("q3_reuse_other", {}).get("reuse_target")
        entry["next_step"] = f"drop this slug; use {entry['reuse_target']} instead"
        buckets["drop_use_other"].append(slug)

    elif verdict in ("keep", "fix_frame"):
        if chroma_state in ("CLEAN", "MILD_HALO"):
            action = "SHIP"
            entry["next_step"] = "ship as-is for demo"
            buckets["ship_as_is"].append(slug)
        elif chroma_state in ("FAKE_CLEAN", "DIRTY", "NO_CHROMA"):
            action = "SHUTTERSTOCK_REPLACE"
            entry["next_step"] = "Gemini chroma fakery — re-source via Shutterstock isolated PNG"
            buckets["needs_shutterstock"].append(slug)
        else:
            action = "REVIEW"
            entry["next_step"] = f"chroma state {chroma_state} — manual look"
            buckets["needs_review"].append(slug)

    elif verdict == "delete":
        action = "DELETE"
        entry["next_step"] = "remove from staging"
        buckets["drop_use_other"].append(slug)

    else:
        action = "REVIEW"
        entry["next_step"] = f"unknown q123 verdict: {verdict}"
        buckets["needs_review"].append(slug)

    entry["action"] = action
    plan[slug] = entry

# Print summary
print("=" * 70)
print("ASSET RECOVERY MAP — 52 scenery props")
print("=" * 70)
for bucket, slugs in buckets.items():
    print(f"\n{bucket}  ({len(slugs)}):")
    for s in slugs:
        e = plan[s]
        extra = ""
        if "replacement" in e:
            extra = f"  -> {e['replacement']}"
        if "reuse_target" in e:
            extra = f"  -> {e['reuse_target']}"
        print(f"  - {s:<35}  q123={e['verdict_q123']:<14} "
              f"chroma={e['chroma_state']:<10}{extra}")

print("\n" + "=" * 70)
print("HEADLINE NUMBERS:")
print(f"  ship as-is (no work)        : {len(buckets['ship_as_is']):>3}")
print(f"  bake into bg (no work)      : {len(buckets['merge_to_bg']):>3}")
print(f"  swap to existing MP4 loop   : {len(buckets['replace_with_mp4_loop']):>3}")
print(f"  drop / use other prop       : {len(buckets['drop_use_other']):>3}")
print(f"  NEEDS new asset (Shutterstock): {len(buckets['needs_shutterstock']):>3}")
print(f"  manual review               : {len(buckets['needs_review']):>3}")
print("=" * 70)

out = {
    "_built_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    "_purpose": "Cross-reference Q1/Q2/Q3 verdicts + chroma edge audit -> demo-ready action plan",
    "_summary": {k: len(v) for k, v in buckets.items()},
    "_buckets": buckets,
    "items": plan,
}
OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\nsaved -> {OUT}")
