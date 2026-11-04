-- Q02b · Drill-down, крок 2: розкриваємо клас «За автором» (IRI …#Oznaky_ZaAvtorom) до понять
SELECT s.notation, s.label AS signal, s.concept_iri,
       COUNT(*) AS checks,
       round(100.0 * AVG(CASE WHEN v.is_false THEN 1 ELSE 0 END), 1) AS false_pct,
       SUM(f.shares_at_check) AS reach
FROM fact_check f
JOIN dim_taxonomy s ON s.taxonomy_key = f.signal_key
JOIN dim_verdict  v USING (verdict_key)
WHERE s.class_iri = 'http://www.lnu.edu.ua/ontologies/disinfo-analysis.owl#Oznaky_ZaAvtorom'
GROUP BY s.notation, s.label, s.concept_iri
ORDER BY s.notation;
