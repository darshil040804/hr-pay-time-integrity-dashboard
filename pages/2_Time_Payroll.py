import plotly.graph_objects as go
import streamlit as st

from src.dashboard import (SEVERITY_ORDER, disclaimer, display_table, excel_download, get_exceptions,
                           get_hours_by_period, multiselect_filter, series_colors, style_figure)
from src.rules import RULES

st.set_page_config(page_title="Time & Payroll Reconciliation", layout="wide")
st.title("Time & Payroll Reconciliation")
st.write(
    "Compares the hours employees recorded with the hours payroll paid, and checks "
    "each pay line for errors such as overtime paid to exempt staff, duplicate lines, "
    "and payments after termination."
)
disclaimer()

hours = get_hours_by_period()
tp_rules = [r for r in RULES if r.startswith("TP")]
exceptions = get_exceptions()
exceptions = exceptions[exceptions["rule_id"].isin(tp_rules)]

period_labels = {"All": "All pay periods"} | {
    row.period_id: f"{row.period_id} ({row.start_date:%b %d} to {row.end_date:%b %d, %Y})"
    for row in hours.itertuples()
}
period = st.selectbox("Pay period", list(period_labels), format_func=period_labels.get)

# Totals for the selected period
selected_hours = hours if period == "All" else hours[hours["period_id"] == period]
selected_exceptions = exceptions if period == "All" else exceptions[exceptions["period_id"] == period]
c1, c2, c3, c4 = st.columns(4)
c1.metric("Hours recorded", f"{selected_hours['recorded_hours'].sum():,.1f}")
c2.metric("Hours paid", f"{selected_hours['paid_hours'].sum():,.1f}")
c3.metric("Paid minus recorded", f"{selected_hours['difference'].sum():+,.1f}")
c4.metric("Exceptions", len(selected_exceptions))
st.caption("Paid hours count regular, overtime, vacation, and sick pay. Shift differential is a "
           "premium on hours already paid, so it is not counted.")

# Recorded vs paid hours per period
colors = series_colors()
fig = go.Figure()
for column, name, color in [("recorded_hours", "Recorded", colors[0]), ("paid_hours", "Paid", colors[1])]:
    fig.add_bar(
        x=hours["period_id"], y=hours[column], name=name, marker_color=color,
        customdata=hours["difference"],
        hovertemplate=f"%{{x}}<br>{name}: %{{y:,.1f}} h<br>Paid minus recorded: %{{customdata:+,.1f}} h<extra></extra>",
    )
fig.update_yaxes(title_text="Hours", rangemode="tozero")
fig.update_layout(barmode="group")

# The totals are close, so the gap gets its own chart.
diff = go.Figure(go.Bar(
    x=hours["period_id"], y=hours["difference"], marker_color=colors[1],
    text=[f"{d:+,.1f}" for d in hours["difference"]], textposition="outside", cliponaxis=False,
    hovertemplate="%{x}<br>Paid minus recorded: %{y:+,.1f} h<extra></extra>",
))
diff.update_yaxes(title_text="Paid minus recorded (hours)", zeroline=True)

st.subheader("Hours recorded vs paid, by pay period")
left, right = st.columns(2)
left.plotly_chart(style_figure(fig), width="stretch", theme="streamlit")
right.plotly_chart(style_figure(diff), width="stretch", theme="streamlit")
st.caption("Positive difference: payroll paid more hours than were recorded (for example, pay with no "
           "time sheet). Totals net out over- and under-payments, so see the exception table for details.")
with st.expander("View chart data"):
    st.dataframe(
        hours[["period_id", "recorded_hours", "paid_hours", "difference"]].rename(columns={
            "period_id": "Period", "recorded_hours": "Hours recorded",
            "paid_hours": "Hours paid", "difference": "Paid minus recorded"}),
        hide_index=True, width="stretch",
    )

# Exception table
st.subheader("Exception details")
c1, c2 = st.columns(2)
with c1:
    filtered = multiselect_filter(selected_exceptions, "rule_id", "Rule", tp_rules, key="tp_rule")
with c2:
    filtered = multiselect_filter(filtered, "severity", "Severity", SEVERITY_ORDER, key="tp_severity")

table = display_table(filtered, ["rule_id", "severity", "period_id", "emp_id", "employee_name",
                                 "issue", "suggested_action"])
st.caption(f"{len(table)} of {len(exceptions)} exceptions shown")
st.dataframe(table, hide_index=True, width="stretch")
suffix = "all_periods" if period == "All" else period
excel_download(table, f"time_payroll_exceptions_{suffix}.xlsx", "Time & Payroll")
