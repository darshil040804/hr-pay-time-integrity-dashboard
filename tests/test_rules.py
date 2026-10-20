"""Regression tests for the validation rules.

1. On the committed data, every rule finds exactly the planted number of
   defects (expected counts come from data/planted_defects.csv).
2. On the clean data (before planting), every rule finds nothing.
3. Small hand-built fixtures pin down rule boundaries.
"""

from datetime import date

import pandas as pd
import pytest

from data.generate import generate_clean
from src.rules import RESULT_COLUMNS, RULES, SEVERITIES, SQL_DIR, connect, run_all, run_rule

PLANTED = pd.read_csv("data/planted_defects.csv")
EXPECTED = dict(zip(PLANTED["rule_id"], PLANTED["expected_count"]))


@pytest.fixture(scope="module")
def planted_con():
    return connect()  # the committed CSVs


@pytest.fixture(scope="module")
def clean_con():
    return connect(generate_clean())


def test_every_rule_has_sql_and_expected_count():
    sql_files = {p.stem for p in SQL_DIR.glob("*.sql")}
    assert sql_files == set(RULES)
    assert set(EXPECTED) == set(RULES)


@pytest.mark.parametrize("rule_id", sorted(EXPECTED))
def test_rule_catches_planted_defects(planted_con, rule_id):
    found = run_rule(planted_con, rule_id)
    assert len(found) == EXPECTED[rule_id], found.to_string()


@pytest.mark.parametrize("rule_id", sorted(RULES))
def test_clean_data_has_no_exceptions(clean_con, rule_id):
    found = run_rule(clean_con, rule_id)
    assert found.empty, found.to_string()


def test_results_have_standard_shape(planted_con):
    results = run_all(planted_con)
    assert list(results.columns) == RESULT_COLUMNS
    assert set(results["severity"]) <= set(SEVERITIES)
    assert results["issue"].str.len().gt(0).all()
    assert results["suggested_action"].str.len().gt(0).all()
    # Time & Payroll rules always say which period the exception belongs to.
    tp = results[results["rule_id"].str.startswith("TP")]
    assert tp["period_id"].notna().all()


# --- Boundary checks on tiny fixtures --------------------------------------

PERIOD = pd.DataFrame([{"period_id": "PP01", "start_date": "2026-01-05",
                        "end_date": "2026-01-18", "pay_date": "2026-01-23"}])


def test_tp04_allows_exactly_16_and_zero_hours():
    time_entries = pd.DataFrame([
        {"emp_id": 1, "work_date": "2026-01-05", "hours": 16.0, "attendance_type": "Regular"},
        {"emp_id": 1, "work_date": "2026-01-06", "hours": 0.0, "attendance_type": "Regular"},
        {"emp_id": 1, "work_date": "2026-01-07", "hours": 16.5, "attendance_type": "Regular"},
        {"emp_id": 1, "work_date": "2026-01-08", "hours": -0.5, "attendance_type": "Regular"},
    ])
    found = run_rule(connect({"time_entries": time_entries, "pay_periods": PERIOD}), "TP-04")
    assert len(found) == 2
    assert set(found["period_id"]) == {"PP01"}


@pytest.mark.parametrize("paid_hours, flagged", [(80.5, False), (79.5, False), (80.6, True), (79.4, True)])
def test_tp01_flags_only_variance_over_half_hour(paid_hours, flagged):
    time_entries = pd.DataFrame([{"emp_id": 1, "work_date": "2026-01-05", "hours": 80.0,
                                  "attendance_type": "Regular"}])
    payroll = pd.DataFrame([{"period_id": "PP01", "emp_id": 1, "wage_type": "1000",
                             "hours": paid_hours, "amount": 100.0, "payment_date": "2026-01-23"}])
    con = connect({"time_entries": time_entries, "payroll_results": payroll, "pay_periods": PERIOD})
    assert len(run_rule(con, "TP-01")) == int(flagged)


@pytest.mark.parametrize("payment_date, flagged", [("2026-01-22", False), ("2026-01-23", False), ("2026-01-24", True)])
def test_tp06_allows_payment_on_term_date(payment_date, flagged):
    employees = pd.DataFrame([{"emp_id": 1, "status": "Terminated", "term_date": date(2026, 1, 23)}])
    payroll = pd.DataFrame([{"period_id": "PP01", "emp_id": 1, "wage_type": "1000",
                             "hours": 8.0, "amount": 100.0, "payment_date": payment_date}])
    assert len(run_rule(connect({"employees": employees, "payroll_results": payroll}), "TP-06")) == int(flagged)


def test_unknown_column_fails_loudly():
    with pytest.raises(ValueError, match="Unknown column"):
        connect({"employees": pd.DataFrame([{"emp_id": 1, "employee_status": "Active"}])})
