"""Shared helpers for the Streamlit pages: cached data, Excel export, chart styling.

The app reads the committed CSVs only. It makes no AI or network calls.
"""

import io
import re

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.rules import RULES, connect, load_csv_tables, rule_sql, run_all

REPO_URL = "https://github.com/darshil040804/hr-pay-time-integrity-dashboard"
DOCS = {
    "Functional Design Specification": "docs/FDS.md",
    "Test scenarios": "docs/test_scenarios.md",
    "AI testing log": "docs/ai_testing_log.md",
    "User guide": "docs/user_guide.md",
    "Data dictionary": "docs/data_dictionary.md",
}
SEVERITY_ORDER = ["High", "Medium", "Low"]
DISCLAIMER = (
    "All data in this app is synthetic and fictional. It is modeled on SAP HCM "
    "structures but does not use real SAP systems or real employee data."
)

# Categorical colors in fixed order (validated for color-vision deficiency).
# Each rule keeps the same color on every chart.
_SERIES_LIGHT = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]
_SERIES_DARK = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300"]


def doc_url(path: str) -> str:
    return f"{REPO_URL}/blob/main/{path}"


def _dark_theme() -> bool:
    theme = getattr(st.context, "theme", None)
    return theme is not None and theme.type == "dark"


def series_colors() -> list[str]:
    """Categorical colors for the active Streamlit theme."""
    return _SERIES_DARK if _dark_theme() else _SERIES_LIGHT


def surface_color() -> str:
    """Streamlit's page background, used for the thin gap between stacked bar segments."""
    return "#0e1117" if _dark_theme() else "#ffffff"


def rule_colors() -> dict[str, str]:
    """Fixed color per rule: OP-01..05 and TP-01..06 each map to slots 1..6."""
    colors = series_colors()
    return {rule_id: colors[int(rule_id[-1]) - 1] for rule_id in RULES}


def rule_severity(rule_id: str) -> str:
    """Read a rule's severity from its SQL file (the single definition)."""
    return re.search(r"'(High|Medium|Low)' AS severity", rule_sql(rule_id)).group(1)


def rule_catalog() -> pd.DataFrame:
    return pd.DataFrame(
        [(rule_id, category, title, rule_severity(rule_id)) for rule_id, (category, title) in RULES.items()],
        columns=["Rule", "Area", "Check", "Severity"],
    )


# --- Cached data ------------------------------------------------------------

@st.cache_data
def get_tables() -> dict[str, pd.DataFrame]:
    return load_csv_tables()


@st.cache_data
def get_exceptions() -> pd.DataFrame:
    """All rule exceptions, with employee name and org unit added for display."""
    tables = get_tables()
    exceptions = run_all(connect(tables))

    emp = tables["employees"][["emp_id", "first_name", "last_name", "position_id"]]
    org = (tables["positions"][["position_id", "org_unit_id"]]
           .merge(tables["org_units"][["org_unit_id", "name"]], on="org_unit_id", how="left"))
    people = emp.merge(org, on="position_id", how="left")
    people["employee_name"] = people["first_name"] + " " + people["last_name"]

    out = exceptions.merge(people[["emp_id", "employee_name", "name"]], on="emp_id", how="left")
    out = out.rename(columns={"name": "org_unit"})
    out["org_unit"] = out["org_unit"].fillna("(no org unit)")
    out["check"] = out["rule_id"].map(lambda r: RULES[r][1])
    return out


@st.cache_data
def get_hours_by_period() -> pd.DataFrame:
    """Recorded vs paid hours per pay period (same definition as rule TP-01)."""
    con = connect(get_tables())
    return con.sql("""
        WITH recorded AS (
            SELECT pp.period_id, sum(t.hours) AS recorded_hours
            FROM time_entries t
            JOIN pay_periods pp ON t.work_date BETWEEN pp.start_date AND pp.end_date
            GROUP BY pp.period_id
        ),
        paid AS (
            SELECT period_id, sum(hours) AS paid_hours
            FROM payroll_results
            WHERE wage_type IN ('1000', '1100', '1200', '1300')
            GROUP BY period_id
        )
        SELECT pp.period_id, pp.start_date, pp.end_date,
               coalesce(recorded_hours, 0) AS recorded_hours,
               coalesce(paid_hours, 0) AS paid_hours,
               coalesce(paid_hours, 0) - coalesce(recorded_hours, 0) AS difference
        FROM pay_periods pp
        LEFT JOIN recorded USING (period_id)
        LEFT JOIN paid USING (period_id)
        ORDER BY pp.period_id
    """).df()


# --- Display helpers ---------------------------------------------------------

DISPLAY_COLUMNS = {
    "rule_id": "Rule", "severity": "Severity", "emp_id": "Employee ID", "employee_name": "Name",
    "org_unit": "Org unit", "period_id": "Period", "issue": "Issue", "suggested_action": "Suggested action",
}


def display_table(exceptions: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Exceptions sorted by severity, with friendly column names."""
    order = exceptions["severity"].map({s: i for i, s in enumerate(SEVERITY_ORDER)})
    sorted_ = exceptions.assign(_order=order).sort_values(["_order", "rule_id", "emp_id"]).drop(columns="_order")
    return sorted_[columns].rename(columns=DISPLAY_COLUMNS)


def multiselect_filter(df: pd.DataFrame, column: str, label: str, options: list[str], key: str) -> pd.DataFrame:
    """A multiselect where an empty selection means 'all'."""
    chosen = st.multiselect(label, options, placeholder="All", key=key)
    return df[df[column].isin(chosen)] if chosen else df


def to_excel(df: pd.DataFrame, sheet_name: str) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name=sheet_name, index=False)
        sheet = writer.sheets[sheet_name]
        for column_cells in sheet.columns:
            width = max(len(str(cell.value or "")) for cell in column_cells)
            sheet.column_dimensions[column_cells[0].column_letter].width = min(width + 2, 80)
    return buffer.getvalue()


def excel_download(df: pd.DataFrame, file_name: str, sheet_name: str) -> None:
    st.download_button(
        "Download Excel", data=to_excel(df, sheet_name), file_name=file_name,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        disabled=df.empty,
    )


def style_figure(fig: go.Figure, height: int = 360) -> go.Figure:
    """Shared chart styling: thin rounded bars, recessive grid, legend on top."""
    fig.update_traces(selector=dict(type="bar"), marker_cornerradius=4)
    fig.update_layout(
        height=height, margin=dict(l=8, r=8, t=8, b=8), bargap=0.35, bargroupgap=0.08,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, title_text=""),
        hoverlabel=dict(namelength=-1),
    )
    return fig


def disclaimer() -> None:
    st.caption(DISCLAIMER)
