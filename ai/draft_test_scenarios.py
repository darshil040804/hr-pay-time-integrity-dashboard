"""Ask an AI to draft structured test scenarios for every rule.

Usage (from the repo root):
    python -m ai.draft_test_scenarios

Writes docs/test_scenarios_ai_draft.md. A human edits the draft into the
final docs/test_scenarios.md, adding the Actual Result and Status columns.
Only synthetic material (rule descriptions and SQL) is sent.

One request per rule area (Org & Personnel, Time & Payroll) keeps each reply
short enough not to be cut off.
"""

import sys
from datetime import date
from pathlib import Path

from ai.client import AIClient, strip_code_fences
from src.rules import RULES, rule_sql

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "docs" / "test_scenarios_ai_draft.md"
COLUMNS = "| Test ID | Rule | Precondition | Steps | Expected Result |"

DASHBOARD = """HOW THE DASHBOARD WORKS (testers cannot load their own data):
- All rules run automatically on the committed synthetic dataset when a page opens.
- Pages: "Org & Personnel" (OP rules: bar chart + table filterable by Rule, Severity, Org unit),
  "Time & Payroll" (TP rules: pay period selector, recorded-vs-paid hours charts, table filterable
  by Rule and Severity), "HR Overview" (KPIs), "Testing & QA".
- Each exception row shows Rule, Severity, Employee ID, Name, Org unit or Period, Issue, Suggested action.
- Data: employee IDs are 6-digit numbers (100001-100500), positions POS0001-POS0535, org units
  ORG001-ORG040, pay periods PP01-PP06 covering 2026-01-05 to 2026-03-29.
- Boundary cases that need special data (e.g. exactly 16 hours) are checked by automated pytest
  tests on small fixtures, not in the dashboard. Say so in the Steps for such scenarios."""


def build_prompt(category: str) -> str:
    rules = "\n\n".join(f"### {rule_id}: {title}\n```sql\n{rule_sql(rule_id)}\n```"
                        for rule_id, (cat, title) in RULES.items() if cat == category)
    return f"""Draft structured test scenarios for the "{category}" HR data validation rules below.
The data is synthetic, modeled on SAP HCM (org units, positions, employees, time entries, payroll results).

{DASHBOARD}

For EACH rule write exactly 2 scenarios: one where the rule must flag a record, and one boundary
or look-alike case where it must NOT.

Return a single Markdown table and nothing else, with exactly these columns:
{COLUMNS}
- Test ID: TS-<rule id>-<two digits>, e.g. TS-TP-01-01
- Precondition: the data state needed, in plain English with concrete values
- Steps: short numbered steps (use <br> between steps)
- Expected Result: what the tester should see

RULES:

{rules}"""


def table_rows(markdown: str) -> list[str]:
    """Data rows of a markdown table (header and separator dropped)."""
    rows = [line.strip() for line in markdown.splitlines() if line.strip().startswith("|")]
    return [row for row in rows if not row.startswith("| Test ID") and not set(row) <= set("|-: ")]


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    client = AIClient()
    rows = []
    for category in dict.fromkeys(cat for cat, _ in RULES.values()):
        print(f"Drafting {category} scenarios with {client.model}...")
        reply = client.chat([
            {"role": "system", "content": "You are a QA lead who writes clear, structured test scenarios."},
            {"role": "user", "content": build_prompt(category)},
        ], temperature=0.3)
        new_rows = table_rows(strip_code_fences(reply))
        print(f"  {len(new_rows)} scenarios")
        rows.extend(new_rows)

    OUTPUT.write_text(
        "# Test Scenarios (AI draft)\n\n"
        f"> Drafted by `{client.model}` on {date.today().isoformat()} with `ai/draft_test_scenarios.py`.\n"
        "> **This is an unreviewed AI draft.** A human edits it into "
        "[`test_scenarios.md`](test_scenarios.md), which adds Actual Result and Status columns.\n\n"
        f"{COLUMNS}\n|---|---|---|---|---|\n" + "\n".join(rows) + "\n",
        encoding="utf-8",
    )
    print(f"Saved {OUTPUT.relative_to(ROOT)} ({len(rows)} scenarios)")


if __name__ == "__main__":
    main()
