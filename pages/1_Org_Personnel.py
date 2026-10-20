import plotly.graph_objects as go
import streamlit as st

from src.dashboard import (SEVERITY_ORDER, disclaimer, display_table, excel_download, get_exceptions,
                           multiselect_filter, series_colors, style_figure)
from src.rules import RULES

st.set_page_config(page_title="Org & Personnel Integrity", layout="wide")
st.title("Org & Personnel Integrity")
st.write(
    "Checks on the org structure and employee assignments: positions, org units, "
    "who holds which position, and whether each employee's pay classification "
    "matches their job."
)
disclaimer()

op_rules = [r for r in RULES if r.startswith("OP")]
exceptions = get_exceptions()
exceptions = exceptions[exceptions["rule_id"].isin(op_rules)]

# Exceptions per rule
counts = exceptions["rule_id"].value_counts().reindex(op_rules, fill_value=0)
labels = [f"{r}  {RULES[r][1]}" for r in op_rules]
fig = go.Figure(go.Bar(
    x=counts.values, y=labels, orientation="h", marker_color=series_colors()[0],
    text=counts.values, textposition="outside", cliponaxis=False,
    hovertemplate="%{y}<br>%{x} exceptions<extra></extra>",
))
fig.update_yaxes(autorange="reversed")
fig.update_xaxes(title_text="Exceptions", rangemode="tozero")
st.subheader("Exceptions by rule")
st.plotly_chart(style_figure(fig, height=300), width="stretch", theme="streamlit")

# Filterable table
st.subheader("Exception details")
c1, c2, c3 = st.columns(3)
with c1:
    filtered = multiselect_filter(exceptions, "rule_id", "Rule", op_rules, key="op_rule")
with c2:
    filtered = multiselect_filter(filtered, "severity", "Severity", SEVERITY_ORDER, key="op_severity")
with c3:
    filtered = multiselect_filter(filtered, "org_unit", "Org unit", sorted(exceptions["org_unit"].unique()),
                                  key="op_org")

table = display_table(filtered, ["rule_id", "severity", "emp_id", "employee_name", "org_unit",
                                 "issue", "suggested_action"])
st.caption(f"{len(table)} of {len(exceptions)} exceptions shown")
st.dataframe(table, hide_index=True, width="stretch")
excel_download(table, "org_personnel_exceptions.xlsx", "Org & Personnel")
