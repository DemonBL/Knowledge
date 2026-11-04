-- Q01 · ROLLUP по ієрархії таксономії ознак (клас → поняття)
-- BQ1: які класи й підкласи ознак найчастіше приводять до вердикту «фейк»/«маніпуляція»?
SELECT
    CASE WHEN GROUPING(s.class_label) = 1 THEN 'УСЬОГО' ELSE s.class_label END AS class,
    CASE WHEN GROUPING(s.label) = 1 THEN '(разом клас)' ELSE s.notation || ' ' || s.label END AS signal,
    SUM(f.check_count)                                             AS checks,
    SUM(CASE WHEN v.is_false THEN 1 ELSE 0 END)                    AS false_verdicts,
    round(100.0 * SUM(CASE WHEN v.is_false THEN 1 ELSE 0 END) / SUM(f.check_count), 1) AS false_pct,
    GROUPING(s.class_label, s.label)                               AS grouping_id
FROM fact_check f
JOIN dim_taxonomy s ON s.taxonomy_key = f.signal_key
JOIN dim_verdict  v USING (verdict_key)
GROUP BY ROLLUP (s.class_label, (s.notation, s.label))
ORDER BY GROUPING(s.class_label), class, GROUPING(s.label) DESC, false_pct DESC;
