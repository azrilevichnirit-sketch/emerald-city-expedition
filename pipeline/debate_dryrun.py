"""Dry-run: print the question + context that would be sent for 3 sample slugs."""
import json
from pathlib import Path
from debate_audit_45 import build_context, ALL_SLUGS

PROJECT = Path(__file__).resolve().parent.parent
lock = json.loads((PROJECT / "content_lock.json").read_text(encoding="utf-8"))

for slug in ["מצנח_מ01", "גלשן_מ01", "כנפיים_מ01", "קאטר_מ10", "זיקוק_מ15"]:
    q, c = build_context(slug, lock)
    print(f"\n===== {slug} =====")
    print("Q:", q)
    print("C:", c)
