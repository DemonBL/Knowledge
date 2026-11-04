-- Q03 · CUBE: охоплення спростованих (фейк/маніпуляція) публікацій за типом платформи × типом акаунта
-- BQ3: які платформи і типи акаунтів дають найбільше охоплення хибних публікацій?
SELECT
    COALESCE(p.platform_type, 'УСІ ПЛАТФОРМИ') AS platform_type,
    COALESCE(a.kind, 'УСІ АКАУНТИ')           AS account_kind,
    COUNT(*)                                  AS false_checks,
    SUM(f.shares_at_check)                    AS reach,
    GROUPING(p.platform_type, a.kind)         AS grouping_id
FROM fact_check f
JOIN dim_platform p USING (platform_key)
JOIN dim_account  a USING (account_key)
JOIN dim_verdict  v USING (verdict_key)
WHERE v.is_false
GROUP BY CUBE (p.platform_type, a.kind)
ORDER BY grouping_id, reach DESC;
