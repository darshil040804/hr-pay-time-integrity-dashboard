"""Run the AI-proposed edge cases that a human reviewed and accepted.

Cases live in tests/ai_generated/edge_cases.json. Pending and rejected cases
are ignored. No AI API is called here: the cases are fixed data.
"""

import pytest

from src.edge_cases import load_cases, run_case
from src.rules import load_csv_tables

ACCEPTED = [case for case in load_cases() if case.review_status == "accepted"]


@pytest.fixture(scope="module")
def reference():
    return load_csv_tables()


@pytest.mark.skipif(not ACCEPTED, reason="no accepted AI edge cases yet")
@pytest.mark.parametrize("case", ACCEPTED, ids=[case.case_id for case in ACCEPTED])
def test_accepted_edge_case(case, reference):
    found = run_case(case, reference)
    flagged = not found.empty
    assert flagged == case.expected_flagged, (
        f"{case.case_id}: {case.description}\n"
        f"Expected {'flagged' if case.expected_flagged else 'not flagged'}; rule returned "
        f"{len(found)} row(s).\nRationale: {case.rationale}"
    )
