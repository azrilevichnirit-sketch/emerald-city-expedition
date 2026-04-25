"""materialize_builder_inputs — translate directing/M<n>/* into the file
layout Builder expects.

Builder spec (agents/builder.md) reads its inputs from:
  pipeline/scene_scripts/script_<ID>.json
  pipeline/scene_briefs/scene_<ID>.json
  pipeline/set_list_<ID>.json
  pipeline/sound_design_<ID>.json
  pipeline/pose_map.json
  pipeline/asset_manifest.json

Our directing pipeline (stages 4-9) produced harmony-passed JSONs in
pipeline/directing/M<n>/{assembly,continuity,timing,interaction,storyboard,
harmony}.json. This script consolidates those plus content_lock + delivery
manifest into the per-mission files Builder expects.

Run AFTER harmony PASS for each mission. Idempotent.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT = Path(__file__).resolve().parent.parent.parent  # C:\emerald
DIRECTING = PROJECT / "pipeline" / "directing"
BRIEFS = PROJECT / "pipeline" / "scene_briefs"
SCRIPTS = PROJECT / "pipeline" / "scene_scripts"
SETS = PROJECT / "pipeline"
SOUND = PROJECT / "pipeline"
for d in (BRIEFS, SCRIPTS):
    d.mkdir(parents=True, exist_ok=True)


def materialize_one(mission: str, content_lock: dict, pose_map: dict) -> dict:
    md = DIRECTING / mission
    if not (md / "harmony.json").exists():
        return {"mission": mission, "status": "no_harmony"}

    h = json.loads((md / "harmony.json").read_text("utf-8"))
    if h.get("status") != "PASS":
        return {"mission": mission, "status": f"harmony_{h.get('status')}"}

    assembly = json.loads((md / "assembly.json").read_text("utf-8"))
    continuity = json.loads((md / "continuity.json").read_text("utf-8"))
    timing = json.loads((md / "timing.json").read_text("utf-8"))
    interaction = json.loads((md / "interaction.json").read_text("utf-8"))
    storyboard = json.loads((md / "storyboard.json").read_text("utf-8"))

    mission_data = content_lock.get("missions", {}).get(mission, {})
    poses = pose_map.get("poses", {})

    # ── 1. SCRIPT (texts only, exactly from content_lock) ──
    script = {
        "_for_mission": mission,
        "_source": "content_lock.json",
        "mission_text": mission_data.get("mission_text", ""),
        "checkpoint_text": mission_data.get("checkpoint_text", ""),
        "checkpoint_label": mission_data.get("checkpoint_label", ""),
        "tools": [
            {
                "slot": t.get("slot"),
                "label": t.get("label"),
                "file": t.get("file"),
                "points": t.get("points"),
            }
            for t in mission_data.get("tools", [])
        ],
    }

    # ── 2. SET_LIST (props + positions from assembly) ──
    set_list = {
        "_for_mission": mission,
        "_source": "directing/assembly.json",
        "canvas": assembly.get("canvas", {"w": 1920, "h": 1080, "aspect": "16:9"}),
        "layers": assembly.get("layers", []),
        "composition_notes": assembly.get("composition_notes", ""),
    }

    # ── 3. SCENE_BRIEF (the directorial decisions) ──
    # Resolve the player pose (use timing's choice as authoritative)
    player_pose_file = None
    for tr in timing.get("tracks", []):
        if tr.get("role") == "player":
            f = tr.get("file") or tr.get("pose") or ""
            if f.endswith(".mp4"):
                player_pose_file = f.split("/")[-1]
            break
    if not player_pose_file:
        # fallback: assembly's player layer
        for L in assembly.get("layers", []):
            if L.get("role") == "player":
                f = L.get("file") or (L.get("pose_candidates", [None]) or [None])[0]
                if f and f.endswith(".mp4"):
                    player_pose_file = f.split("/")[-1]
                break

    pose_info = poses.get(player_pose_file, {}) if player_pose_file else {}

    scene_brief = {
        "_for_mission": mission,
        "_built_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "_source": "directing/{assembly,continuity,timing,interaction,storyboard}.json",
        "scene_id": mission,
        "duration_ms": timing.get("total_duration_ms"),
        "entry_transition": continuity.get("entry_transition"),
        "exit_transition": continuity.get("exit_transition"),
        "background": next(
            (L for L in assembly.get("layers", []) if L.get("role") == "background"),
            {},
        ),
        "player": {
            "pose_file": player_pose_file,
            "pose_semantic": pose_info.get("semantic_name") or pose_info.get("semantic"),
            "loop_segment_sec": pose_info.get("loop_segment"),
            "hold_frame_sec": pose_info.get("hold_frame"),
            "one_shot": pose_info.get("one_shot", False),
            "catch_pose": pose_info.get("catch_pose", False),
        },
        "tracks": timing.get("tracks", []),
        "interactive_elements": interaction.get("interactive_elements", []),
        "global_ui": interaction.get("global_ui", {}),
        "beats": storyboard.get("beats", []),
        "summary_he": storyboard.get("summary_he", ""),
        "summary_en": storyboard.get("summary_en", ""),
    }

    # ── 4. SOUND_DESIGN (audio hints from storyboard, no real audio yet) ──
    sound_design = {
        "_for_mission": mission,
        "_status": "PLACEHOLDER (sound pass not yet run)",
        "_source": "storyboard.beats[].audio_hint",
        "audio_cues": [
            {"t_ms": b.get("t_ms"), "hint": b.get("audio_hint")}
            for b in storyboard.get("beats", [])
            if b.get("audio_hint")
        ],
    }

    # ── Write files ──
    (SCRIPTS / f"script_{mission}.json").write_text(
        json.dumps(script, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (BRIEFS / f"scene_{mission}.json").write_text(
        json.dumps(scene_brief, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (PROJECT / "pipeline" / f"set_list_{mission}.json").write_text(
        json.dumps(set_list, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (PROJECT / "pipeline" / f"sound_design_{mission}.json").write_text(
        json.dumps(sound_design, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return {
        "mission": mission,
        "status": "materialized",
        "files": [
            f"pipeline/scene_scripts/script_{mission}.json",
            f"pipeline/scene_briefs/scene_{mission}.json",
            f"pipeline/set_list_{mission}.json",
            f"pipeline/sound_design_{mission}.json",
        ],
        "pose_chosen": player_pose_file,
    }


def main(argv: list[str]) -> int:
    arg = argv[1] if len(argv) > 1 else "all"
    if arg == "all":
        missions = [f"M{i}" for i in range(1, 16)]
    else:
        missions = [m.strip() for m in arg.split(",") if m.strip()]

    cl = json.loads((PROJECT / "content_lock.json").read_text("utf-8"))
    pm = json.loads((PROJECT / "pipeline" / "pose_map.json").read_text("utf-8"))

    print(f"materializing builder inputs for {len(missions)} mission(s)...")
    results = []
    for m in missions:
        try:
            r = materialize_one(m, cl, pm)
        except Exception as e:
            r = {"mission": m, "status": "ERROR", "error": f"{type(e).__name__}: {e}"}
        results.append(r)
        print(f"  {r['mission']}: {r['status']}"
              + (f"  pose={r.get('pose_chosen')}" if r.get("pose_chosen") else ""))

    summary = {
        "_built_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "results": results,
        "summary": {
            "materialized": sum(1 for r in results if r["status"] == "materialized"),
            "skipped": sum(1 for r in results if r["status"] != "materialized"),
        },
    }
    (PROJECT / "pipeline" / "_builder_inputs_index.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nindex: pipeline/_builder_inputs_index.json")
    print(f"materialized: {summary['summary']['materialized']}/15")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
