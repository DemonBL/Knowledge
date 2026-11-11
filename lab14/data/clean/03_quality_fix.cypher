// ЛР14 · міграція якості kb-2026.11-v0 → v1 (Neo4j 5.26). Зворотна: 03_quality_undo.cypher
MATCH (c:Claim) WHERE NOT (c)<-[:ABOUT]-(:Verdict) SET c.status = 'не перевірено (вердикту немає)';
MATCH (c:Claim) WHERE (c)<-[:ABOUT]-(:Verdict) SET c.status = 'перевірено';
MATCH (n:Narrative) OPTIONAL MATCH (n)<-[:PART_OF]-(c:Claim) OPTIONAL MATCH (c)<-[:MAKES_CLAIM]-(p:Publication) WITH n, count(DISTINCT c) AS cc, count(DISTINCT p) AS pc SET n.claimCount = cc, n.publicationCount = pc;
MATCH (v:Verdict {category:'правда'})-[:ABOUT]->(c:Claim) WHERE v.decidedAt >= date('2026-09-01') AND COUNT { (:OfficialSource)-[:CONFIRMS]->(c) } < 2 SET v.complianceStatus = 'потребує другого офіційного джерела (INT-REG-2026 §2)';
MATCH (v:Verdict)-[:ABOUT]->(c:Claim)<-[:MAKES_CLAIM]-(p:Publication) WITH v, min(p.publishedAt) AS f WHERE v.decidedAt < f SET v.firstSeenAt = f, v.temporalFlag = 'вердикт раніше за першу публікацію у графі';
MATCH (r:Rule) SET r.alias = replace(r.id, 'RULE-', 'R');
MATCH (r:Rule {id:'RULE-2'}) SET r.altCondition = 'автор має спростоване твердження (фейк / маніпуляція) у публікації з ≥ 1000 поширень [ЛР8 RDF]';
