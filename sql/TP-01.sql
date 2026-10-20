-- TP-01: Paid hours differ from recorded time hours by more than 0.5 for the period
-- Compares hours-based wage types (1000-1300) with recorded time, per employee
-- per period. Shift differential (1400) is a premium on hours already paid,
-- so it is excluded. Only employee-periods with BOTH time and pay are compared;
-- pay without any time is rule TP-03.
WITH recorded AS (
    SELECT pp.period_id, t.emp_id, sum(t.hours) AS hours
    FROM time_entries t
    JOIN pay_periods pp ON t.work_date BETWEEN pp.start_date AND pp.end_date
    GROUP BY pp.period_id, t.emp_id
),
paid AS (
    SELECT period_id, emp_id, sum(hours) AS hours
    FROM payroll_results
    WHERE wage_type IN ('1000', '1100', '1200', '1300')
    GROUP BY period_id, emp_id
)
SELECT
    'TP-01' AS rule_id,
    'High' AS severity,
    paid.emp_id,
    paid.period_id,
    format('Employee {} was paid for {:.1f} hours in {} but recorded {:.1f} hours (difference {:+.1f}).',
           paid.emp_id, paid.hours, paid.period_id, recorded.hours, paid.hours - recorded.hours) AS issue,
    'Compare the time sheet with the payroll result and correct whichever is wrong before the next pay run.' AS suggested_action
FROM paid
JOIN recorded ON recorded.period_id = paid.period_id AND recorded.emp_id = paid.emp_id
WHERE abs(paid.hours - recorded.hours) > 0.5
ORDER BY paid.period_id, paid.emp_id
