-- TP-06: Payment dated after the employee's term_date
-- No pay should be dated after termination. A payment ON the term date is allowed.
-- One row per payroll line.
SELECT
    'TP-06' AS rule_id,
    'High' AS severity,
    r.emp_id,
    r.period_id,
    format('Employee {} was terminated on {} but received ${:.2f} (wage type {}) on {}.',
           r.emp_id, e.term_date, r.amount, r.wage_type, r.payment_date) AS issue,
    'Stop further payments and start overpayment recovery with the former employee.' AS suggested_action
FROM payroll_results r
JOIN employees e ON e.emp_id = r.emp_id
WHERE e.term_date IS NOT NULL
  AND r.payment_date > e.term_date
ORDER BY r.period_id, r.emp_id
