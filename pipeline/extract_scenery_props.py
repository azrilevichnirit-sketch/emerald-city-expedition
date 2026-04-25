"""Normalize the 15 mission scenery plans into a structured list of props.

Input:  pipeline/debates/scenery/_scenery_plan.json (approved syntheses in Hebrew)
Output: pipeline/debates/scenery/_props_structured.json
   [{"mission":"M1","slug":"broken_door","he":"דלת פרוצה","en":"broken jungle door",
     "css":"bottom:X%; left:Y%; width:Z%; z-index:N","size":"1024x1024"}, ...]

Uses Claude to parse each mission's synthesis into structured JSON. Output is then
consumed by generate_scenery_props.py.
"""
import json
import re
from pathlib import Path
from debate_runner import call_claude

PROJECT = Path(__file__).resolve().parent.parent
PLAN = PROJECT / "pipeline" / "debates" / "scenery" / "_scenery_plan.json"
OUT = PROJECT / "pipeline" / "debates" / "scenery" / "_props_structured.json"
LOCK = json.loads((PROJECT / "content_lock.json").read_text("utf-8"))


SYS = (
    "You are a production structure extractor. Given a Hebrew synthesis describing "
    "scenery props for a game mission, return STRICT JSON ARRAY (no prose, no "
    "markdown, no code fences) of props. Each prop: "
    "{\"slug\": <lowercase ascii, underscore-separated, matches *.png filename>, "
    "\"he\": <Hebrew label>, "
    "\"en_prompt\": <detailed English visual description of JUST this prop, 20-40 words, "
    "photorealistic tropical-expedition style, no characters, no text, neutral isolated>, "
    "\"css\": <exact CSS zone string if provided, else empty>, "
    "\"size\": \"1024x1024\"}. "
    "Extract only props that clearly appear in the synthesis. If synthesis mentions a "
    "location area (jungle, cave) AND specific props inside, extract each as separate prop. "
    "Do NOT invent. Do NOT include tool-hand items (bungee rope, camera, etc — those are "
    "tools, not scenery)."
)


def extract_one(mid, mission, synthesis):
    user = (
        f"Mission {mid}.\n"
        f"mission_text: {mission['mission_text']}\n"
        f"synthesis (Hebrew): {synthesis}\n\n"
        "Return JSON array only."
    )
    resp = call_claude(SYS, user, max_tokens=1200)
    # strip code fences if any
    resp = re.sub(r"^```(?:json)?\s*|\s*```$", "", resp.strip(), flags=re.M)
    try:
        arr = json.loads(resp)
    except json.JSONDecodeError:
        m = re.search(r"\[.*\]", resp, re.S)
        arr = json.loads(m.group(0)) if m else []
    for p in arr:
        p["mission"] = mid
    return arr


def main():
    plan = json.loads(PLAN.read_text("utf-8"))["plan_by_mission"]
    out = []
    for mid, info in plan.items():
        if info.get("decision") != "pass":
            print(f"  {mid}: skip (decision={info.get('decision')})")
            continue
        syn = info.get("synthesis") or ""
        if not isinstance(syn, str):
            syn = json.dumps(syn, ensure_ascii=False)
        mission = LOCK["missions"].get(mid, {})
        props = extract_one(mid, mission, syn)
        print(f"  {mid}: {len(props)} props — {[p.get('slug') for p in props]}")
        out.extend(props)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"total props: {len(out)}. wrote {OUT}")


if __name__ == "__main__":
    main()
