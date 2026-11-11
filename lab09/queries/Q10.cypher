// Q10 · CQ10 · Вплив спростування ДСНС: які публікації й акаунти треба позначити
// Якщо ДСНС спростувала твердження, які публікації (з похідними до 4 кроків) і які акаунти їх поширили?
MATCH (o:OfficialSource {id: 'OFF-01'})-[:REFUTES]->(c:Claim)<-[:MAKES_CLAIM]-(origin:Publication)
WHERE NOT (origin)-[:DERIVED_FROM]->()
MATCH (p:Publication)-[:DERIVED_FROM*0..4]->(origin)
MATCH (acc:Account)-[:PUBLISHED|REPOSTED]->(p)
WITH collect(DISTINCT c) AS cs, collect(DISTINCT p) AS ps, collect(DISTINCT acc) AS accs
RETURN size(cs) AS refutedClaims, size(ps) AS publicationsToLabel, size(accs) AS accountsToNotify,
       reduce(s = 0, x IN ps | s + x.shares) AS reachAffected;
