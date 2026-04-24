"""Shared library for the directing pipeline (stages 4-9).

Each directing agent (assembly, continuity, timing, interaction, storyboard,
harmony) is a narrow specialist that:
  1. Loads full project context (content_lock + asset_manifest + pose_map +
     bg briefs + all PRIOR stage outputs for its mission).
  2. Calls Claude Sonnet 4.5 with a focused system prompt that teaches ONLY
     its narrow responsibility.
  3. Writes ONE structured JSON to pipeline/directing/M<n>/<stage>.json.
  4. Reports status to the orchestrator which runs 4 -> 5 -> 6 -> 7 -> 8 -> 9.

Iron rules Nirit set for this pipeline:
  - SEQUENTIAL, not round-table. No agent "debates" a peer's decision.
  - Each agent reads predecessors' outputs as HARD CONSTRAINTS (not opinions
    to revisit).
  - harmony_auditor (stage 9) is NOT an agent that adds content. It is a
    cross-layer CHECKER that either PASSes or FAILs and points at the agent
    responsible for the contradiction.
  - All agents see all project-level context (never slug-only).

Usage (from each agent module):
    from _lib import call_claude, load_project_context, write_output

    ctx = load_project_context(mission="M1")
    # ctx.content_lock, ctx.asset_manifest, ctx.pose_map, ctx.bg_brief,
    # ctx.prior_outputs  (dict of stage_name -> parsed JSON)

    result = call_claude(system=MY_SYSTEM, user=render_user(ctx))
    write_output(mission="M1", stage="assembly", data=result)
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT = Path(__file__).resolve().parent.parent.parent
KEYS = PROJECT / "keys"
DIRECTING_OUT = PROJECT / "pipeline" / "directing"
DIRECTING_OUT.mkdir(parents=True, exist_ok=True)

# ----- Secrets -----

def _load_key(env_var: str, file_path: Path) -> str:
    v = os.environ.get(env_var)
    if v:
        return v.strip()
    if file_path.exists():
        return file_path.read_text("utf-8").strip()
    raise RuntimeError(f"missing secret: set env {env_var} or file {file_path}")


def claude_key() -> str:
    return _load_key("CLAUDE_API_KEY", KEYS / "claude" / "key.txt")


# ----- Claude API -----

CLAUDE_URL = "https://api.anthropic.com/v1/messages"
CLAUDE_MODEL = "claude-sonnet-4-5-20250929"


def call_claude(system: str, user: str, max_tokens: int = 4096,
                temperature: float = 0.3, retries: int = 3) -> str:
    """Single-turn Claude call. Returns assistant text.

    Retries on 429/5xx. Raises on non-recoverable error.
    """
    payload = {
        "model": CLAUDE_MODEL,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    body = json.dumps(payload).encode("utf-8")
    headers = {
        "x-api-key": claude_key(),
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    last_err = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(CLAUDE_URL, data=body, headers=headers,
                                          method="POST")
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return data["content"][0]["text"]
        except urllib.error.HTTPError as e:
            body_text = e.read().decode("utf-8", errors="replace")
            if e.code in (429, 500, 502, 503, 504):
                last_err = f"HTTP {e.code}: {body_text[:200]}"
                time.sleep(2 ** attempt * 3)
                continue
            raise RuntimeError(f"Claude HTTP {e.code}: {body_text[:400]}")
        except Exception as e:
            last_err = f"{type(e).__name__}: {e}"
            time.sleep(2 ** attempt * 3)
    raise RuntimeError(f"Claude failed after {retries} attempts: {last_err}")


def extract_json(text: str) -> Any:
    """Extract JSON from Claude's response. Tolerates ```json fences."""
    t = text.strip()
    if t.startswith("```"):
        lines = t.split("\n")
        # drop first fence line
        lines = lines[1:]
        # drop trailing fence
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        t = "\n".join(lines).strip()
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        # Try to find the outermost { ... } or [ ... ]
        for start_ch, end_ch in [("{", "}"), ("[", "]")]:
            s = t.find(start_ch)
            e = t.rfind(end_ch)
            if s >= 0 and e > s:
                try:
                    return json.loads(t[s:e+1])
                except json.JSONDecodeError:
                    pass
        raise RuntimeError(f"failed to parse JSON from Claude response:\n{text[:500]}")


# ----- Project context -----

@dataclass
class Context:
    mission: str                      # "M1".."M15"
    content_lock: dict                # full content_lock.json
    mission_data: dict                # content_lock.missions[M<n>]
    asset_manifest: dict              # asset_manifest.json
    pose_map: dict                    # pose_map.json
    bg_brief: dict | None             # bg director brief for this mission
    bg_mission_map: dict              # bg_mission_map.json
    prior_outputs: dict = field(default_factory=dict)
    # prior_outputs keys: "assembly","continuity","timing","interaction","storyboard","harmony"


def load_project_context(mission: str) -> Context:
    cl = json.loads((PROJECT / "content_lock.json").read_text("utf-8"))
    am_path = PROJECT / "pipeline" / "asset_manifest.json"
    am = json.loads(am_path.read_text("utf-8")) if am_path.exists() else {}
    pm_path = PROJECT / "pipeline" / "pose_map.json"
    pm = json.loads(pm_path.read_text("utf-8")) if pm_path.exists() else {}
    bgmm_path = PROJECT / "pipeline" / "bg_mission_map.json"
    bgmm = json.loads(bgmm_path.read_text("utf-8")) if bgmm_path.exists() else {}

    bg_brief_path = (PROJECT / "pipeline" / "debates" / "backgrounds"
                     / f"director_bg_design_bg_{mission}.json")
    bg_brief = (json.loads(bg_brief_path.read_text("utf-8"))
                if bg_brief_path.exists() else None)

    prior = {}
    mission_dir = DIRECTING_OUT / mission
    if mission_dir.exists():
        for stage in ("assembly", "continuity", "timing", "interaction",
                       "storyboard", "harmony"):
            p = mission_dir / f"{stage}.json"
            if p.exists():
                try:
                    prior[stage] = json.loads(p.read_text("utf-8"))
                except json.JSONDecodeError:
                    pass

    return Context(
        mission=mission,
        content_lock=cl,
        mission_data=cl.get("missions", {}).get(mission, {}),
        asset_manifest=am,
        pose_map=pm,
        bg_brief=bg_brief,
        bg_mission_map=bgmm,
        prior_outputs=prior,
    )


def load_prior_mission_output(prev_mission: str, stage: str) -> dict | None:
    p = DIRECTING_OUT / prev_mission / f"{stage}.json"
    if p.exists():
        try:
            return json.loads(p.read_text("utf-8"))
        except json.JSONDecodeError:
            return None
    return None


# ----- Output writer -----

def write_output(mission: str, stage: str, data: Any,
                 meta: dict | None = None) -> Path:
    out_dir = DIRECTING_OUT / mission
    out_dir.mkdir(parents=True, exist_ok=True)
    out = {
        "_stage": stage,
        "_mission": mission,
        "_generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "_generated_by": f"agent_0{STAGE_NUMS[stage]}_{stage}",
    }
    if meta:
        out.update({f"_{k}": v for k, v in meta.items()})
    if isinstance(data, dict):
        out.update(data)
    else:
        out["data"] = data
    p = out_dir / f"{stage}.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=2), "utf-8")
    print(f"  [{stage}] wrote {p.relative_to(PROJECT)}")
    return p


STAGE_NUMS = {
    "assembly": 4,
    "continuity": 5,
    "timing": 6,
    "interaction": 7,
    "storyboard": 8,
    "harmony": 9,
}


# ----- Mission helpers -----

def all_missions() -> list[str]:
    return [f"M{i}" for i in range(1, 16)]


def prev_mission(m: str) -> str | None:
    try:
        n = int(m.lstrip("M"))
        return f"M{n-1}" if n > 1 else None
    except ValueError:
        return None


def parse_missions_arg(arg: str) -> list[str]:
    if arg in ("all", ""):
        return all_missions()
    return [m.strip() for m in arg.split(",") if m.strip()]


def render_content_lock_mission(ctx: Context) -> str:
    """Compact rendering of the mission block for inclusion in prompts."""
    md = ctx.mission_data
    lines = [
        f"Mission: {ctx.mission}",
        f"mission_text: {md.get('mission_text', '')}",
        f"checkpoint_text: {md.get('checkpoint_text', '')}",
        f"checkpoint_label: {md.get('checkpoint_label', '')}",
        "Tools (3 slots A/B/C):",
    ]
    for t in md.get("tools", []):
        lines.append(
            f"  [{t['slot']}] {t['label']} (file={t['file']}, points={t['points']})"
        )
    return "\n".join(lines)


def render_bg_brief_summary(ctx: Context) -> str:
    """Extract the key facts from the bg brief without dumping the full debate."""
    if not ctx.bg_brief:
        return f"(no bg brief found for {ctx.mission})"
    question = ctx.bg_brief.get("question", "")
    context = ctx.bg_brief.get("context", "")
    # last round's voice_a often contains the final synthesis
    rounds = ctx.bg_brief.get("rounds", [])
    synthesis = ""
    if rounds:
        synthesis = rounds[-1].get("voice_a", "")[:800]
    return (
        f"Scene brief (from director debate):\n"
        f"  question: {question[:300]}\n"
        f"  context: {context[:300]}\n"
        f"  synthesis: {synthesis}"
    )
