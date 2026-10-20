"""Executable versions of the scenarios in docs/test_scenarios.md.

Test IDs match the document, so each row's Actual Result comes from this file.

- TS-<rule>-01 (must flag): runs the real dashboard page with Streamlit's
  AppTest on the committed data, applies the documented filters, and checks
  the exception table.
- TS-<rule>-02 (must not flag): builds a tiny fixture for the boundary case
  and checks the rule returns nothing. A control variant that crosses the
  boundary must flag, proving the fixture really exercises the rule.
"""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from src.edge_cases import build_tables_from_records
from src.rules import connect, load_csv_tables, run_rule

PAGES = Path(__file__).resolve().parent.parent / "pages"
OP_PAGE, TP_PAGE = str(PAGES / "1_Org_Personnel.py"), str(PAGES / "2_Time_Payroll.py")

# Test ID: (page, rule filter, pay period or None, rows expected after filtering, text expected in an Issue)
DASHBOARD_SCENARIOS = {
    "TS-OP-01-01": (OP_PAGE, "OP-01", None, 6, "(100058) is assigned to position POS0058, which is inactive"),
    "TS-OP-02-01": (OP_PAGE, "OP-02", None, 4, "Position POS0482 has no org unit"),
    "TS-OP-03-01": (OP_PAGE, "OP-03", None, 3, "(100017) shares position POS0046 with employee 100046"),
    "TS-OP-04-01": (OP_PAGE, "OP-04", None, 5, "(100476) was terminated on 2025-07-14 but still holds active position POS0495"),
    "TS-OP-05-01": (OP_PAGE, "OP-05", None, 5, '(100123) is Salaried but job "Student Services Coordinator" is Non-exempt'),
    "TS-TP-01-01": (TP_PAGE, "TP-01", "PP01", 3, "Employee 100088 was paid for 91.0 hours in PP01 but recorded 83.0 hours"),
    "TS-TP-02-01": (TP_PAGE, "TP-02", "PP01", 1, 'Employee 100205 received 4.0 hours of overtime ($241.68) in PP01, but job "IT Analyst" is Exempt'),
    "TS-TP-03-01": (TP_PAGE, "TP-03", "PP03", 2, "Hourly employee 100047 was paid 61.5 hours in PP03 with no time entries"),
    "TS-TP-04-01": (TP_PAGE, "TP-04", "PP06", 3, "Employee 100109 recorded 18.0 hours of Regular on 2026-03-17"),
    "TS-TP-05-01": (TP_PAGE, "TP-05", "PP01", 2, "Employee 100021 has 2 payroll lines for wage type 1400"),
    "TS-TP-06-01": (TP_PAGE, "TP-06", "PP02", 1, "Employee 100484 was terminated on 2025-07-08 but received $800.00"),
}


@pytest.mark.parametrize("test_id", DASHBOARD_SCENARIOS)
def test_dashboard_scenario(test_id):
    page, rule_id, period, expected_rows, expected_issue = DASHBOARD_SCENARIOS[test_id]
    at = AppTest.from_file(page, default_timeout=60).run()
    if period:
        at.selectbox[0].set_value(period).run()
    at.multiselect(key="op_rule" if page == OP_PAGE else "tp_rule").set_value([rule_id]).run()
    assert not at.exception

    table = at.dataframe[-1].value  # the exception table is the last table on the page
    assert set(table["Rule"]) == {rule_id}
    assert len(table) == expected_rows
    assert table["Issue"].str.contains(expected_issue, regex=False).any()


# Test ID: (rule, build_records(value), value that must NOT flag, control value that MUST flag)
def _op_01(status):
    return {"positions": [{"position_id": "POS0101", "status": "Inactive", "valid_to": "2025-12-31"}],
            "employees": [{"emp_id": 100102, "position_id": "POS0101", "status": status,
                           "term_date": "2025-12-01" if status == "Terminated" else None}]}


def _op_02(org_unit_id):
    return {"positions": [{"position_id": "POS0201", "org_unit_id": org_unit_id}]}


def _op_03(second_status):
    return {"positions": [{"position_id": "POS0301"}],
            "employees": [{"emp_id": 100203, "position_id": "POS0301", "hire_date": "2025-03-01"},
                          {"emp_id": 100204, "position_id": "POS0301", "hire_date": "2025-06-01",
                           "status": second_status,
                           "term_date": "2025-12-01" if second_status == "Terminated" else None}]}


def _op_04(term_date):
    return {"positions": [{"position_id": "POS0401", "status": "Active"}],
            "employees": [{"emp_id": 100302, "position_id": "POS0401", "status": "Terminated",
                           "term_date": term_date}]}


def _op_05(subgroup):  # JOB01 Professor is Exempt
    return {"positions": [{"position_id": "POS0501", "job_id": "JOB01"}],
            "employees": [{"emp_id": 100402, "position_id": "POS0501", "employee_group": "Faculty",
                           "employee_subgroup": subgroup}]}


def _tp_01(paid_hours):  # PP03 = 2026-02-02 to 2026-02-15; 5 x 8h recorded = 40.0
    return {"time_entries": [{"emp_id": 100102, "work_date": f"2026-02-0{d}", "hours": 8.0} for d in range(2, 7)],
            "payroll_results": [{"period_id": "PP03", "emp_id": 100102, "wage_type": "1000",
                                 "hours": paid_hours, "payment_date": "2026-02-20"}]}


def _tp_02(job_id):  # JOB06 Payroll Specialist is Non-exempt, JOB01 Professor is Exempt
    return {"positions": [{"position_id": "POS0601", "job_id": job_id}],
            "employees": [{"emp_id": 100202, "position_id": "POS0601"}],
            "payroll_results": [{"period_id": "PP04", "emp_id": 100202, "wage_type": "1100",
                                 "hours": 5.0, "payment_date": "2026-03-06"}]}


def _tp_03(work_date):  # PP05 = 2026-03-02 to 2026-03-15
    return {"employees": [{"emp_id": 100302, "employee_subgroup": "Hourly"}],
            "time_entries": [{"emp_id": 100302, "work_date": work_date, "hours": 12.0},
                             {"emp_id": 100302, "work_date": work_date, "hours": 8.0, "attendance_type": "Overtime"}],
            "payroll_results": [{"period_id": "PP05", "emp_id": 100302, "wage_type": "1000",
                                 "hours": 20.0, "payment_date": "2026-03-20"}]}


def _tp_04(hours):
    return {"time_entries": [{"emp_id": 100402, "work_date": "2026-02-11", "hours": hours}]}


def _tp_05(lines):
    return {"payroll_results": [{"period_id": "PP05", "emp_id": 100404, "wage_type": "1200",
                                 "hours": 8.0, "payment_date": "2026-03-20"}] * lines}


def _tp_06(payment_date):
    return {"employees": [{"emp_id": 100406, "status": "Terminated", "position_id": None,
                           "term_date": "2026-02-15"}],
            "payroll_results": [{"period_id": "PP03", "emp_id": 100406, "payment_date": payment_date}]}


FIXTURE_SCENARIOS = {
    "TS-OP-01-02": ("OP-01", _op_01, "Terminated", "Active"),
    "TS-OP-02-02": ("OP-02", _op_02, "ORG010", "ORG999"),
    "TS-OP-03-02": ("OP-03", _op_03, "Terminated", "Active"),
    "TS-OP-04-02": ("OP-04", _op_04, "2026-04-01", "2026-03-01"),
    "TS-OP-05-02": ("OP-05", _op_05, "Salaried", "Hourly"),
    "TS-TP-01-02": ("TP-01", _tp_01, 40.4, 40.6),
    "TS-TP-02-02": ("TP-02", _tp_02, "JOB06", "JOB01"),
    "TS-TP-03-02": ("TP-03", _tp_03, "2026-03-05", "2026-02-20"),
    "TS-TP-04-02": ("TP-04", _tp_04, 16.0, 16.5),
    "TS-TP-05-02": ("TP-05", _tp_05, 1, 2),
    "TS-TP-06-02": ("TP-06", _tp_06, "2026-02-15", "2026-02-16"),
}


@pytest.fixture(scope="module")
def reference():
    return load_csv_tables()


@pytest.mark.parametrize("test_id", FIXTURE_SCENARIOS)
def test_fixture_scenario(test_id, reference):
    rule_id, build, not_flagged_value, control_value = FIXTURE_SCENARIOS[test_id]

    def found(value):
        return run_rule(connect(build_tables_from_records(build(value), reference)), rule_id)

    assert found(not_flagged_value).empty, "boundary case must not be flagged"
    assert len(found(control_value)) == 1, "control case (boundary crossed) must be flagged"
