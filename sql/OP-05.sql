-- OP-05: Employee subgroup inconsistent with job FLSA status
-- Exempt jobs must be Salaried; Non-exempt jobs must be Hourly.
SELECT
    'OP-05' AS rule_id,
    'High' AS severity,
    e.emp_id,
    NULL::VARCHAR AS period_id,
    format('{} {} ({}) is {} but job "{}" is {}.',
           e.first_name, e.last_name, e.emp_id, e.employee_subgroup, j.title, j.flsa_status) AS issue,
    'Correct the employee subgroup to match the job''s FLSA status, or review whether the job is classified correctly.' AS suggested_action
FROM employees e
JOIN positions p ON p.position_id = e.position_id
JOIN jobs j ON j.job_id = p.job_id
WHERE (e.employee_subgroup = 'Hourly' AND j.flsa_status = 'Exempt')
   OR (e.employee_subgroup = 'Salaried' AND j.flsa_status = 'Non-exempt')
ORDER BY e.emp_id
