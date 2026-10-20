-- TP-02: Overtime wage type paid to an Exempt employee
-- Overtime (1100) is only for employees whose job is Non-exempt.
-- One row per overtime payroll line.
SELECT
    'TP-02' AS rule_id,
    'High' AS severity,
    r.emp_id,
    r.period_id,
    format('Employee {} received {:.1f} hours of overtime (${:.2f}) in {}, but job "{}" is Exempt.',
           r.emp_id, r.hours, r.amount, r.period_id, j.title) AS issue,
    'Reverse the overtime payment, or reclassify the job if the employee should be Non-exempt.' AS suggested_action
FROM payroll_results r
JOIN employees e ON e.emp_id = r.emp_id
JOIN positions p ON p.position_id = e.position_id
JOIN jobs j ON j.job_id = p.job_id
WHERE r.wage_type = '1100'
  AND j.flsa_status = 'Exempt'
ORDER BY r.period_id, r.emp_id
