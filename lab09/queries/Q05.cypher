// Q05 · CQ5 · Інструменти фактчекерів: заявлені vs використані у вердиктах
// Які інструменти застосовує кожен фактчекер і скільки разів вони стали доказом у його вердиктах?
MATCH (f:FactChecker)-[:USES]->(t:Tool)
OPTIONAL MATCH (f)-[:ISSUED]->(v:Verdict)-[:BASED_ON]->(t)
WITH f, t, count(v) AS usedInVerdicts
RETURN f.name AS checker, collect(t.name + ' (' + toString(usedInVerdicts) + ')') AS tools,
       sum(usedInVerdicts) AS evidenceCount
ORDER BY evidenceCount DESC;
