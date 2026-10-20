"""Ask an AI to draft structured test scenarios for every rule.

Usage (from the repo root):
    python -m ai.draft_test_scenarios

Writes docs/test_scenarios_ai_draft.md. A human edits the draft into the
final docs/test_scenarios.md, adding the Actual Result and Status columns.
Only synthetic material (rule descriptions and SQL) is sent.
"""

from datetime import date
from pathlib import Path

from ai.client import AIClient, strip_code_fences
from src.rules import RULES, rule_sql

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "docs" / "test_scenarios_ai_draft.md"


def build_prompt() -> str:
    rules = "\n\n".join(f"### {rule_id}: {title} ({category})\n```sql\n{rule_sql(rule_id)}\n```"
                        for rule_id, (category, title) in RULES.items())
    return f"""Draft structured test scenarios for the HR data validation rules below.
The data is synthetic, modeled on SAP HCM (org units, positions, employees, time entries, payroll results).
The rules run in a Streamlit dashboard; a tester checks them by loading prepared data and reading the exception tables.

For EACH rule write 2 or 3 scenarios: at least one where the rule must flag a record, at least one where it
must not (a boundary or look-alike case).

Return a single Markdown table and nothing else, with exactly these columns:
| Test ID | Rule | Precondition | Steps | Expected Result |
- Test ID: TS-<rule id>-<two digits>, e.g. TS-TP-01-01
- Precondition: the data state needed, in plain English with concrete values
- Steps: short numbered steps a tester follows in the dashboard (use <br> between steps)
- Expected Result: what the tester should see, e.g. "One TP-01 exception for employee X in PP02"

RULES:

{rules}"""


def main():
    client = AIClient()
    print(f"Drafting test scenarios with {client.model}...")
    reply = client.chat([
        {"role": "system", "content": "You are a QA lead who writes clear, structured test scenarios."},
        {"role": "user", "content": build_prompt()},
    ], temperature=0.3)
    table = strip_code_fences(reply)

    OUTPUT.write_text(
        "# Test Scenarios (AI draft)\n\n"
        f"> Drafted by `{client.model}` on {date.today().isoformat()} with `ai/draft_test_scenarios.py`.\n"
        "> **This is an unreviewed AI draft.** A human edits it into "
        "[`test_scenarios.md`](test_scenarios.md), which adds Actual Result and Status columns.\n\n"
        f"{table}\n",
        encoding="utf-8",
    )
    print(f"Saved {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
