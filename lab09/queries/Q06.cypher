// Q06 · CQ6 · Охоплення наративів з урахуванням похідних публікацій
// Які твердження належать до кожного наративу і яке сумарне охоплення мають усі публікації ланцюжків поширення?
MATCH (n:Narrative)<-[:PART_OF]-(c:Claim)<-[:MAKES_CLAIM]-(origin:Publication)
WHERE NOT (origin)-[:DERIVED_FROM]->()
MATCH (p:Publication)-[:DERIVED_FROM*0..4]->(origin)
WITH n, collect(DISTINCT c) AS cs, collect(DISTINCT p) AS ps
RETURN n.name AS narrative, size(cs) AS claims, size(ps) AS publications,
       reduce(s = 0, x IN ps | s + x.shares) AS reach
ORDER BY publications DESC;
