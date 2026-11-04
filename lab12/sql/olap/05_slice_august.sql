-- Q05 · Slice: зріз куба по одному значенню виміру часу — серпень 2026
-- Які наративи домінували в серпні й скільки серед їхніх перевірок хибних?
SELECT n.narrative_id, n.name AS narrative,
       COUNT(*) AS checks,
       SUM(CASE WHEN v.is_false THEN 1 ELSE 0 END) AS false_verdicts,
       SUM(f.shares_at_check) AS reach
FROM fact_check f
JOIN dim_date      d USING (date_key)
JOIN dim_narrative n USING (narrative_key)
JOIN dim_verdict   v USING (verdict_key)
WHERE d.year = 2026 AND d.month = 8                 -- slice
GROUP BY n.narrative_id, n.name
ORDER BY checks DESC;
