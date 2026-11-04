-- Q06 · Dice: підкуб за кількома вимірами одночасно —
-- платформи Telegram і TikTok × високий пріоритет × клас ознак «За медіа» × IV квартал
-- Якими методами перевіряють медіафейки високого пріоритету і скільки це триває?
SELECT m.notation, m.label AS method,
       COUNT(*) AS checks,
       round(AVG(f.hours_to_verdict), 1) AS avg_hours,
       round(AVG(f.evidence_count), 2) AS avg_evidence,
       round(100.0 * AVG(CASE WHEN v.is_false THEN 1 ELSE 0 END), 1) AS false_pct
FROM fact_check f
JOIN dim_platform p ON p.platform_key = f.platform_key
JOIN dim_taxonomy s ON s.taxonomy_key = f.signal_key
JOIN dim_taxonomy m ON m.taxonomy_key = f.method_key
JOIN dim_verdict  v ON v.verdict_key  = f.verdict_key
JOIN dim_date     d ON d.date_key     = f.date_key
WHERE p.platform IN ('Telegram', 'TikTok')
  AND f.priority = 'високий'
  AND s.class_label = 'За медіа'
  AND d.quarter IN (3, 4)
GROUP BY m.notation, m.label
ORDER BY checks DESC;
