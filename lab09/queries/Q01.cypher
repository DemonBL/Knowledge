// Q01 · CQ1 · Автори зі спростованими публікаціями та їхнє охоплення
// Хто з авторів поширює спростовані твердження, який у них індекс довіри і яке сумарне охоплення?
MATCH (a:Account)-[:PUBLISHED]->(p:Publication)-[:MAKES_CLAIM]->(c:Claim)<-[:ABOUT]-(v:Verdict)
WHERE v.category IN ['фейк', 'маніпуляція']
WITH a, count(DISTINCT p) AS refutedPubs, sum(p.shares) AS reach
RETURN a.id AS account, a.name AS name, a.kind AS kind, a.trust AS trust, refutedPubs, reach
ORDER BY reach DESC LIMIT 10;
