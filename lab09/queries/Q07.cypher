// Q07 · CQ7 · На яких доказах ґрунтуються вердикти
// На яких типах доказів (офіційне джерело / інструмент / фактчекінгова організація) ґрунтуються вердикти кожної категорії?
MATCH (v:Verdict)-[b:BASED_ON]->(e)
WITH v.category AS category, labels(e)[0] AS evidenceType, count(*) AS n, avg(b.confidence) AS avgConf
RETURN category, evidenceType, n, round(avgConf, 2) AS avgConfidence
ORDER BY category, n DESC;
