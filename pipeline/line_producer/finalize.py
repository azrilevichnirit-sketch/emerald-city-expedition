"""line_producer.finalize — writes delivery_manifest.json after panel audit.

Reads:  pipeline/line_producer/optimization_log.json (with panel_verdict on each item)
Writes: delivery_manifest.json at project root

Only includes items with panel_verdict in {"pass", "flag_to_producer"}.
Items with "reject" or "retry_conservative" are excluded — those need another
pass through line_producer.run --conservative or producer attention.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT = Path(r"C:\emerald")
LP_DIR = PROJECT / "pipeline" / "line_producer"
LOG_PATH = LP_DIR / "optimization_log.json"
MANIFEST_PATH = PROJECT / "delivery_manifest.json"


def main() -> int:
    if not LOG_PATH.exists():
        print("ERROR: optimization_log.json missing. Run run.py + panel_audit.py first.")
        return 1
    log = json.loads(LOG_PATH.read_text("utf-8"))
    items = log.get("items", [])
    if not any("panel_verdict" in i for i in items):
        print("ERROR: no panel_verdict in items. Run panel_audit.py first.")
        return 1

    delivered = []
    flagged = []
    pending_retry = []
    for it in items:
        v = it.get("panel_verdict")
        rec = {
            "asset": it.get("asset"),
            "type": it.get("type"),
            "before_kb": it.get("before_kb"),
            "after_kb": it.get("after_kb"),
            "codec": it.get("codec"),
            "panel_verdict": v,
            "in_budget": it.get("in_budget"),
            "src": it.get("src"),
            "dst": it.get("dst"),
        }
        if v == "pass":
            delivered.append(rec)
        elif v == "flag_to_producer":
            flagged.append({**rec, "issue": it.get("panel_reason"),
                             "options": ["accept overage", "lower display", "regenerate"]})
            delivered.append(rec)  # ship anyway, but flagged
        elif v == "retry_conservative":
            pending_retry.append(rec)
        # reject -> excluded entirely

    total_before = sum(d.get("before_kb", 0) for d in delivered)
    total_after = sum(d.get("after_kb", 0) for d in delivered)
    summary = {
        "total_assets": len(delivered),
        "optimized": sum(1 for d in delivered if d.get("panel_verdict") == "pass"),
        "flagged_for_producer": len(flagged),
        "pending_retry": len(pending_retry),
        "total_kb_before": total_before,
        "total_kb_after": total_after,
        "reduction_ratio": round(total_before / max(1, total_after), 2),
        "page_load_estimated_mb": round(total_after / 1024, 1),
    }

    out = {
        "delivery_date": time.strftime("%Y-%m-%d"),
        "summary": summary,
        "per_asset": delivered,
        "flagged": flagged,
        "pending_retry": pending_retry,
    }
    MANIFEST_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2),
                              encoding="utf-8")

    print(f"\nDELIVERY MANIFEST written: {MANIFEST_PATH.relative_to(PROJECT)}")
    for k, v in summary.items():
        print(f"  {k:<22} {v}")
    if pending_retry:
        print(f"\n  {len(pending_retry)} item(s) need conservative retry:")
        print(f"    python pipeline/line_producer/run.py --conservative")
    if flagged:
        print(f"\n  {len(flagged)} item(s) flagged for Producer review.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
