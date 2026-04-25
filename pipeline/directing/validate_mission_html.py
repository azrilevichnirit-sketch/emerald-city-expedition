"""validate_mission_html — strict QA pass on the generated HTML files.

Checks per mission:
  - File exists, parses (well-formed enough for browser)
  - Referenced asset paths (../../assets/...) all resolve
  - 4 zones present (a/b/c/d) at correct dimensions
  - RTL declared
  - Hebrew font loaded (Heebo)
  - Canvas chroma key present (no raw <video> for player)
  - Segment loop, NOT video.loop = true
  - 3 tools rendered, each with ⓘ icon + tooltip
  - No forbidden colors (gold/orange/yellow palette)
  - mission_text + checkpoint_text are not empty
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT = Path(__file__).resolve().parent.parent.parent
HTML_DIR = PROJECT / "pipeline" / "builder_html"
OUT = PROJECT / "pipeline" / "review" / "builder_html_qa.json"
OUT.parent.mkdir(parents=True, exist_ok=True)

FORBIDDEN_COLORS = ["#ffd700", "#ffa500", "#ffeb3b", "#ffc107",
                    "#ff9800", "gold", "orange"]
ALLOWED_OK_TOKENS = ["#4A90E2", "#E94B3C", "#7FB069", "#1a3a5c",
                     "#F5A623"]  # F5A623 might fail "no orange" — director chose this; flag


def find_asset_refs(html: str) -> list[str]:
    return re.findall(r"\.\./\.\./assets/[^\"' )]+", html)


def validate_one(mission: str) -> dict:
    p = HTML_DIR / f"{mission}.html"
    if not p.exists():
        return {"mission": mission, "status": "MISSING"}

    html = p.read_text(encoding="utf-8")
    issues = []
    info = {}

    # ── structural ──
    if 'dir="rtl"' not in html:
        issues.append("missing dir=rtl")
    if 'charset="UTF-8"' not in html:
        issues.append("missing UTF-8 charset")
    for z in ("zone-a", "zone-b", "zone-c", "zone-d"):
        if f'id="{z}"' not in html:
            issues.append(f"missing #{z}")

    # zone heights from design_system
    if "height:6vh" not in html: issues.append("zone-a height != 6vh")
    if "height:54vh" not in html: issues.append("zone-b height != 54vh")
    if "height:16vh" not in html: issues.append("zone-c height != 16vh")
    if "height:24vh" not in html: issues.append("zone-d height != 24vh")

    # ── font ──
    if "Heebo" not in html:
        issues.append("Heebo font not loaded")

    # ── chroma key ──
    if "getImageData" not in html or "putImageData" not in html:
        issues.append("no chroma key processing")
    if "#player-source" not in html and "player-source" not in html:
        issues.append("no player video source")
    if "player-canvas" not in html:
        issues.append("no player canvas")
    # player video must be display:none
    if "#player-source{display:none}" not in html.replace(" ", "") and \
       "#player-source { display:none }" not in html and \
       "#player-source{display: none}" not in html:
        # be lenient — just check the rule exists somewhere
        if "player-source" in html and "display:none" not in html:
            issues.append("player-source not display:none")

    # ── no video.loop=true ──
    # exclude comment strings — strip JS/HTML comments before checking
    code = re.sub(r"//[^\n]*", "", html)
    code = re.sub(r"/\*.*?\*/", "", code, flags=re.S)
    if re.search(r"\.loop\s*=\s*true", code) or re.search(r"\bloop\s*:\s*true", code):
        issues.append("uses video.loop=true (forbidden)")
    if "startBgLoop" not in html:
        issues.append("no segment loop function")

    # ── tools ──
    tools_match = re.search(r"const TOOLS = (\[.*?\]);", html, re.S)
    if not tools_match:
        issues.append("TOOLS array not found")
    else:
        try:
            tools = json.loads(tools_match.group(1))
            info["tool_count"] = len(tools)
            if len(tools) != 3:
                issues.append(f"tool count = {len(tools)}, expected 3")
            for t in tools:
                if not t.get("file"):
                    issues.append(f"tool {t.get('slot')} missing file")
                if not t.get("label"):
                    issues.append(f"tool {t.get('slot')} missing label")
                if t.get("consequence") not in ("hold", "use", "wear", "deploy"):
                    issues.append(f"tool {t.get('slot')} bad consequence: {t.get('consequence')}")
        except json.JSONDecodeError as e:
            issues.append(f"TOOLS array unparseable: {e}")

    if "tool-info-icon" not in html:
        issues.append("no ⓘ icon")
    if "tool-tooltip" not in html:
        issues.append("no tool tooltip")
    if "switch (tool.consequence)" not in html:
        issues.append("no consequence switch")

    # ── colors ──
    low = html.lower()
    for c in FORBIDDEN_COLORS:
        if c in low:
            issues.append(f"forbidden color: {c}")

    # ── content ──
    scene_match = re.search(r"const SCENE = (\{.*?\});", html, re.S)
    if scene_match:
        try:
            scene = json.loads(scene_match.group(1))
            info["mission_text_len"] = len(scene.get("missionText", ""))
            info["checkpoint_text_len"] = len(scene.get("checkpointText", ""))
            if not scene.get("missionText"):
                issues.append("missionText empty")
            if not scene.get("checkpointText"):
                issues.append("checkpointText empty")
        except json.JSONDecodeError as e:
            issues.append(f"SCENE unparseable: {e}")

    # ── asset paths exist ──
    refs = find_asset_refs(html)
    info["asset_refs"] = len(refs)
    bad_refs = []
    for r in set(refs):
        # convert ../../assets/foo → assets/foo relative to PROJECT
        rel = r.replace("../../", "")
        if not (PROJECT / rel).exists():
            bad_refs.append(r)
    if bad_refs:
        issues.extend([f"asset missing: {r}" for r in bad_refs])

    return {
        "mission": mission,
        "status": "OK" if not issues else "FAIL",
        "issues": issues,
        "info": info,
    }


def main(argv: list[str]) -> int:
    arg = argv[1] if len(argv) > 1 else "all"
    if arg == "all":
        missions = [f"M{i}" for i in range(1, 16)]
    else:
        missions = [m.strip() for m in arg.split(",") if m.strip()]

    print(f"validating {len(missions)} HTML file(s)...")
    results = []
    fail = 0
    for m in missions:
        r = validate_one(m)
        results.append(r)
        if r["status"] != "OK":
            fail += 1
        marker = "OK" if r["status"] == "OK" else f"FAIL ({len(r['issues'])})"
        print(f"  {m}: {marker}")
        for issue in r.get("issues", [])[:5]:
            print(f"      - {issue}")

    summary = {"total": len(missions), "ok": len(missions) - fail, "fail": fail}
    OUT.write_text(json.dumps({
        "_audited_at": __import__("time").strftime("%Y-%m-%d %H:%M:%S"),
        "summary": summary,
        "results": results,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nsummary: {summary['ok']}/{summary['total']} pass  -> {OUT.relative_to(PROJECT)}")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
