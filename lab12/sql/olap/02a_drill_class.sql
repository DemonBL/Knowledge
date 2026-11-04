-- Q02a · Drill-down, крок 1: рівень «клас ознак» × місяць (частка хибних вердиктів)
SELECT s.class_label AS class, d.month, d.month_name,
       COUNT(*) AS checks,
       round(100.0 * AVG(CASE WHEN v.is_false THEN 1 ELSE 0 END), 1) AS false_pct
FROM fact_check f
JOIN dim_taxonomy s ON s.taxonomy_key = f.signal_key
JOIN dim_verdict  v USING (verdict_key)
JOIN dim_date     d USING (date_key)
WHERE d.month BETWEEN 7 AND 10
GROUP BY s.class_label, d.month, d.month_name
ORDER BY s.class_label, d.month;
