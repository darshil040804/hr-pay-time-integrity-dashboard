-- TP-03: Active hourly employee paid with no time entries in the period
-- Hourly pay must be backed by recorded time. One row per employee per period.
SELECT
    'TP-03' AS rule_id,
    'Medium' AS severity,
    r.emp_id,
    r.period_id,
    format('Hourly employee {} was paid {:.1f} hours in {} with no time entries recorded.',
           r.emp_id, sum(r.hours), r.period_id) AS issue,
    'Get the missing time sheet from the employee''s supervisor, or reverse the payment if no work was done.' AS suggested_action
FROM payroll_results r
JOIN employees e ON e.emp_id = r.emp_id
JOIN pay_periods pp ON pp.period_id = r.period_id
WHERE e.status = 'Active'
  AND e.employee_subgroup = 'Hourly'
  AND NOT EXISTS (
      SELECT 1 FROM time_entries t
      WHERE t.emp_id = r.emp_id
        AND t.work_date BETWEEN pp.start_date AND pp.end_date
  )
GROUP BY r.emp_id, r.period_id
ORDER BY r.period_id, r.emp_id
