"""One-shot panel query: how to close the M8 gap (footprints + tunnel)?
A) new bg | B) keep bg + scenery props | C) other.
Zero Veo. Just the 3 directors voting on a design choice.
"""
import sys
import json
import base64
from pathlib import Path
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "pipeline"))
from debate_runner import call_engine
from resolve_via_panel import _parse_json, ENGINES

LOCK = json.loads((PROJECT / "content_lock.json").read_text("utf-8"))
BG_KF = PROJECT / "pipeline" / "review" / "backgrounds" / "_kf_bg_M8.png"

img_b64 = base64.b64encode(BG_KF.read_bytes()).decode("ascii") if BG_KF.exists() else None

m = LOCK["missions"]["M8"]
system = (
    "You are one of 3 Studio Emerald directors.\n\n"
    f"Mission M8: {m['mission_text']}\n"
    f"Checkpoint: {m.get('checkpoint_text','')}\n\n"
    "The attached image is a keyframe from bg_M8 (existing background video).\n"
    "bg_M8 shows a wet vertical rock face. OpenAI flagged that the mission also\n"
    "requires TWO additional elements: fresh footprints and a tunnel-mouth entrance.\n\n"
    "Our layer architecture (from design_system.md section 8):\n"
    "  z-index 0: background video (bg_M8)\n"
    "  z-index 2: scenery PNGs (props composited over bg)\n"
    "  z-index 5+: rivals, player, etc.\n\n"
    "Decide the CHEAPEST correct path:\n"
    "  (A) Regenerate bg_M8 entirely to include footprints + tunnel (full Veo call)\n"
    "  (B) Keep bg_M8 as-is, produce 2 new scenery PNG props (footprints.png,\n"
    "      tunnel_mouth.png) composited on top in code\n"
    "  (C) Something else - explain\n\n"
    "Return STRICT JSON:\n"
    '{"choice":"A|B|C","reason":"<one sentence>","extra":"<if C, describe>"}'
)

print("asking panel on M8 options...")
votes = {}
for eng in ENGINES:
    try:
        resp = call_engine(eng, system, "Pick the right option for M8.",
                           image_b64=img_b64, max_tokens=300)
        votes[eng] = _parse_json(resp)
    except Exception as e:
        votes[eng] = {"choice": "?", "reason": f"error: {e}"}
    v = votes[eng]
    print(f"  {eng}: {v.get('choice')} -> {v.get('reason','')[:120]}")

c = Counter(v.get("choice") for v in votes.values())
winner = c.most_common(1)[0]
print(f"\nRESULT: {winner[0]} wins ({winner[1]}/3)")
out = PROJECT / "pipeline" / "review" / "backgrounds" / "_m8_option_vote.json"
out.write_text(
    json.dumps({"votes": votes, "winner": winner[0], "tally": dict(c)},
               ensure_ascii=False, indent=2),
    "utf-8",
)
print(f"saved -> {out.name}")
