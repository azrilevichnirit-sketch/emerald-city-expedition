"""Director-panel audit: does the existing bg pool cover M2, M11, M12?

For each pending mission (M2=storm/shelter, M11=cliff+waterfall escape,
M12=cave+rivals trail), the 3-director panel views a labelled contact sheet
of all 18 existing bg clips (one keyframe each) and votes:

  - "use_<slug>" -> mission can be served by an existing bg (specify which)
  - "missing"    -> no suitable bg; must be produced tomorrow alongside Veo regens

The panel works from the mission text in content_lock.json. Zero Veo calls.

Output: pipeline/review/backgrounds/_bg_coverage_audit.json
"""
import base64
import json
import subprocess
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# Windows cp1252 stdout crashes on Hebrew/special chars in print()
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from debate_runner import call_engine, call_gemini, load_project_context
from resolve_via_panel import _parse_json, ENGINES

PROJECT = Path(__file__).resolve().parent.parent
BG_DIR = PROJECT / "assets" / "backgrounds"
REVIEW_DIR = PROJECT / "pipeline" / "review" / "backgrounds"
OUT_PATH = REVIEW_DIR / "_bg_coverage_audit.json"
CONTACT_SHEET_PATH = REVIEW_DIR / "_bg_contact_sheet.png"

PENDING_MISSIONS = [f"M{i}" for i in range(1, 16)]  # all 15 missions

LOCK = json.loads((PROJECT / "content_lock.json").read_text("utf-8"))


def list_bg_files():
    files = sorted(BG_DIR.glob("bg_*.mp4"))
    return files


def extract_keyframe(mp4_path, out_png, t=1.0):
    """One representative keyframe per bg (halfway-ish through a short loop)."""
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-ss", str(t), "-i", str(mp4_path),
        "-vframes", "1", "-q:v", "2", str(out_png),
    ], check=True)


def build_contact_sheet(bg_files, out_png, tile=360, cols=6):
    """Labeled 6x3 grid of 18 keyframes."""
    kf_paths = []
    for mp4 in bg_files:
        kf = REVIEW_DIR / f"_kf_{mp4.stem}.png"
        if not kf.exists():
            extract_keyframe(mp4, kf)
        kf_paths.append((mp4.stem, kf))

    rows = (len(kf_paths) + cols - 1) // cols
    label_h = 28
    cell_h = tile + label_h
    sheet = Image.new("RGB", (tile * cols, cell_h * rows), "white")
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("arial.ttf", 18)
    except Exception:
        font = ImageFont.load_default()

    for idx, (slug, kf) in enumerate(kf_paths):
        r, c = divmod(idx, cols)
        x, y = c * tile, r * cell_h
        img = Image.open(kf).convert("RGB")
        img = img.resize((tile, tile))
        sheet.paste(img, (x, y))
        # label strip
        draw.rectangle([x, y + tile, x + tile, y + tile + label_h], fill="black")
        draw.text((x + 8, y + tile + 4), slug, fill="white", font=font)

    sheet.save(out_png, "PNG")
    return out_png


def vote_on_mission(engine, mission_id, sheet_b64, bg_slugs):
    m = LOCK["missions"][mission_id]
    system = (
        f"You are the Director of Studio Emerald, one of THREE independent directors.\n"
        f"We need to decide whether an EXISTING background clip can serve mission {mission_id}, "
        f"or whether a new one must be produced tomorrow.\n\n"
        f"Mission {mission_id} text (Hebrew): {m['mission_text']}\n"
        f"Checkpoint (mission end): {m['checkpoint_text']}\n\n"
        f"You are looking at a CONTACT SHEET with ONE keyframe from each of 18 existing "
        f"bg clips. Each tile is LABELED with its slug. Candidate slugs: {', '.join(bg_slugs)}.\n\n"
        f"Judge each tile on: does its visual location, mood, time-of-day, and "
        f"atmosphere plausibly serve this mission as an **ambient loop background** "
        f"(the player acts on top of it; UI/mission text overlaid separately)?\n\n"
        f"Rules:\n"
        f" - Prefer an existing bg if even ONE is close enough — saves Veo quota.\n"
        f" - A near-miss (wrong time of day, wrong hero element) is a REJECT, not a pick — "
        f"    don't compromise the narrative just to save quota.\n"
        f" - If nothing fits, say so clearly.\n\n"
        f"Return STRICT JSON:\n"
        f"{{\n"
        f"  \"verdict\": \"use_existing|missing\",\n"
        f"  \"pick\": \"<slug if use_existing else null>\",\n"
        f"  \"runner_up\": \"<second-best slug or null>\",\n"
        f"  \"reason\": \"<one sentence>\"\n"
        f"}}"
    )
    resp = call_engine(engine, system,
                       f"Which existing bg (if any) serves {mission_id}?",
                       image_b64=sheet_b64, max_tokens=400)
    return _parse_json(resp)


def qa_sanity(mission_id, sheet_b64, bg_slugs):
    """Gemini QA: lenient sanity check that panel picks are not absurd."""
    m = LOCK["missions"][mission_id]
    instr = (
        f"QA sanity check. Mission {mission_id}: {m['mission_text']}\n"
        f"Candidate slugs on contact sheet: {', '.join(bg_slugs)}.\n"
        f"Return STRICT JSON: "
        f"{{\"candidates_any_plausible\":\"yes|no\","
        f"\"best_candidate\":\"<slug or null>\","
        f"\"notes\":\"<one sentence>\"}}."
    )
    resp = call_gemini(instr, "Sanity-check the bg coverage question.",
                       image_b64=sheet_b64, max_tokens=350)
    return _parse_json(resp)


def main():
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    bg_files = list_bg_files()
    bg_slugs = [f.stem for f in bg_files]
    print(f"[audit_bg_coverage] {len(bg_files)} existing bg clips: {', '.join(bg_slugs)}")

    sheet = build_contact_sheet(bg_files, CONTACT_SHEET_PATH)
    print(f"[contact_sheet] {sheet.name}")
    sheet_b64 = base64.b64encode(sheet.read_bytes()).decode("ascii")

    # Resume from any prior partial run so we don't re-spend API quota on
    # missions already voted. Only re-audits missions missing from the file.
    results = {}
    if OUT_PATH.exists():
        try:
            results = json.loads(OUT_PATH.read_text("utf-8"))
            print(f"[resume] loaded {len(results)} prior mission results from {OUT_PATH.name}")
        except Exception:
            results = {}

    for mid in PENDING_MISSIONS:
        if mid in results and results[mid].get("decision"):
            print(f"\n=== mission {mid} === (skipped — already decided: "
                  f"{results[mid]['decision'].get('action')})")
            continue
        print(f"\n=== mission {mid} ===")
        qa = qa_sanity(mid, sheet_b64, bg_slugs)
        print(f"  QA: any_plausible={qa.get('candidates_any_plausible')} "
              f"best={qa.get('best_candidate')}")

        panel = {}
        for eng in ENGINES:
            try:
                panel[eng] = vote_on_mission(eng, mid, sheet_b64, bg_slugs)
            except Exception as e:
                panel[eng] = {"verdict": "missing", "pick": None,
                              "reason": f"engine error: {e}"}
            v = panel[eng]
            print(f"  {eng}: {v.get('verdict')} pick={v.get('pick')} "
                  f"-> {v.get('reason','')[:80]}")

        # Decision rule:
        #  - 3/3 pick the same slug -> USE_EXISTING that slug
        #  - 2/3 pick the same slug -> USE_EXISTING that slug (majority)
        #  - 2+ vote "missing" -> MUST PRODUCE
        #  - split picks -> MUST PRODUCE (no consensus on which)
        picks = [v.get("pick") for v in panel.values() if v.get("verdict") == "use_existing"]
        missing_votes = sum(1 for v in panel.values() if v.get("verdict") == "missing")
        from collections import Counter
        pick_counts = Counter(p for p in picks if p)

        if missing_votes >= 2:
            decision = {"action": "produce_tomorrow", "reason": "majority says no existing bg fits"}
        elif pick_counts and pick_counts.most_common(1)[0][1] >= 2:
            chosen, votes = pick_counts.most_common(1)[0]
            decision = {"action": "use_existing", "slug": chosen,
                        "reason": f"{votes}/3 directors picked {chosen}"}
        else:
            decision = {"action": "produce_tomorrow",
                        "reason": "no consensus on a single existing bg"}

        print(f"  DECISION: {decision}")
        results[mid] = {
            "mission_text": LOCK["missions"][mid]["mission_text"],
            "qa": qa,
            "panel": panel,
            "decision": decision,
        }
        # incremental save — if script dies we keep prior mission votes
        OUT_PATH.write_text(json.dumps(results, indent=2, ensure_ascii=False), "utf-8")

    OUT_PATH.write_text(json.dumps(results, indent=2, ensure_ascii=False), "utf-8")
    print(f"\n=== AUDIT DONE -> {OUT_PATH.name} ===")
    print("SUMMARY:")
    for mid, r in results.items():
        d = r["decision"]
        if d["action"] == "use_existing":
            print(f"  {mid}: USE {d['slug']}  ({d['reason']})")
        else:
            print(f"  {mid}: PRODUCE TOMORROW  ({d['reason']})")


if __name__ == "__main__":
    main()
