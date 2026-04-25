"""
For tools that auto-failed or human-review-failed, mutate their prompt JSONs
to be more rembg-friendly: stronger 3D shape cues, less flat/folded geometry,
explicit 'prominent object', and a fresh attempt.

Reads pipeline/loop_state.json + optional pipeline/human_review_verdicts.json
Writes pipeline/retries_queue.json listing slugs to re-generate, and mutates
their prompt JSONs in-place with _retry_attempt counter.
"""
import json
from pathlib import Path

PROJECT = Path(r"C:/Users/azril/OneDrive/Desktop/fincail_game/new")
PROMPTS = PROJECT / "pipeline" / "prompts"
AUTO = PROJECT / "pipeline" / "auto_review.json"
VERDICTS = PROJECT / "pipeline" / "human_review_verdicts.json"
QA = PROJECT / "pipeline" / "review" / "tools_qa"

REINFORCE = (", prominent 3D shape with strong silhouette, object clearly stands out, "
             "well-lit with deep shadows, large centered subject")


def load_auto():
    if AUTO.exists():
        return json.loads(AUTO.read_text(encoding="utf-8"))
    return {}


def load_verdicts():
    if VERDICTS.exists():
        return json.loads(VERDICTS.read_text(encoding="utf-8"))
    return {}


def needs_retry(slug, auto, verdicts):
    a = auto.get(slug, {})
    v = verdicts.get(slug, {})
    if a.get("status") in ("auto_fail_empty", "auto_fail_rembg_stripped", "missing"):
        return True
    if v.get("verdict") == "FAIL":
        return True
    return False


def mutate(slug):
    path = PROMPTS / f"{slug}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    attempt = data.get("_retry_attempt", 0) + 1
    if attempt > 2:
        return None, attempt
    orig = data["prompts"]["leonardo"]
    if REINFORCE not in orig:
        data["prompts"]["leonardo"] = orig + REINFORCE
    data["_retry_attempt"] = attempt
    # Remove stale generated files so should_skip doesn't skip
    for suffix in ("_raw.png", "_rembg.png", "_final.png"):
        f = QA / f"{slug}{suffix}"
        if f.exists():
            f.unlink()
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data, attempt


def main():
    auto = load_auto()
    verdicts = load_verdicts()
    slugs = [p.stem for p in sorted(PROMPTS.glob("*.json"))]
    queue = []
    exhausted = []
    for s in slugs:
        if not needs_retry(s, auto, verdicts):
            continue
        data, attempt = mutate(s)
        if data is None:
            exhausted.append(s)
            print(f"EXHAUSTED: {s} (attempt {attempt} > 2)")
        else:
            queue.append({"slug": s, "attempt": attempt})
            print(f"QUEUED: {s} (attempt {attempt})")
    # Also remove these from loop_state so run_full_loop regenerates them
    state_f = PROJECT / "pipeline" / "loop_state.json"
    if state_f.exists():
        state = json.loads(state_f.read_text(encoding="utf-8"))
        for q in queue:
            state["tools"].pop(q["slug"], None)
        state_f.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    (PROJECT / "pipeline" / "retries_queue.json").write_text(
        json.dumps({"queue": queue, "exhausted": exhausted}, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(f"\nQueued: {len(queue)}, Exhausted (needs_manual_review): {len(exhausted)}")


if __name__ == "__main__":
    main()
