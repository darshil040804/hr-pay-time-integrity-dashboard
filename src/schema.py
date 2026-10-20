"""Column names and data types for every table.

This is the single definition of the data model. The generator, the rules,
the tests, and the AI scripts all import it, so a column is only ever
renamed in one place.

Type names:
    "string" - text (IDs, names, codes). Missing values allowed.
    "int"    - whole number. Missing values allowed.
    "float"  - decimal number (hours, amounts).
    "date"   - calendar date, stored in CSV as YYYY-MM-DD.
"""

from datetime import date

import pandas as pd

SCHEMA = {
    "org_units": {
        "org_unit_id": "string",
        "name": "string",
        "parent_org_unit_id": "string",
        "valid_from": "date",
        "valid_to": "date",
    },
    "jobs": {
        "job_id": "string",
        "title": "string",
        "flsa_status": "string",
    },
    "positions": {
        "position_id": "string",
        "org_unit_id": "string",
        "job_id": "string",
        "status": "string",
        "valid_from": "date",
        "valid_to": "date",
    },
    "employees": {
        "emp_id": "int",
        "first_name": "string",
        "last_name": "string",
        "position_id": "string",
        "employee_group": "string",
        "employee_subgroup": "string",
        "weekly_scheduled_hours": "float",
        "status": "string",
        "hire_date": "date",
        "term_date": "date",
    },
    "wage_types": {
        "wage_type": "string",
        "description": "string",
        "eligible_flsa": "string",
    },
    "pay_periods": {
        "period_id": "string",
        "start_date": "date",
        "end_date": "date",
        "pay_date": "date",
    },
    "time_entries": {
        "emp_id": "int",
        "work_date": "date",
        "hours": "float",
        "attendance_type": "string",
    },
    "payroll_results": {
        "period_id": "string",
        "emp_id": "int",
        "wage_type": "string",
        "hours": "float",
        "amount": "float",
        "payment_date": "date",
    },
}

# Allowed values for coded columns.
ALLOWED_VALUES = {
    ("jobs", "flsa_status"): ["Exempt", "Non-exempt"],
    ("positions", "status"): ["Active", "Inactive"],
    ("employees", "employee_group"): ["Faculty", "Support Staff", "Temporary"],
    ("employees", "employee_subgroup"): ["Salaried", "Hourly"],
    ("employees", "status"): ["Active", "Terminated"],
    ("time_entries", "attendance_type"): ["Regular", "Overtime", "Vacation", "Sick"],
}

# "Open-ended" end date, as in SAP (record is valid until further notice).
END_OF_TIME = "9999-12-31"

_PANDAS_TYPES = {"string": "string", "int": "Int64", "float": "float64"}


def to_date(value):
    """Convert a string, Timestamp, or date to a datetime.date (None if missing).

    Dates are kept as plain datetime.date objects rather than pandas
    timestamps because 9999-12-31 is outside the pandas timestamp range.
    DuckDB reads these columns as DATE.
    """
    if value is None or (not isinstance(value, date) and pd.isna(value)):
        return None
    if isinstance(value, str):
        return date.fromisoformat(value[:10])
    if isinstance(value, pd.Timestamp):
        return value.date()
    return value


def coerce(df: pd.DataFrame, table: str) -> pd.DataFrame:
    """Return df with exactly the table's columns, in order, with correct types.

    Missing columns are added as empty. Raises KeyError for an unknown table.
    """
    columns = SCHEMA[table]
    out = df.reindex(columns=list(columns)).copy()
    for col, kind in columns.items():
        if kind == "date":
            out[col] = out[col].map(to_date).astype("object")
        else:
            out[col] = out[col].astype(_PANDAS_TYPES[kind])
    return out
