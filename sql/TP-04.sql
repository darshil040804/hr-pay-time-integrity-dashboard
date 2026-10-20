-- TP-04: Daily hours over 16 or negative
-- Each time entry must be between 0 and 16 hours. Exactly 16 is allowed.
SELECT
    'TP-04' AS rule_id,
    'Medium' AS severity,
    t.emp_id,
    pp.period_id,
    format('Employee {} recorded {:.1f} hours of {} on {}.',
           t.emp_id, t.hours, t.attendance_type, t.work_date) AS issue,
    CASE WHEN t.hours < 0
         THEN 'Correct the negative time entry; hours cannot be below zero.'
         ELSE 'Confirm the hours with the supervisor; more than 16 hours in one day is likely a data entry error.'
    END AS suggested_action
FROM time_entries t
LEFT JOIN pay_periods pp ON t.work_date BETWEEN pp.start_date AND pp.end_date
WHERE t.hours > 16 OR t.hours < 0
ORDER BY t.emp_id, t.work_date
