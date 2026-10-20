import streamlit as st

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

st.info(
    "All data in this app is synthetic and fictional. It is modeled on SAP HCM "
    "structures but does not use real SAP systems or real employee data."
)
