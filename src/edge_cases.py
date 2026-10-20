"""AI-proposed edge cases: the case format, validation, and how a case is run.

Shared by ai/generate_edge_cases.py (validation and --dry-run),
tests/test_ai_edge_cases.py (accepted cases), and the Testing & QA page.

A case is a tiny dataset plus a prediction: does the rule flag anything?
    records          {table: [row, ...]}; columns a row leaves out are filled
                     from a clean TEMPLATE_ROWS row for that table.
    expected_flagged True if the rule should return at least one exception.

Reference tables (org_units, jobs, wage_types, pay_periods) that a case does
not provide are loaded from the committed CSVs, so a case only needs the rows
that matter for its scenario.
"""

import json
from pathlib import Path
from typing import Literal

import pandas as pd
from pydantic import BaseModel, Field, field_validator

from src.rules import RULES, connect, load_csv_tables, run_rule
from src.schema import ALLOWED_VALUES, SCHEMA, coerce

ROOT = Path(__file__).resolve().parent.parent
EDGE_CASES_PATH = ROOT / "tests" / "ai_generated" / "edge_cases.json"
REFERENCE_TABLES = ["org_units", "jobs", "wage_types", "pay_periods"]

# One clean, neutral row per table. Fills any column a case leaves out.
TEMPLATE_ROWS = {
    "org_units": {"org_unit_id": "ORG008", "name": "College of Engineering", "parent_org_unit_id": "ORG002",
                  "valid_from": "2020-01-01", "valid_to": "9999-12-31"},
    "jobs": {"job_id": "JOB08", "title": "Administrative Assistant", "flsa_status": "Non-exempt"},
    "positions": {"position_id": "POS9001", "org_unit_id": "ORG008", "job_id": "JOB08", "status": "Active",
                  "valid_from": "2020-01-01", "valid_to": "9999-12-31"},
    "employees": {"emp_id": 900001, "first_name": "Test", "last_name": "Employee", "position_id": "POS9001",
                  "employee_group": "Support Staff", "employee_subgroup": "Hourly",
                  "weekly_scheduled_hours": 40.0, "status": "Active", "hire_date": "2020-01-01",
                  "term_date": None},
    "wage_types": {"wage_type": "1000", "description": "Regular Pay", "eligible_flsa": "Both"},
    "pay_periods": {"period_id": "PP01", "start_date": "2026-01-05", "end_date": "2026-01-18",
                    "pay_date": "2026-01-23"},
    "time_entries": {"emp_id": 900001, "work_date": "2026-01-05", "hours": 8.0, "attendance_type": "Regular"},
    "payroll_results": {"period_id": "PP01", "emp_id": 900001, "wage_type": "1000", "hours": 8.0,
                        "amount": 160.0, "payment_date": "2026-01-23"},
}


class EdgeCase(BaseModel):
    case_id: str = Field(pattern=r"^AI-(OP|TP)-\d{2}-\d{3}$")
    rule_id: str
    description: str = Field(min_length=5)
    records: dict[str, list[dict]]
    expected_flagged: bool
    rationale: str = Field(min_length=5)
    review_status: Literal["pending", "accepted", "rejected"] = "pending"
    reviewer_note: str = ""
    # Set by the reviewer when this case exposed a bug in the rule (see docs/ai_testing_log.md).
    rule_bug: bool = False

    @field_validator("rule_id")
    @classmethod
    def _known_rule(cls, value):
        if value not in RULES:
            raise ValueError(f"unknown rule {value!r}")
        return value

    @field_validator("records")
    @classmethod
    def _matches_schema(cls, records):
        if not any(records.values()):
            raise ValueError("records is empty")
        for table, rows in records.items():
            if table not in SCHEMA:
                raise ValueError(f"unknown table {table!r}")
            for row in rows:
                unknown = set(row) - set(SCHEMA[table])
                if unknown:
                    raise ValueError(f"unknown column(s) in {table}: {sorted(unknown)}")
                for column, value in row.items():
                    allowed = ALLOWED_VALUES.get((table, column))
                    if allowed and value is not None and value not in allowed:
                        raise ValueError(f"{table}.{column}={value!r} is not one of {allowed}")
            try:
                coerce(pd.DataFrame(rows), table)  # types and dates must parse
            except Exception as error:
                raise ValueError(f"bad value in {table}: {error}") from None
        return records


def build_tables(case: EdgeCase, reference: dict[str, pd.DataFrame] | None = None) -> dict[str, pd.DataFrame]:
    """Turn a case's records into full tables, ready for rules.connect()."""
    reference = reference if reference is not None else load_csv_tables()
    tables = {}
    for table in SCHEMA:
        if table in case.records:
            rows = [TEMPLATE_ROWS[table] | row for row in case.records[table]]
            tables[table] = coerce(pd.DataFrame(rows, columns=list(SCHEMA[table])), table)
        elif table in REFERENCE_TABLES:
            tables[table] = reference[table]
    return tables


def run_case(case: EdgeCase, reference: dict[str, pd.DataFrame] | None = None) -> pd.DataFrame:
    """Run the case's rule on the case's data; returns the exception rows."""
    return run_rule(connect(build_tables(case, reference)), case.rule_id)


def load_cases(path: Path = EDGE_CASES_PATH) -> list[EdgeCase]:
    if not path.exists():
        return []
    return [EdgeCase(**raw) for raw in json.loads(path.read_text(encoding="utf-8"))]


def save_cases(cases: list[EdgeCase], path: Path = EDGE_CASES_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(cases, key=lambda c: c.case_id)
    path.write_text(json.dumps([c.model_dump() for c in ordered], indent=2) + "\n", encoding="utf-8")
