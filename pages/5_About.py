import streamlit as st

from src.dashboard import DOCS, REPO_URL, disclaimer, doc_url, rule_catalog

st.set_page_config(page_title="About", layout="wide")
st.title("About")
disclaimer()

st.header("How the rules work")
st.write(
    "The data is a fictional university's HR records, built to resemble SAP HCM: "
    "org units, jobs, and positions (Organizational Management), employee records "
    "(Personnel Administration), daily time entries (Time Management), and payroll "
    "results by wage type (Payroll). A generator builds a fully consistent dataset, "
    "then plants a known number of defects."
)
st.write(
    "Each validation rule is a short SQL query stored in its own file in the `sql/` "
    "folder. The app loads the data into an in-memory DuckDB database and runs every "
    "rule. Each exception it returns names the employee and pay period involved, "
    "describes the problem in plain English, and suggests what HR should do about it."
)
st.write(
    "Automated tests prove the rules work: every rule must find exactly the number of "
    "defects that were planted, and must find nothing in the clean data."
)
st.dataframe(rule_catalog(), hide_index=True, width="stretch")

st.header("How to read the dashboard")
st.markdown(
    "- **Severity** tells you what to fix first. **High** means pay may be wrong or a "
    "compliance rule is broken. **Medium** means the record is wrong and could cause "
    "pay or reporting errors. **Low** is a data-quality issue with no direct pay impact.\n"
    "- **Org & Personnel Integrity** lists problems with positions and assignments. "
    "Filter by rule, severity, or org unit, then download the list to Excel.\n"
    "- **Time & Payroll Reconciliation** compares recorded and paid hours for each "
    "pay period and lists pay errors. Pick a period to focus on it.\n"
    "- **HR Overview** shows headcount, vacancies, and how exceptions are spread "
    "across pay periods.\n"
    "- Each row's **Suggested action** is the recommended next step for an HR user."
)

st.header("Documentation")
st.markdown(f"- [GitHub repository]({REPO_URL})\n" + "\n".join(f"- [{name}]({doc_url(path)})" for name, path in DOCS.items()))
