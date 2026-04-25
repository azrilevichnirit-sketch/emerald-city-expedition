"""Re-run only steps 6+7 of the endoscope pipeline — debate+image already done."""
import json
from pathlib import Path
from run_endoscope_pipeline import step6_director, step7_finalize, SLUG, REVIEW_DIR, QA_DIR

PROJECT = Path(__file__).resolve().parent.parent
final_file = REVIEW_DIR / f"{SLUG}_rD_final.png"
qa_file = QA_DIR / f"{SLUG}_rD_qa.json"
directive_file = PROJECT / "pipeline" / "prompts" / f"{SLUG}_rD.txt"

assert final_file.exists(), f"missing: {final_file}"
assert qa_file.exists(), f"missing: {qa_file}"

qa = json.loads(qa_file.read_text(encoding="utf-8"))
# directive was embedded in prompts/; we reconstruct briefly from the debate synthesis
debates = PROJECT / "pipeline" / "debates" / f"production_designer_pregen_{SLUG}.json"
debate = json.loads(debates.read_text(encoding="utf-8"))
directive = debate["final_decision"].get("synthesis", "") + " | " + debate["final_decision"].get("fix_notes", "")

director = step6_director(final_file, directive)
summary = step7_finalize(final_file, qa, director, directive)
print()
print(json.dumps(summary, ensure_ascii=False, indent=2))
