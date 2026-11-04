-- Q07 · PIVOT: організації × категорії вердиктів (кількість перевірок)
-- Як розподіляються вердикти між фактчекінговими організаціями?
PIVOT (
    SELECT an.org_name AS organization, v.category, f.check_count
    FROM fact_check f
    JOIN dim_analyst an USING (analyst_key)
    JOIN dim_verdict v  USING (verdict_key)
)
ON category IN ('фейк', 'маніпуляція', 'неможливо перевірити', 'правда')
USING SUM(check_count)
ORDER BY organization;
