-- OP-03: Two active employees in the same position
-- A position holds one active employee. The first holder (earliest hire date)
-- is treated as the rightful one; every additional holder is flagged.
WITH holders AS (
    SELECT
        e.*,
        row_number() OVER (PARTITION BY e.position_id ORDER BY e.hire_date, e.emp_id) AS holder_number,
        first_value(e.emp_id) OVER (PARTITION BY e.position_id ORDER BY e.hire_date, e.emp_id) AS first_holder
    FROM employees e
    WHERE e.status = 'Active'
      AND e.position_id IS NOT NULL
)
SELECT
    'OP-03' AS rule_id,
    'Medium' AS severity,
    emp_id,
    NULL::VARCHAR AS period_id,
    format('{} {} ({}) shares position {} with employee {}.',
           first_name, last_name, emp_id, position_id, first_holder) AS issue,
    'Confirm which employee belongs in the position and move the other to their correct position.' AS suggested_action
FROM holders
WHERE holder_number > 1
ORDER BY emp_id
