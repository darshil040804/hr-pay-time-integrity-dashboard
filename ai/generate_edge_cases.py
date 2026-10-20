"""Ask an AI for boundary and tricky test cases per rule, validate them, save as pending.

Usage (from the repo root):
    python -m ai.generate_edge_cases                  # all rules
    python -m ai.generate_edge_cases --rules TP-01 TP-04
    python -m ai.generate_edge_cases --dry-run        # no AI calls: run pending cases, print AGREE/DISAGREE

Generated cases are merged into tests/ai_generated/edge_cases.json with
review_status "pending". Cases that were already there are never changed.
Only cases a human marks "accepted" run in pytest; see docs/ai_testing_log.md.

Only synthetic data (rule text, SQL, table schemas, made-up rows) is sent.
"""

import argparse
import json
import re
import sys

from pydantic import ValidationError

from ai.client import AIClient
from src.edge_cases import (REFERENCE_TABLES, TEMPLATE_ROWS, EdgeCase, load_cases, run_case,
                            save_cases)
from src.rules import RULES, load_csv_tables, rule_sql
from src.schema import ALLOWED_VALUES, SCHEMA

SYSTEM_PROMPT = (
    "You are a senior QA analyst testing HR data validation rules for a payroll team. "
    "You design small, precise test datasets that probe boundaries and tricky situations. "
    "You reply with JSON only."
)


# Models like typographic punctuation; plain ASCII keeps the JSON easy to review and edit.
_ASCII_PUNCTUATION = str.maketrans({"‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-",
                                    "‘": "'", "’": "'", "“": '"', "”": '"',
                                    "…": "...", " ": " ", " ": " ", "≤": "<=", "≥": ">="})


def plain_text(text: str) -> str:
    return text.translate(_ASCII_PUNCTUATION) if isinstance(text, str) else text


def tables_used(sql: str) -> list[str]:
    return [table for table in SCHEMA if re.search(rf"\b{table}\b", sql)]


def reference_summary(reference) -> str:
    periods = "; ".join(f"{r.period_id} {r.start_date} to {r.end_date}, paid {r.pay_date}"
                        for r in reference["pay_periods"].itertuples())
    jobs = "; ".join(f"{r.job_id} {r.title} ({r.flsa_status})" for r in reference["jobs"].itertuples())
    wage_types = "; ".join(f"{r.wage_type} {r.description}" for r in reference["wage_types"].itertuples())
    org_units = ", ".join(reference["org_units"]["org_unit_id"].head(10)) + ", ..."
    return (f"- pay_periods: {periods}\n- jobs: {jobs}\n- wage_types: {wage_types}\n"
            f"- org_units: IDs {org_units} (ORG001-ORG040 exist; anything else does not)")


def build_prompt(rule_id: str, n_cases: int, reference) -> str:
    sql = rule_sql(rule_id)
    tables = tables_used(sql)
    schemas = "\n".join(
        f"- {t}: " + ", ".join(f"{c} ({kind})" for c, kind in SCHEMA[t].items()) for t in tables
    )
    allowed = "\n".join(f"- {t}.{c}: {values}" for (t, c), values in ALLOWED_VALUES.items() if t in tables)
    templates = "\n".join(f"- {t}: {json.dumps(TEMPLATE_ROWS[t])}" for t in tables)
    category, title = RULES[rule_id]

    return f"""Design {n_cases} boundary or tricky test cases for this validation rule.

RULE {rule_id} ({category}): {title}

The rule is implemented in DuckDB SQL. It returns one row per exception:
```sql
{sql}
```

TABLES THE RULE READS (column (type)):
{schemas}

ALLOWED VALUES:
{allowed}

DATA CONVENTIONS:
- Dates are "YYYY-MM-DD" strings. "9999-12-31" means open-ended. Use null for a missing value.
- These reference tables are preloaded with standard data unless your case provides its own rows
  for that table (then only your rows are used):
{reference_summary(reference)}
- Any column you leave out of a row is filled from this clean template row for its table:
{templates}
  So give each row only the columns that matter, but always give the IDs that link rows together
  (emp_id, position_id, period_id, job_id, org_unit_id).
- Include rows for every non-reference table the rule reads. Keep each case small (under 10 rows per table).

WHAT MAKES A GOOD CASE:
Probe boundaries and tricky situations, for example: values exactly at a threshold, just over and
just under it; dates exactly on a boundary (on the term date, on the last day of a pay period);
nulls and missing links; records that look like a defect but are legitimate; several defects at once.
Include both cases that SHOULD be flagged and cases that should NOT be flagged.

DECIDE expected_flagged FROM THE BUSINESS INTENT of the rule ("{title}"), the way an HR or payroll
expert would. Do not simply trace the SQL. If you believe the SQL handles your case differently
from the business intent, still answer per the business intent and explain the mismatch in the rationale.
expected_flagged is true if the rule should return AT LEAST ONE exception for the case's data.

Reply with JSON only, in exactly this shape:
{{"cases": [
  {{"description": "one sentence: the scenario being tested",
    "records": {{"<table>": [{{"<column>": <value>, ...}}, ...], ...}},
    "expected_flagged": true,
    "rationale": "one or two sentences: why, citing the boundary"}}
]}}"""


def generate_for_rule(client: AIClient, rule_id: str, n_cases: int, next_number: int, reference):
    """Ask for cases for one rule; return the valid ones as pending EdgeCases."""
    try:
        reply = client.chat_json(
            [{"role": "system", "content": SYSTEM_PROMPT},
             {"role": "user", "content": build_prompt(rule_id, n_cases, reference)}],
            temperature=0.4,
        )
    except json.JSONDecodeError as error:
        print(f"  {rule_id}: reply was not valid JSON ({error}); skipped")
        return []

    raw_cases = reply.get("cases", []) if isinstance(reply, dict) else []
    valid = []
    for i, raw in enumerate(raw_cases, start=1):
        case_id = f"AI-{rule_id}-{next_number + len(valid):03d}"
        try:
            raw = {**raw, "description": plain_text(raw.get("description")),
                   "rationale": plain_text(raw.get("rationale"))}
            case = EdgeCase(**{**raw, "case_id": case_id, "rule_id": rule_id,
                               "review_status": "pending", "reviewer_note": "", "rule_bug": False})
            run_case(case, reference)  # must load and run cleanly
        except (ValidationError, TypeError, ValueError) as error:
            reason = error.errors()[0]["msg"] if isinstance(error, ValidationError) else str(error)
            print(f"  {rule_id} proposal {i}: dropped ({reason})")
            continue
        except Exception as error:  # e.g. a value DuckDB cannot load
            print(f"  {rule_id} proposal {i}: dropped (could not run: {error})")
            continue
        valid.append(case)
    print(f"  {rule_id}: {len(valid)} of {len(raw_cases)} proposed cases kept")
    return valid


def next_case_number(cases, rule_id: str) -> int:
    numbers = [int(c.case_id.rsplit("-", 1)[1]) for c in cases if c.rule_id == rule_id]
    return max(numbers, default=0) + 1


def generate(rule_ids: list[str], n_cases: int) -> None:
    client = AIClient()
    reference = load_csv_tables()
    cases = load_cases()
    print(f"Model {client.model}; {len(cases)} existing cases kept as they are.")
    added = 0
    for rule_id in rule_ids:
        new = generate_for_rule(client, rule_id, n_cases, next_case_number(cases, rule_id), reference)
        cases.extend(new)
        added += len(new)
        save_cases(cases)  # save after every rule so a later failure loses nothing
    print(f"Added {added} pending cases. Next: python -m ai.generate_edge_cases --dry-run")


def dry_run(include_reviewed: bool) -> None:
    """Run cases against the rules (no AI calls) and print AGREE / DISAGREE."""
    reference = load_csv_tables()
    cases = [c for c in load_cases() if include_reviewed or c.review_status == "pending"]
    if not cases:
        print("No pending cases. Run without --dry-run to generate some.")
        return
    disagreements = 0
    for case in cases:
        found = run_case(case, reference)
        flagged = not found.empty
        verdict = "AGREE" if flagged == case.expected_flagged else "DISAGREE"
        disagreements += verdict == "DISAGREE"
        print(f"{verdict:8s} {case.case_id} [{case.review_status}]  AI expects "
              f"{'flagged' if case.expected_flagged else 'not flagged'}; rule "
              f"{'flagged ' + str(len(found)) + ' row(s)' if flagged else 'flagged nothing'}")
        print(f"         {case.description}")
        if verdict == "DISAGREE":
            print(f"         AI rationale: {case.rationale}")
    print(f"\n{len(cases)} cases: {len(cases) - disagreements} AGREE, {disagreements} DISAGREE.")
    print("Review each case in tests/ai_generated/edge_cases.json and set review_status to "
          '"accepted" or "rejected" (see docs/ai_testing_log.md).')


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rules", nargs="+", default=list(RULES), choices=list(RULES), metavar="RULE_ID",
                        help="rules to generate cases for (default: all)")
    parser.add_argument("--cases", type=int, default=4, choices=range(3, 6), metavar="3-5",
                        help="cases to request per rule (default 4)")
    parser.add_argument("--dry-run", action="store_true",
                        help="make no AI calls; run pending cases and print AGREE/DISAGREE")
    parser.add_argument("--all", action="store_true", help="with --dry-run, include reviewed cases too")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows consoles default to cp1252

    if args.dry_run:
        dry_run(args.all)
    else:
        generate(args.rules, args.cases)


if __name__ == "__main__":
    main()
