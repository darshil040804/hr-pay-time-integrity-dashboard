# AI Testing Log

**AI proposes, a human reviews, deterministic tests decide.**

An AI model proposes boundary and tricky test cases for each validation rule. A person reviews every case. Only accepted cases run in `pytest`, and those tests use fixed data and never call an AI API. This log records every disagreement between the AI and the rules, and what was decided.

Only synthetic data is sent to the AI provider: rule descriptions, SQL, table schemas, and made-up rows.

## Workflow

1. **Generate.** `python -m ai.generate_edge_cases` asks the AI for 3–5 cases per rule. Each case is validated against the schema and saved to [`tests/ai_generated/edge_cases.json`](../tests/ai_generated/edge_cases.json) as `pending`. Cases that are already in the file are never overwritten.
2. **Dry run.** `python -m ai.generate_edge_cases --dry-run` runs every pending case against the current rules and prints `AGREE` or `DISAGREE`. No AI calls are made.
3. **Decide each DISAGREE:**
   - **The rule is wrong:** fix the SQL, open a GitHub Issue, set the case to `"accepted"` and `"rule_bug": true`. The case is now a regression test for the fix.
   - **The AI is wrong:** set the case to `"rejected"` and explain why in `reviewer_note`.
4. **Accept sensible AGREE cases.** Set them to `"accepted"`. Reject cases that agree only by accident (for example, the data doesn't test what the description says).
5. **Record** each disagreement in the table below.
6. **Run** `pytest`. Accepted cases run as `tests/test_ai_edge_cases.py::test_accepted_edge_case[<case id>]`.

## How a case is judged

The AI is asked to predict `expected_flagged` from the rule's **business intent**, not by tracing the SQL. A disagreement therefore means either:

- the SQL doesn't match the business rule (a **rule bug**), or
- the AI misread the business rule or built data that doesn't match its own description (an **AI error**).

## Generation runs

| Date | Model | Rules | Proposed | Kept | Dry run |
|---|---|---|---:|---:|---|
| 2026-10-20 | `openai/gpt-oss-120b` (Groq) | all 11 | 44 | 44 | 38 AGREE, 6 DISAGREE |

## Disagreements

| Case ID | Rule | AI expectation | Rule behavior | Decision | Fix / Issue link |
|---|---|---|---|---|---|
| | | | | | |
