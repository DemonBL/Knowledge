-- «Сироти»: рядки факту без відповідного рядка виміру (очікується 0 для кожного FK)
SELECT 'account' AS fk, count(*) AS n FROM fact_check f LEFT JOIN dim_account d USING (account_key) WHERE d.account_key IS NULL
UNION ALL SELECT 'platform', count(*) FROM fact_check f LEFT JOIN dim_platform d USING (platform_key) WHERE d.platform_key IS NULL
UNION ALL SELECT 'analyst', count(*) FROM fact_check f LEFT JOIN dim_analyst d USING (analyst_key) WHERE d.analyst_key IS NULL
UNION ALL SELECT 'narrative', count(*) FROM fact_check f LEFT JOIN dim_narrative d USING (narrative_key) WHERE d.narrative_key IS NULL
UNION ALL SELECT 'signal', count(*) FROM fact_check f LEFT JOIN dim_taxonomy d ON d.taxonomy_key = f.signal_key WHERE d.taxonomy_key IS NULL
UNION ALL SELECT 'method', count(*) FROM fact_check f LEFT JOIN dim_taxonomy d ON d.taxonomy_key = f.method_key WHERE d.taxonomy_key IS NULL
UNION ALL SELECT 'verdict', count(*) FROM fact_check f LEFT JOIN dim_verdict d USING (verdict_key) WHERE d.verdict_key IS NULL
UNION ALL SELECT 'date', count(*) FROM fact_check f LEFT JOIN dim_date d USING (date_key) WHERE d.date_key IS NULL;
