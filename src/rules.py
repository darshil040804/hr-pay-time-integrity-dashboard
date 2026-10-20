"""Load tables into DuckDB and run the validation rules.

Each rule is a plain SQL file in sql/<RULE_ID>.sql. Every rule returns the
same columns (RESULT_COLUMNS), one row per exception.

Typical use:
    con = connect()                 # the committed CSVs in data/
    exceptions = run_all(con)

    con = connect(my_tables)        # any {table: DataFrame}, e.g. a tiny test fixture
    run_rule(con, "TP-04")

Tables missing from the input are created empty, and missing columns are
filled with blanks, so a fixture only needs the rows a rule actually reads.
"""

from pathlib import Path

import duckdb
import pandas as pd

from src.schema import SCHEMA, coerce

ROOT = Path(__file__).resolve().parent.parent
SQL_DIR = ROOT / "sql"
DATA_DIR = ROOT / "data"

RESULT_COLUMNS = ["rule_id", "severity", "emp_id", "period_id", "issue", "suggested_action"]
SEVERITIES = ["High", "Medium", "Low"]

# Plain-English description of every rule. The SQL file is the definition;
# this is what the dashboard and the AI scripts show.
RULES = {
    "OP-01": ("Org & Personnel", "Employee assigned to an inactive position"),
    "OP-02": ("Org & Personnel", "Position with missing or nonexistent org unit"),
    "OP-03": ("Org & Personnel", "Two active employees in the same position"),
    "OP-04": ("Org & Personnel", "Terminated employee still assigned to an active position past term date"),
    "OP-05": ("Org & Personnel", "Employee subgroup inconsistent with job FLSA status"),
    "TP-01": ("Time & Payroll", "Paid hours differ from recorded time hours by more than 0.5 for the period"),
    "TP-02": ("Time & Payroll", "Overtime wage type paid to an Exempt employee"),
    "TP-03": ("Time & Payroll", "Active hourly employee paid with no time entries in the period"),
    "TP-04": ("Time & Payroll", "Daily hours over 16 or negative"),
    "TP-05": ("Time & Payroll", "Duplicate payroll line: same employee, period, wage type"),
    "TP-06": ("Time & Payroll", "Payment dated after the employee's term date"),
}

_DUCKDB_TYPES = {"string": "VARCHAR", "int": "BIGINT", "float": "DOUBLE", "date": "DATE"}


def load_csv_tables(data_dir: Path = DATA_DIR) -> dict[str, pd.DataFrame]:
    """Read every table's CSV from data_dir, with schema types applied."""
    tables = {}
    for name in SCHEMA:
        raw = pd.read_csv(data_dir / f"{name}.csv", dtype=str, keep_default_na=False, na_values=[""])
        tables[name] = coerce(raw, name)
    return tables


def load_tables(con: duckdb.DuckDBPyConnection, tables: dict[str, pd.DataFrame]) -> None:
    """Create every schema table in con and fill it from `tables`.

    Raises ValueError for an unknown table or column name, so a typo in a
    test fixture fails loudly instead of being silently ignored.
    """
    unknown = set(tables) - set(SCHEMA)
    if unknown:
        raise ValueError(f"Unknown table(s): {sorted(unknown)}")

    for name, columns in SCHEMA.items():
        df = tables.get(name, pd.DataFrame())
        bad_columns = set(df.columns) - set(columns)
        if bad_columns:
            raise ValueError(f"Unknown column(s) in {name}: {sorted(bad_columns)}")

        ddl = ", ".join(f"{col} {_DUCKDB_TYPES[kind]}" for col, kind in columns.items())
        con.execute(f"CREATE OR REPLACE TABLE {name} ({ddl})")
        con.register("_incoming", coerce(df, name))
        con.execute(f"INSERT INTO {name} SELECT * FROM _incoming")
        con.unregister("_incoming")


def connect(tables: dict[str, pd.DataFrame] | None = None) -> duckdb.DuckDBPyConnection:
    """Return an in-memory DuckDB connection loaded with `tables` (default: the CSVs)."""
    con = duckdb.connect()
    load_tables(con, load_csv_tables() if tables is None else tables)
    return con


def rule_sql(rule_id: str) -> str:
    if rule_id not in RULES:
        raise KeyError(f"Unknown rule: {rule_id}")
    return (SQL_DIR / f"{rule_id}.sql").read_text(encoding="utf-8")


def run_rule(con: duckdb.DuckDBPyConnection, rule_id: str) -> pd.DataFrame:
    """Run one rule and return its exceptions (columns = RESULT_COLUMNS)."""
    result = con.sql(rule_sql(rule_id)).df()
    return result[RESULT_COLUMNS].astype({"emp_id": "Int64"})


def run_all(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Run every rule and return all exceptions in one DataFrame."""
    return pd.concat([run_rule(con, rule_id) for rule_id in RULES], ignore_index=True)
