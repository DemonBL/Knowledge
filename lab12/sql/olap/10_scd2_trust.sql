-- Q10 · SCD2: частка хибних вердиктів за рівнем довіри автора НА МОМЕНТ перевірки
--       порівняно з ПОТОЧНИМ рівнем довіри того самого акаунта
-- BQ6: чи вища частка фейків у менш довірених акаунтів?
WITH cur AS (SELECT account_id, trust_label AS current_trust FROM dim_account WHERE is_current)
SELECT a.trust_level, a.trust_label AS trust_at_check,
       COUNT(*) AS checks,
       round(100.0 * AVG(CASE WHEN v.is_false THEN 1 ELSE 0 END), 1) AS false_pct,
       SUM(CASE WHEN NOT a.is_current THEN 1 ELSE 0 END) AS checks_on_old_version,
       string_agg(DISTINCT CASE WHEN c.current_trust <> a.trust_label THEN c.current_trust END, ', ') AS now_downgraded_to
FROM fact_check f
JOIN dim_account a USING (account_key)
JOIN cur c USING (account_id)
JOIN dim_verdict v USING (verdict_key)
GROUP BY a.trust_level, a.trust_label
ORDER BY a.trust_level;
