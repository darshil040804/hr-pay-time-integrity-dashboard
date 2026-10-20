-- OP-02: Position with missing or nonexistent org unit
-- Every position must belong to an org unit that exists in org_units.
-- One row per position. emp_id is the active holder, if there is one.
SELECT
    'OP-02' AS rule_id,
    'Low' AS severity,
    (SELECT min(e.emp_id) FROM employees e
      WHERE e.position_id = p.position_id AND e.status = 'Active') AS emp_id,
    NULL::VARCHAR AS period_id,
    CASE WHEN p.org_unit_id IS NULL
         THEN format('Position {} has no org unit.', p.position_id)
         ELSE format('Position {} points to org unit {}, which does not exist.', p.position_id, p.org_unit_id)
    END AS issue,
    'Assign the position to a valid org unit in the org structure.' AS suggested_action
FROM positions p
LEFT JOIN org_units o ON o.org_unit_id = p.org_unit_id
WHERE o.org_unit_id IS NULL
ORDER BY p.position_id
