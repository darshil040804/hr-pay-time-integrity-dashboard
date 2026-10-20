# Test Scenarios

> All data is synthetic and fictional, modeled on SAP HCM structures.

Structured test cases for the 11 validation rules: two per rule.

- **`-01` scenarios (must flag)** use a real planted defect in the committed data. They are run in the dashboard itself.
- **`-02` scenarios (must not flag)** are boundary or look-alike cases. The dashboard only shows the committed data, so these run on a small fixture dataset. Each one also has a **control**: the same fixture with the boundary crossed, which must be flagged. The control proves the fixture really exercises the rule.

Every scenario is automated in [`tests/test_scenarios.py`](../tests/test_scenarios.py) under the same Test ID. The `-01` tests drive the real Streamlit page (Streamlit `AppTest`), apply the filters listed in Steps, and read the exception table. The Actual Result column below comes from that run.

**Executed:** 2026-10-20 · `pytest tests/test_scenarios.py` · **22 passed, 0 failed**

## Org & Personnel

| Test ID | Rule | Precondition | Steps | Expected Result | Actual Result | Status |
|---|---|---|---|---|---|---|
| TS-OP-01-01 | OP-01 | Committed data. Employee 100058 is Active and holds POS0058, which is Inactive (planted). | 1. Open **Org & Personnel**.<br>2. Set **Rule** = OP-01. | 6 rows, all OP-01 (Medium). One reads "...(100058) is assigned to position POS0058, which is inactive." | 6 OP-01 rows; 100058 row present with that text. | Pass |
| TS-OP-01-02 | OP-01 | Fixture: employee 100102 is **Terminated** and still linked to Inactive position POS0101. Control: same employee Active. | Automated: `test_fixture_scenario[TS-OP-01-02]` | No exception (rule checks Active employees only). Control: 1 exception. | No exception. Control flagged 1. | Pass |
| TS-OP-02-01 | OP-02 | Committed data. Vacant position POS0482 has a blank org unit (planted). | 1. Open **Org & Personnel**.<br>2. Set **Rule** = OP-02. | 4 rows, all OP-02 (Low). One reads "Position POS0482 has no org unit." Org unit shows "(no org unit)". | 4 OP-02 rows; POS0482 row present. | Pass |
| TS-OP-02-02 | OP-02 | Fixture: position POS0201 points to ORG010, which exists. Control: points to ORG999. | Automated: `test_fixture_scenario[TS-OP-02-02]` | No exception. Control: 1 exception. | No exception. Control flagged 1. | Pass |
| TS-OP-03-01 | OP-03 | Committed data. Employees 100046 and 100017 are both Active in POS0046 (planted). | 1. Open **Org & Personnel**.<br>2. Set **Rule** = OP-03. | 3 rows (one per extra holder). One reads "...(100017) shares position POS0046 with employee 100046." | 3 OP-03 rows; 100017 row present. | Pass |
| TS-OP-03-02 | OP-03 | Fixture: POS0301 has one Active employee (100203) and one **Terminated** employee (100204). Control: both Active. | Automated: `test_fixture_scenario[TS-OP-03-02]` | No exception (only one active holder). Control: 1 exception for the later hire. | No exception. Control flagged 1. | Pass |
| TS-OP-04-01 | OP-04 | Committed data. Employee 100476 was terminated on 2025-07-14 but holds Active position POS0495 (planted). | 1. Open **Org & Personnel**.<br>2. Set **Rule** = OP-04. | 5 rows, all OP-04 (High). One reads "...(100476) was terminated on 2025-07-14 but still holds active position POS0495." | 5 OP-04 rows; 100476 row present. | Pass |
| TS-OP-04-02 | OP-04 | Fixture: employee 100302 is Terminated with term date **2026-04-01**, after the as-of date (2026-03-29), and holds an Active position. Control: term date 2026-03-01. | Automated: `test_fixture_scenario[TS-OP-04-02]` | No exception (term date not yet past). Control: 1 exception. | No exception. Control flagged 1. | Pass |
| TS-OP-05-01 | OP-05 | Committed data. Employee 100123 is Salaried in a Non-exempt job (planted). | 1. Open **Org & Personnel**.<br>2. Set **Rule** = OP-05. | 5 rows, all OP-05 (High). One reads "...(100123) is Salaried but job "Student Services Coordinator" is Non-exempt." | 5 OP-05 rows; 100123 row present. | Pass |
| TS-OP-05-02 | OP-05 | Fixture: employee 100402 is **Salaried** in an Exempt job (JOB01 Professor). Control: Hourly. | Automated: `test_fixture_scenario[TS-OP-05-02]` | No exception. Control: 1 exception. | No exception. Control flagged 1. | Pass |

## Time & Payroll

| Test ID | Rule | Precondition | Steps | Expected Result | Actual Result | Status |
|---|---|---|---|---|---|---|
| TS-TP-01-01 | TP-01 | Committed data. Employee 100088 was paid 91.0 hours in PP01 but recorded 83.0 (planted). | 1. Open **Time & Payroll**.<br>2. Select pay period **PP01**.<br>3. Set **Rule** = TP-01. | 3 rows, all TP-01 (High). One reads "Employee 100088 was paid for 91.0 hours in PP01 but recorded 83.0 hours (difference +8.0)." | 3 TP-01 rows; 100088 row present. | Pass |
| TS-TP-01-02 | TP-01 | Fixture: 40.0 hours recorded in PP03, **40.4** paid (difference 0.4). Control: 40.6 paid (difference 0.6). | Automated: `test_fixture_scenario[TS-TP-01-02]` | No exception (0.5 or less is tolerated). Control: 1 exception. | No exception. Control flagged 1. | Pass |
| TS-TP-02-01 | TP-02 | Committed data. Employee 100205 (IT Analyst, Exempt) was paid 4.0 overtime hours in PP01 (planted). | 1. Open **Time & Payroll**.<br>2. Select **PP01**.<br>3. Set **Rule** = TP-02. | 1 row (High): "Employee 100205 received 4.0 hours of overtime ($241.68) in PP01, but job "IT Analyst" is Exempt." | 1 TP-02 row with that text. | Pass |
| TS-TP-02-02 | TP-02 | Fixture: employee in a **Non-exempt** job (JOB06 Payroll Specialist) paid 5.0 overtime hours in PP04. Control: Exempt job (JOB01). | Automated: `test_fixture_scenario[TS-TP-02-02]` | No exception. Control: 1 exception. | No exception. Control flagged 1. | Pass |
| TS-TP-03-01 | TP-03 | Committed data. Hourly employee 100047 was paid in PP03 with no time entries (planted). | 1. Open **Time & Payroll**.<br>2. Select **PP03**.<br>3. Set **Rule** = TP-03. | 2 rows, all TP-03 (Medium). One reads "Hourly employee 100047 was paid 61.5 hours in PP03 with no time entries recorded." | 2 TP-03 rows; 100047 row present. | Pass |
| TS-TP-03-02 | TP-03 | Fixture: hourly employee paid 20.0 hours in PP05, with time entries (12h + 8h) on 2026-03-05, inside PP05. Control: the entries are dated 2026-02-20, outside PP05. | Automated: `test_fixture_scenario[TS-TP-03-02]` | No exception. Control: 1 exception. | No exception. Control flagged 1. | Pass |
| TS-TP-04-01 | TP-04 | Committed data. Employee 100109 recorded 18.0 hours on 2026-03-17 (planted). | 1. Open **Time & Payroll**.<br>2. Select **PP06**.<br>3. Set **Rule** = TP-04. | 3 rows, all TP-04 (Medium). One reads "Employee 100109 recorded 18.0 hours of Regular on 2026-03-17." | 3 TP-04 rows; 100109 row present. | Pass |
| TS-TP-04-02 | TP-04 | Fixture: one time entry of exactly **16.0** hours. Control: 16.5 hours. | Automated: `test_fixture_scenario[TS-TP-04-02]` | No exception (16 is allowed). Control: 1 exception. | No exception. Control flagged 1. | Pass |
| TS-TP-05-01 | TP-05 | Committed data. Employee 100021 has two shift differential (1400) lines in PP01 (planted). | 1. Open **Time & Payroll**.<br>2. Select **PP01**.<br>3. Set **Rule** = TP-05. | 2 rows, all TP-05 (High). One reads "Employee 100021 has 2 payroll lines for wage type 1400 (Shift Differential) in PP01..." | 2 TP-05 rows; 100021 row present. | Pass |
| TS-TP-05-02 | TP-05 | Fixture: a **single** vacation pay (1200) line for one employee in PP05. Control: the same line twice. | Automated: `test_fixture_scenario[TS-TP-05-02]` | No exception. Control: 1 exception. | No exception. Control flagged 1. | Pass |
| TS-TP-06-01 | TP-06 | Committed data. Employee 100484, terminated 2025-07-08, received $800.00 on 2026-02-06 (planted). | 1. Open **Time & Payroll**.<br>2. Select **PP02**.<br>3. Set **Rule** = TP-06. | 1 row (High): "Employee 100484 was terminated on 2025-07-08 but received $800.00 (wage type 1000) on 2026-02-06." | 1 TP-06 row with that text. | Pass |
| TS-TP-06-02 | TP-06 | Fixture: employee terminated 2026-02-15 and paid **on** 2026-02-15. Control: paid 2026-02-16. | Automated: `test_fixture_scenario[TS-TP-06-02]` | No exception (payment on the term date is allowed). Control: 1 exception. | No exception. Control flagged 1. | Pass |

## How this document was produced

1. **AI draft.** [`ai/draft_test_scenarios.py`](../ai/draft_test_scenarios.py) asked `openai/gpt-oss-120b` (via Groq) for two scenarios per rule. The output is kept unedited in [`test_scenarios_ai_draft.md`](test_scenarios_ai_draft.md).
2. **Problems found in review:**
   - The first draft wasn't executable. It told testers to "load the OP-01-Flag data set" and "run the validation", but the dashboard has no data loading and runs rules automatically. It also used IDs like `E001` and dates in 2023, and the reply was cut off after TP-04.
   - The prompt was changed to describe how the dashboard really works, with one request per rule area to avoid truncation. The second draft was complete and used the right ID formats, but its preconditions described records that don't exist in the data (for example, "employee 100101 is in inactive position POS0100").
3. **Human edits:**
   - Every `-01` precondition was replaced with a real planted defect, with exact row counts after filtering.
   - The `-02` boundary ideas were mostly kept, made precise, and given a control case.
   - The OP-05 fixture was changed to a real job ID, and the OP-04 fixture was changed to keep the position Active so only the date boundary is tested.
   - The Actual Result and Status columns were added and filled from the automated run.

Other test layers: [`tests/test_rules.py`](../tests/test_rules.py) checks planted-defect counts and clean data, and human-reviewed AI edge cases run from [`tests/test_ai_edge_cases.py`](../tests/test_ai_edge_cases.py). See the [AI testing log](ai_testing_log.md).
