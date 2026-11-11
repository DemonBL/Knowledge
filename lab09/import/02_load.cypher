LOAD CSV WITH HEADERS FROM 'file:///nodes_Account.csv' AS r
MERGE (n:Account {id: r.id})
SET n.name=r.name, n.kind=r.kind, n.trust=r.trust, n.trustLevel=toInteger(r.trustLevel), n.followers=toInteger(r.followers), n.createdAt=date(r.createdAt), n.verified=(r.verified='True');

LOAD CSV WITH HEADERS FROM 'file:///nodes_Publication.csv' AS r
MERGE (n:Publication {id: r.id})
SET n.text=r.text, n.shares=toInteger(r.shares), n.platform=r.platform, n.publishedAt=date(r.publishedAt);

LOAD CSV WITH HEADERS FROM 'file:///nodes_Claim.csv' AS r
MERGE (n:Claim {id: r.id})
SET n.text=r.text, n.priority=r.priority, n.city=r.city;

LOAD CSV WITH HEADERS FROM 'file:///nodes_Narrative.csv' AS r
MERGE (n:Narrative {id: r.id})
SET n.name=r.name;

LOAD CSV WITH HEADERS FROM 'file:///nodes_Verdict.csv' AS r
MERGE (n:Verdict {id: r.id})
SET n.category=r.category, n.confidence=r.confidence, n.decidedAt=date(r.decidedAt);

LOAD CSV WITH HEADERS FROM 'file:///nodes_FactChecker.csv' AS r
MERGE (n:FactChecker {id: r.id})
SET n.name=r.name, n.specialization=r.specialization;

LOAD CSV WITH HEADERS FROM 'file:///nodes_Tool.csv' AS r
MERGE (n:Tool {id: r.id})
SET n.name=r.name, n.kind=r.kind;

LOAD CSV WITH HEADERS FROM 'file:///nodes_OfficialSource.csv' AS r
MERGE (n:OfficialSource {id: r.id})
SET n.name=r.name, n.trust=r.trust, n.trustLevel=toInteger(r.trustLevel);

LOAD CSV WITH HEADERS FROM 'file:///nodes_FactCheckOrg.csv' AS r
MERGE (n:FactCheckOrg {id: r.id})
SET n.name=r.name, n.trust=r.trust, n.trustLevel=toInteger(r.trustLevel);

LOAD CSV WITH HEADERS FROM 'file:///nodes_Media.csv' AS r
MERGE (n:Media {id: r.id})
SET n.kind=r.kind, n.exifDate=date(r.exifDate), n.reverseSearch=r.reverseSearch;

LOAD CSV WITH HEADERS FROM 'file:///nodes_Rule.csv' AS r
MERGE (n:Rule {id: r.id})
SET n.condition=r.condition, n.action=r.action;

LOAD CSV WITH HEADERS FROM 'file:///rels_PUBLISHED.csv' AS r
MATCH (a:Account {id: r.start})
MATCH (b:Publication {id: r.end})
MERGE (a)-[x:PUBLISHED]->(b)
SET x.source=r.source, x.confidence=toFloat(r.confidence), x.validFrom=date(r.validFrom);

LOAD CSV WITH HEADERS FROM 'file:///rels_REPOSTED.csv' AS r
MATCH (a:Account {id: r.start})
MATCH (b:Publication {id: r.end})
MERGE (a)-[x:REPOSTED]->(b)
SET x.source=r.source, x.confidence=toFloat(r.confidence), x.validFrom=date(r.validFrom), x.minutesAfter=toInteger(r.minutesAfter);

LOAD CSV WITH HEADERS FROM 'file:///rels_DERIVED_FROM.csv' AS r
MATCH (a:Publication {id: r.start})
MATCH (b:Publication {id: r.end})
MERGE (a)-[x:DERIVED_FROM]->(b)
SET x.source=r.source, x.confidence=toFloat(r.confidence), x.validFrom=date(r.validFrom);

LOAD CSV WITH HEADERS FROM 'file:///rels_MAKES_CLAIM.csv' AS r
MATCH (a:Publication {id: r.start})
MATCH (b:Claim {id: r.end})
MERGE (a)-[x:MAKES_CLAIM]->(b)
SET x.source=r.source, x.confidence=toFloat(r.confidence), x.validFrom=date(r.validFrom);

LOAD CSV WITH HEADERS FROM 'file:///rels_CONTAINS.csv' AS r
MATCH (a:Publication {id: r.start})
MATCH (b:Media {id: r.end})
MERGE (a)-[x:CONTAINS]->(b)
SET x.source=r.source, x.confidence=toFloat(r.confidence), x.validFrom=date(r.validFrom);

LOAD CSV WITH HEADERS FROM 'file:///rels_PART_OF.csv' AS r
MATCH (a:Claim {id: r.start})
MATCH (b:Narrative {id: r.end})
MERGE (a)-[x:PART_OF]->(b)
SET x.source=r.source, x.confidence=toFloat(r.confidence), x.validFrom=date(r.validFrom);

LOAD CSV WITH HEADERS FROM 'file:///rels_ABOUT.csv' AS r
MATCH (a:Verdict {id: r.start})
MATCH (b:Claim {id: r.end})
MERGE (a)-[x:ABOUT]->(b)
SET x.source=r.source, x.confidence=toFloat(r.confidence), x.validFrom=date(r.validFrom);

LOAD CSV WITH HEADERS FROM 'file:///rels_ISSUED.csv' AS r
MATCH (a:FactChecker {id: r.start})
MATCH (b:Verdict {id: r.end})
MERGE (a)-[x:ISSUED]->(b)
SET x.source=r.source, x.confidence=toFloat(r.confidence), x.validFrom=date(r.validFrom);

LOAD CSV WITH HEADERS FROM 'file:///rels_BASED_ON.csv' AS r
MATCH (a:Verdict {id: r.start})
MATCH (b:OfficialSource|Tool|FactCheckOrg {id: r.end})
MERGE (a)-[x:BASED_ON]->(b)
SET x.source=r.source, x.confidence=toFloat(r.confidence), x.validFrom=date(r.validFrom);

LOAD CSV WITH HEADERS FROM 'file:///rels_REFUTES.csv' AS r
MATCH (a:OfficialSource {id: r.start})
MATCH (b:Claim {id: r.end})
MERGE (a)-[x:REFUTES]->(b)
SET x.source=r.source, x.confidence=toFloat(r.confidence), x.validFrom=date(r.validFrom);

LOAD CSV WITH HEADERS FROM 'file:///rels_CONFIRMS.csv' AS r
MATCH (a:OfficialSource {id: r.start})
MATCH (b:Claim {id: r.end})
MERGE (a)-[x:CONFIRMS]->(b)
SET x.source=r.source, x.confidence=toFloat(r.confidence), x.validFrom=date(r.validFrom);

LOAD CSV WITH HEADERS FROM 'file:///rels_VERIFIED_WITH.csv' AS r
MATCH (a:Media {id: r.start})
MATCH (b:Tool {id: r.end})
MERGE (a)-[x:VERIFIED_WITH]->(b)
SET x.source=r.source, x.confidence=toFloat(r.confidence), x.validFrom=date(r.validFrom);

LOAD CSV WITH HEADERS FROM 'file:///rels_USES.csv' AS r
MATCH (a:FactChecker {id: r.start})
MATCH (b:Tool {id: r.end})
MERGE (a)-[x:USES]->(b)
SET x.source=r.source, x.confidence=toFloat(r.confidence), x.validFrom=date(r.validFrom);

LOAD CSV WITH HEADERS FROM 'file:///rels_WORKS_FOR.csv' AS r
MATCH (a:FactChecker {id: r.start})
MATCH (b:FactCheckOrg {id: r.end})
MERGE (a)-[x:WORKS_FOR]->(b)
SET x.source=r.source, x.confidence=toFloat(r.confidence), x.validFrom=date(r.validFrom);

LOAD CSV WITH HEADERS FROM 'file:///rels_FORMALIZED_IN.csv' AS r
MATCH (a:FactChecker {id: r.start})
MATCH (b:Rule {id: r.end})
MERGE (a)-[x:FORMALIZED_IN]->(b)
SET x.source=r.source, x.confidence=toFloat(r.confidence), x.validFrom=date(r.validFrom);
