import streamlit as st

from src.dashboard import DISCLAIMER, DOCS, REPO_URL, SEVERITY_ORDER, doc_url, get_exceptions

st.set_page_config(page_title="HR Pay & Time Integrity Dashboard", layout="wide")

st.title("HR Pay & Time Integrity Dashboard")

st.write(
    "This dashboard validates and reconciles HR data across organizational "
    "management, personnel administration, time management, and payroll. "
    "The dataset contains deliberately planted defects, such as employees in "
    "inactive positions, overtime paid to exempt staff, and paid hours that "
    "don't match recorded time. Documented SQL rules catch each defect, and "
    "automated tests confirm every one is found."
)

st.info(DISCLAIMER)

exceptions = get_exceptions()
counts = exceptions["severity"].value_counts()

st.subheader("Open exceptions")
cols = st.columns(4)
cols[0].metric("Total", len(exceptions))
for col, severity in zip(cols[1:], SEVERITY_ORDER):
    col.metric(f"{severity} severity", int(counts.get(severity, 0)))

st.subheader("Where to look")
st.page_link("pages/1_Org_Personnel.py", label="Org & Personnel Integrity: positions, assignments, FLSA consistency")
st.page_link("pages/2_Time_Payroll.py", label="Time & Payroll Reconciliation: recorded vs paid hours, pay errors")
st.page_link("pages/3_HR_Overview.py", label="HR Overview: headcount, vacancies, exception trends")
st.page_link("pages/5_About.py", label="About: how the rules work and how to read the dashboard")

st.subheader("Project links")
st.markdown(f"- [GitHub repository]({REPO_URL})\n" + "\n".join(f"- [{name}]({doc_url(path)})" for name, path in DOCS.items()))
