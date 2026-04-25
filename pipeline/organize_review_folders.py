"""Move all _r*.png / _r*.mp4 / _r*_grid.png working candidates into a
_candidates/ subfolder, keeping only canonical files + logs at the top level
of pipeline/review/<type>/. Also rewrites tmp_path references in protocol
logs to match the new locations so audit trails stay valid.

Run once after a protocol pass to reduce visual clutter when Nirit browses
the review folder.
"""
import json
import re
import shutil
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
REVIEW = PROJECT / "pipeline" / "review"

MOVE_PATTERNS_BY_FOLDER = {
    "scenery": [re.compile(r"^[a-z_0-9]+_r\d+\.png$", re.I)],
    "backgrounds": [
        re.compile(r"^bg_\w+_r\d+\.mp4$", re.I),
        re.compile(r"^bg_\w+_r\d+_grid\.png$", re.I),
        re.compile(r"^bg_\w+_r\d+_frame_\d+\.png$", re.I),
        re.compile(r"^bg_\w+_r\d+_kf_t[\d.]+\.png$", re.I),
    ],
}


def organize_folder(subfolder):
    folder = REVIEW / subfolder
    if not folder.exists():
        print(f"[{subfolder}] folder does not exist -- skip")
        return
    dest = folder / "_candidates"
    dest.mkdir(exist_ok=True)

    patterns = MOVE_PATTERNS_BY_FOLDER.get(subfolder, [])
    moved = 0
    moved_paths = {}  # old_str -> new_str
    for f in folder.iterdir():
        if not f.is_file():
            continue
        if any(p.match(f.name) for p in patterns):
            new = dest / f.name
            shutil.move(str(f), str(new))
            moved_paths[str(f)] = str(new)
            moved += 1
    print(f"[{subfolder}] moved {moved} files to {dest.name}/")

    # Rewrite tmp_path / raw / grid references inside protocol log
    log_path = folder / "_protocol_log.json"
    if log_path.exists() and moved_paths:
        raw = log_path.read_text("utf-8")
        updated = raw
        for old, new in moved_paths.items():
            # Handle both forward and backslash variants (JSON-escaped)
            for variant in (old, old.replace("\\", "\\\\"),
                            old.replace("\\", "/")):
                updated = updated.replace(variant, new.replace("\\", "\\\\"))
        if updated != raw:
            log_path.write_text(updated, "utf-8")
            print(f"[{subfolder}] rewrote path references in _protocol_log.json")


def main():
    organize_folder("scenery")
    organize_folder("backgrounds")
    print("\ndone. top level of review/ now contains only canonical files + logs.")


if __name__ == "__main__":
    main()
