// Q11 · CQ11 · Вплив блокування першоджерела ACC-005
// Якщо акаунт ACC-005 заблокують, які похідні публікації (1–4 кроки), наративи та акаунти це зачепить?
MATCH (src:Account {id: 'ACC-005'})-[:PUBLISHED]->(own:Publication)
MATCH chain = (d:Publication)-[:DERIVED_FROM*1..4]->(own)
MATCH (d)-[:MAKES_CLAIM]->(:Claim)-[:PART_OF]->(n:Narrative)
MATCH (a:Account)-[:PUBLISHED]->(d)
RETURN count(DISTINCT own) AS ownPublications, count(DISTINCT d) AS derivedPublications,
       max(length(chain)) AS maxDepth, collect(DISTINCT n.name) AS narratives,
       count(DISTINCT a) AS dependentAccounts;
