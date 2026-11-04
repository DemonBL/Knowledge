-- Q08 · Віконні функції: накопичена кількість фейків і 7-денне ковзне середнє за наративами
-- BQ5: які наративи зростають?
WITH daily AS (
    SELECT n.narrative_id, d.full_date,
           SUM(CASE WHEN v.category = 'фейк' THEN 1 ELSE 0 END) AS fakes
    FROM dim_date d
    CROSS JOIN (SELECT * FROM dim_narrative WHERE narrative_id IN ('NAR-02', 'NAR-03', 'NAR-05')) n
    LEFT JOIN fact_check f ON f.date_key = d.date_key AND f.narrative_key = n.narrative_key
    LEFT JOIN dim_verdict v ON v.verdict_key = f.verdict_key
    WHERE d.full_date BETWEEN DATE '2026-07-01' AND DATE '2026-10-31'
    GROUP BY n.narrative_id, d.full_date
)
SELECT narrative_id, full_date, fakes,
       SUM(fakes) OVER (PARTITION BY narrative_id ORDER BY full_date
                        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)      AS cum_fakes,
       round(AVG(fakes) OVER (PARTITION BY narrative_id ORDER BY full_date
                        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW), 2)        AS ma7_fakes
FROM daily
ORDER BY narrative_id, full_date;
