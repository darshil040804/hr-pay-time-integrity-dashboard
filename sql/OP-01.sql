-- OP-01: Employee assigned to an inactive position
-- An active employee should only hold a position that is still open (Active).
SELECT
    'OP-01' AS rule_id,
    'Medium' AS severity,
    e.emp_id,
    NULL::VARCHAR AS period_id,
    format('{} {} ({}) is assigned to position {}, which is inactive.',
           e.first_name, e.last_name, e.emp_id, e.position_id) AS issue,
    'Move the employee to an active position, or reactivate the position if it should still be open.' AS suggested_action
FROM employees e
JOIN positions p ON p.position_id = e.position_id
WHERE e.status = 'Active'
  AND p.status = 'Inactive'
ORDER BY e.emp_id
