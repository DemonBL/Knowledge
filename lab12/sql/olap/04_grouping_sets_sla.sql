-- Q04 · GROUPING SETS: тривалість перевірки і виконання SLA за класом методу та пріоритетом
-- BQ2: скільки триває перевірка залежно від методу й пріоритету, чи виконується SLA (12/24/48 год)?
SELECT
    CASE WHEN GROUPING(m.class_label) = 1 THEN '—' ELSE m.class_label END AS method_class,
    CASE WHEN GROUPING(f.priority)    = 1 THEN '—' ELSE f.priority    END AS priority,
    COUNT(*)                                        AS checks,
    round(AVG(f.hours_to_verdict), 1)               AS avg_hours,
    round(quantile_cont(f.hours_to_verdict, 0.9), 1) AS p90_hours,
    round(100.0 * AVG(CASE WHEN f.sla_met THEN 1 ELSE 0 END), 1) AS sla_pct
FROM fact_check f
JOIN dim_taxonomy m ON m.taxonomy_key = f.method_key
GROUP BY GROUPING SETS ((m.class_label, f.priority), (m.class_label), (f.priority), ())
ORDER BY GROUPING(m.class_label), method_class, GROUPING(f.priority), priority;
