// Q02 · CQ2 · Офіційні джерела: що підтвердили, що спростували
// Яке офіційне джерело підтвердило чи спростувало які твердження?
MATCH (o:OfficialSource)-[r:REFUTES|CONFIRMS]->(c:Claim)
RETURN o.name AS source, type(r) AS action, count(c) AS claims, collect(c.id)[..6] AS examples
ORDER BY source, action;
