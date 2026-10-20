import pandas as pd
import streamlit as st

from src.dashboard import disclaimer, doc_url, get_exceptions, get_tables
from src.edge_cases import load_cases, run_case
from src.rules import DATA_DIR, RULES

st.set_page_config(page_title="Testing & QA", layout="wide")
st.title("Testing & QA")
st.write(
    "**AI proposes, a human reviews, deterministic tests decide.** Every rule is checked "
    "against defects planted in the data on purpose. On top of that, an AI model proposes "
    "boundary and tricky test cases, such as hours of exactly 16 or a payment on the "
    "termination date. A person reviews each one and either accepts it, rejects it with a "
    "note, or fixes the rule if the AI found a real bug. Only accepted cases become automated "
    "tests, and those tests run offline on fixed data, so the results are repeatable. This page "
    "reads committed files only and makes no AI calls."
)
disclaimer()


@st.cache_data
def get_cases() -> pd.DataFrame:
    """All AI edge cases, with whether the current rule agrees with the AI's expectation."""
    reference = get_tables()
    rows = []
    for case in load_cases():
        flagged = not run_case(case, reference).empty
        rows.append({
            "Case": case.case_id, "Rule": case.rule_id, "Scenario": case.description,
            "AI expects": "Flagged" if case.expected_flagged else "Not flagged",
            "Rule result": "Flagged" if flagged else "Not flagged",
            "Agrees": flagged == case.expected_flagged,
            "Status": case.review_status.capitalize(), "Rule bug": case.rule_bug,
            "AI rationale": case.rationale, "Reviewer note": case.reviewer_note,
        })
    return pd.DataFrame(rows)


# Planted-defect regression results
st.header("Planted-defect regression")
planted = pd.read_csv(DATA_DIR / "planted_defects.csv")
found = get_exceptions()["rule_id"].value_counts()
results = pd.DataFrame({
    "Rule": planted["rule_id"],
    "Check": planted["rule_id"].map(lambda r: RULES[r][1]),
    "Expected": planted["expected_count"],
    "Found": planted["rule_id"].map(found).fillna(0).astype(int),
})
results["Result"] = (results["Expected"] == results["Found"]).map({True: "✅ Pass", False: "❌ Fail"})
passed = (results["Expected"] == results["Found"]).sum()
st.write(f"**{passed} of {len(results)} rules** find exactly the number of defects planted in the data. "
         "The same check, plus a check that clean data produces zero exceptions, runs in `pytest`.")
st.dataframe(results, hide_index=True, width="stretch")

# AI edge cases
st.header("AI-assisted edge cases")
cases = get_cases()
if cases.empty:
    st.info("No AI edge cases have been generated yet.")
    st.stop()

status = cases["Status"].value_counts()
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Proposed", len(cases))
c2.metric("Accepted", int(status.get("Accepted", 0)), help="Run as automated tests in pytest.")
c3.metric("Rejected", int(status.get("Rejected", 0)), help="The AI's expectation was wrong; see reviewer note.")
c4.metric("Pending review", int(status.get("Pending", 0)))
c5.metric("Rule bugs found", int(cases["Rule bug"].sum()), help="Cases that exposed a bug which was then fixed in the SQL.")

reviewed = cases[cases["Status"] != "Pending"]
st.subheader("Reviewed cases")
if reviewed.empty:
    st.info("No cases have been reviewed yet. Accepted and rejected cases, with reviewer notes, appear here.")
else:
    st.dataframe(reviewed[["Case", "Rule", "Status", "Scenario", "AI expects", "Rule bug", "Reviewer note"]],
                 hide_index=True, width="stretch")

pending = cases[cases["Status"] == "Pending"]
if not pending.empty:
    st.subheader("Awaiting review")
    disagree = (~pending["Agrees"]).sum()
    st.write(f"{len(pending)} cases are waiting for a human decision. In **{disagree}** of them the current "
             "rule disagrees with the AI. Either the rule has a bug or the AI misjudged the business rule.")
    view = pending.assign(Verdict=pending["Agrees"].map({True: "AGREE", False: "DISAGREE"}))
    st.dataframe(view.sort_values(["Agrees", "Case"])[["Verdict", "Case", "Rule", "Scenario", "AI expects",
                                                       "Rule result", "AI rationale"]],
                 hide_index=True, width="stretch")

st.markdown(f"Every disagreement and its outcome is recorded in the "
            f"[AI testing log]({doc_url('docs/ai_testing_log.md')}).")
