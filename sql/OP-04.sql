-- OP-04: Terminated employee still assigned to an active position past term_date
-- After termination the position should be released so it shows as vacant.
-- "Past" is judged against the as-of date: the end of the last pay period
-- (today's date if no pay periods are loaded).
WITH as_of AS (
    SELECT coalesce(max(end_date), current_date) AS as_of_date FROM pay_periods
)
SELECT
    'OP-04' AS rule_id,
    'High' AS severity,
    e.emp_id,
    NULL::VARCHAR AS period_id,
    format('{} {} ({}) was terminated on {} but still holds active position {}.',
           e.first_name, e.last_name, e.emp_id, e.term_date, e.position_id) AS issue,
    'Process the termination fully: remove the employee from the position so it can be refilled.' AS suggested_action
FROM employees e
JOIN positions p ON p.position_id = e.position_id
CROSS JOIN as_of
WHERE e.status = 'Terminated'
  AND p.status = 'Active'
  AND e.term_date < as_of.as_of_date
ORDER BY e.emp_id
