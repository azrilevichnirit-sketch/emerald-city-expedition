"""Snapshot today's decisions into pipeline/today_state.json so directing agents
4-9 (and line_producer) all see the SAME current truth without having to
re-derive it from multiple sources.

Sources read:
  - assets/backgrounds/*.mp4    -> delivered backgrounds
  - assets/transitions/*.mp4    -> delivered transitions
  - assets/scenery/*.png        -> active scenery (what's still staged)
  - pipeline/review/asset_recovery_map.json
  - pipeline/review/reroute_log.json (optional)

Output: pipeline/today_state.json
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT = Path(r"C:\emerald")
OUT = PROJECT / "pipeline" / "today_state.json"


def list_files(d: Path, ext: str) -> list[str]:
    if not d.exists():
        return []
    return sorted(p.name for p in d.glob(f"*{ext}"))


def main() -> int:
    recovery = json.loads(
        (PROJECT / "pipeline" / "review" / "asset_recovery_map.json").read_text("utf-8"))

    state = {
        "_built_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "_purpose": (
            "Single source of truth for directing agents 4-9 and line_producer. "
            "Reflects ALL decisions through 2026-04-25 morning: rescue QA, "
            "re-routing 9 rescue-failed props, Veo deliveries, recovery map cleanup."
        ),

        "delivered": {
            "backgrounds": list_files(PROJECT / "assets" / "backgrounds", ".mp4"),
            "transitions": list_files(PROJECT / "assets" / "transitions", ".mp4"),
            "tools": list_files(PROJECT / "assets" / "tools", ".png"),
            "scenery_active": list_files(PROJECT / "assets" / "scenery", ".png"),
            "rivals": list_files(PROJECT / "assets" / "rivals", ".png"),
            "player_poses": list_files(PROJECT / "assets" / "player", ".mp4")
                            + list_files(PROJECT / "assets" / "player", ".png"),
        },

        "still_pending_veo": {
            "transitions": [t for t in ["T_M14"]
                            if not (PROJECT / "assets" / "transitions" / f"{t}.mp4").exists()],
            "backgrounds": [b for b in []  # all bg delivered
                            if not (PROJECT / "assets" / "backgrounds" / f"{b}.mp4").exists()],
        },

        "scenery_disposition": {
            "ship_as_is": recovery["_buckets"].get("ship_as_is", []),
            "merge_to_bg": {
                "_note": ("These are NOT separate scenery layers. They are baked INTO "
                          "the mission bg video. Directors must NOT place them as "
                          "independent layers in assembly.json."),
                "items": recovery["_buckets"].get("merge_to_bg", []),
            },
            "replace_with_mp4_loop": {
                "_note": ("Replace static PNG with looping MP4. Place as scenery layer "
                          "but reference the .mp4 file."),
                "items": recovery["_buckets"].get("replace_with_mp4_loop", []),
            },
            "builder_css": {
                "_note": ("Animated by Builder via CSS in player layer. NO asset file. "
                          "Directors should reference these as CSS-driven elements "
                          "in interaction.json, not as scenery in assembly.json."),
                "items": recovery["_buckets"].get("builder_css", []),
            },
            "drop_use_other": {
                "_note": ("Skip entirely. Don't reference anywhere."),
                "items": recovery["_buckets"].get("drop_use_other", []),
            },
            "needs_review": {
                "_note": "Hold — Nirit reviews these later.",
                "items": recovery["_buckets"].get("needs_review", []),
            },
        },

        "summary_counts": recovery.get("_summary", {}),

        "decisions_today": [
            {
                "decision": "Strict 2nd-pass QA caught 9 false-positive rescues",
                "detail": ("Original rescue auto-QA had false positives. Added 3-test "
                           "strict gate: subject_area_pct + open-ended naming + "
                           "slug-match. 9 props reverted from active staging."),
                "outcome": ("9 props moved out of needs_veo into either merge_to_bg "
                            "(7 environmental: darkening_sky, forest_far_side, "
                            "jungle_trees, river_shore_bank, churning_water_pool, "
                            "escape_boat_distant, rival_team_disappearing) or "
                            "builder_css (2 footprints: fresh_footprints_m8, "
                            "wet_footprints_trail)."),
            },
            {
                "decision": "Veo scope clarified: bg + transitions only",
                "detail": ("Per Nirit: Veo is for SHORT VIDEOS (backgrounds + transitions) "
                           "ONLY. Not for individual scenery props."),
                "outcome": "needs_veo bucket emptied; props re-routed.",
            },
            {
                "decision": "Veo quota mystery solved",
                "detail": ("`veo-3.0-fast-generate-001` and `veo-3.0-generate-001` "
                           "have INDEPENDENT quota buckets. Switched to non-fast "
                           "model — works on both keys with KEY_A->KEY_B failover."),
                "outcome": ("All 6 backgrounds delivered (bg_M9, bg_M11, bg_M12, "
                            "bg_06, bg_07, bg_01). 2 of 3 transitions delivered "
                            "(T_M7, T_M13). T_M14 still pending — autonomous drain "
                            "is retrying."),
            },
            {
                "decision": "overgrown_path rescue passed strict QA",
                "detail": ("rescue passed subject_area=66%, slug_match=PASS — "
                           "moved from merge_to_bg to ship_as_is."),
                "outcome": "ship_as_is += overgrown_path.",
            },
        ],

        "rules_for_directors": [
            "Reference ONLY files in delivered.* — never reference props in merge_to_bg.items, drop_use_other.items, or builder_css.items as independent layers.",
            "For builder_css items (footprints) — reference them in interaction.json as CSS-animated overlays in player layer, not as separate assets.",
            "For replace_with_mp4_loop items (rain, bush, jeep) — reference the .mp4 path in assembly.json scenery layer.",
            "Backgrounds: each mission has bg_M<n>.mp4 OR bg_<NN>.mp4. Use the mission-specific one if it exists; fall back to generic bg_<NN>.mp4 only when no mission-specific bg exists.",
            "Transitions: T_M14 is not yet delivered — if your mission depends on T_M14, mark it tentatively and the harmony auditor will flag it.",
        ],
    }

    OUT.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {OUT}")
    print(f"  delivered backgrounds: {len(state['delivered']['backgrounds'])}")
    print(f"  delivered transitions: {len(state['delivered']['transitions'])}")
    print(f"  delivered tools:       {len(state['delivered']['tools'])}")
    print(f"  delivered scenery:     {len(state['delivered']['scenery_active'])}")
    print(f"  still_pending_veo:     {state['still_pending_veo']}")
    print(f"  decisions logged:      {len(state['decisions_today'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
