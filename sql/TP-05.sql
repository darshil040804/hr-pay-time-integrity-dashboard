-- TP-05: Duplicate payroll line: same employee, period, wage type
-- Each wage type should appear once per employee per period.
-- One row per duplicated combination.
SELECT
    'TP-05' AS rule_id,
    'High' AS severity,
    r.emp_id,
    r.period_id,
    format('Employee {} has {} payroll lines for wage type {} ({}) in {}, totaling ${:.2f}.',
           r.emp_id, count(*), r.wage_type, coalesce(any_value(w.description), 'unknown'),
           r.period_id, sum(r.amount)) AS issue,
    'Check whether the employee was paid twice; reverse the duplicate line or combine the lines into one.' AS suggested_action
FROM payroll_results r
LEFT JOIN wage_types w ON w.wage_type = r.wage_type
GROUP BY r.emp_id, r.period_id, r.wage_type
HAVING count(*) > 1
ORDER BY r.period_id, r.emp_id, r.wage_type
