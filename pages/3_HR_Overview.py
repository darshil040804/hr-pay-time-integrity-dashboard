import plotly.graph_objects as go
import streamlit as st

from src.dashboard import (disclaimer, get_exceptions, get_tables, rule_colors, series_colors, style_figure,
                           surface_color)
from src.rules import RULES

st.set_page_config(page_title="HR Overview", layout="wide")
st.title("HR Overview")
st.write("Workforce and data-quality KPIs across the whole organization.")
disclaimer()

tables = get_tables()
employees, positions, org_units = tables["employees"], tables["positions"], tables["org_units"]
exceptions = get_exceptions()

# KPIs
active_emps = employees[employees["status"] == "Active"]
active_positions = positions[positions["status"] == "Active"]
vacant = ~active_positions["position_id"].isin(active_emps["position_id"])
emps_with_exception = exceptions["emp_id"].dropna().nunique()

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Headcount", len(active_emps), help="Active employees.")
c2.metric("Active positions", len(active_positions))
c3.metric("Vacancy rate", f"{vacant.mean():.1%}", help="Active positions with no active employee in them.")
c4.metric("Total exceptions", len(exceptions))
c5.metric("Employees with any exception", f"{emps_with_exception / len(employees):.1%}",
          help=f"{emps_with_exception} of {len(employees)} employees (active and terminated) "
               "appear in at least one exception.")

# Headcount by org unit
headcount = (active_emps.merge(positions[["position_id", "org_unit_id"]], on="position_id", how="left")
             .merge(org_units[["org_unit_id", "name"]], on="org_unit_id", how="left")
             .assign(name=lambda d: d["name"].fillna("(no org unit)"))
             .groupby("name").size().sort_values(ascending=False))
fig = go.Figure(go.Bar(
    x=headcount.values, y=headcount.index, orientation="h", marker_color=series_colors()[0],
    text=headcount.values, textposition="outside", cliponaxis=False,
    hovertemplate="%{y}<br>%{x} active employees<extra></extra>",
))
fig.update_yaxes(autorange="reversed")
fig.update_xaxes(title_text="Active employees", rangemode="tozero")
st.subheader("Headcount by org unit")
st.plotly_chart(style_figure(fig, height=max(400, 22 * len(headcount))), width="stretch", theme="streamlit")

# Exceptions by rule over pay periods (Time & Payroll rules are period-based)
st.subheader("Exceptions by rule over pay periods")
tp = exceptions[exceptions["rule_id"].str.startswith("TP")]
periods = list(tables["pay_periods"]["period_id"])
tp_rules = [r for r in RULES if r.startswith("TP")]
by_period = (tp.groupby(["period_id", "rule_id"]).size().unstack(fill_value=0)
             .reindex(index=periods, columns=tp_rules, fill_value=0))
colors = rule_colors()
fig = go.Figure()
for rule_id in tp_rules:
    fig.add_bar(
        x=periods, y=by_period[rule_id], name=f"{rule_id} {RULES[rule_id][1]}", marker_color=colors[rule_id],
        marker_line=dict(width=2, color=surface_color()),
        hovertemplate=f"%{{x}}<br>{rule_id}: %{{y}} exceptions<extra></extra>",
    )
fig = style_figure(fig, height=440)
fig.update_traces(marker_cornerradius=0)
fig.update_layout(barmode="stack", legend_traceorder="normal")
fig.update_yaxes(title_text="Exceptions", rangemode="tozero", dtick=1)
st.plotly_chart(fig, width="stretch", theme="streamlit")
st.caption("Org & Personnel rules check the current state of the org structure rather than a pay "
           f"period, so they are not shown here ({len(exceptions) - len(tp)} exceptions).")
with st.expander("View chart data"):
    st.dataframe(by_period.rename_axis("Period").reset_index(), hide_index=True, width="stretch")
