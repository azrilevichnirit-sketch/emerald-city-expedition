"""Surgical layout fix for M1-M15:
- zone-a: transparent background (no top bar)
- zone-b: top:0 height:60vh (full screen above zone-c)
- zone-c: top:60vh
- Score readable via text-shadow
"""
import re
import sys
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent / "builder_html"

# Patterns to find and replace
FIXES = [
    # zone-a: replace background:#1a1a1a (or #...) with transparent + pointer-events:none
    (
        re.compile(r'(#zone-a\s*\{[^}]*?)background:#1a1a1a([^}]*?)\}'),
        r'\1background:transparent;pointer-events:none\2}'
    ),
    # zone-b: change top:6vh to top:0, height:54vh to height:60vh
    (
        re.compile(r'(#zone-b\s*\{[^}]*?)top:6vh([^}]*?)height:54vh([^}]*?)\}'),
        r'\1top:0\2height:60vh\3}'
    ),
    # score-display: add text-shadow if missing
    (
        re.compile(r'(#zone-a\s*\.score\s*\{[^}]*?font-weight:700;[^}]*?)\}'),
        r'\1;text-shadow:0 1px 3px rgba(0,0,0,0.9),0 2px 6px rgba(0,0,0,0.7)}'
    ),
]

def fix_file(p: Path) -> dict:
    txt_before = p.read_text(encoding="utf-8")
    txt = txt_before
    counts = {}
    for pattern, replacement in FIXES:
        new_txt, n = pattern.subn(replacement, txt)
        counts[pattern.pattern[:40]] = n
        txt = new_txt
    if txt != txt_before:
        p.write_text(txt, encoding="utf-8")
    return {"file": p.name, "counts": counts, "size_before": len(txt_before),
            "size_after": len(txt), "changed": txt != txt_before}

def main():
    html_files = sorted(OUT_DIR.glob("M*.html"))
    if not html_files:
        print("no M*.html found")
        return 1
    print(f"found {len(html_files)} mission files")
    for p in html_files:
        r = fix_file(p)
        status = "CHANGED" if r["changed"] else "no-op"
        print(f"  {r['file']:14} {status}  counts={r['counts']}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
