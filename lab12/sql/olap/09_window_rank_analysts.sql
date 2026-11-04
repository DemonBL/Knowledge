-- Q09 · Віконні функції: ранг аналітиків усередині організації, частка в навантаженні організації,
--       середня черга (напівадитивна міра backlog_open — усереднюється, а не сумується за часом)
-- BQ4: як навантаження розподілене між організаціями й аналітиками?
SELECT an.org_name AS organization, an.analyst_id, an.specialization,
       COUNT(*)                                     AS checks,
       RANK() OVER (PARTITION BY an.org_name ORDER BY COUNT(*) DESC) AS rank_in_org,
       round(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY an.org_name), 1) AS share_of_org_pct,
       round(AVG(f.hours_to_verdict), 1)            AS avg_hours,
       round(AVG(f.backlog_open), 2)                AS avg_backlog,
       round(SUM(f.effort_minutes) / 60.0, 1)       AS effort_hours
FROM fact_check f
JOIN dim_analyst an USING (analyst_key)
GROUP BY an.org_name, an.analyst_id, an.specialization
ORDER BY organization, rank_in_org;
