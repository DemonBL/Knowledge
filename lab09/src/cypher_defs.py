"""ЛР9 · усі тексти Cypher в одному місці (з них генеруються import/*.cypher і queries/*.cypher)."""

LABELS = ["Account", "Publication", "Claim", "Narrative", "Verdict", "FactChecker", "Tool",
          "OfficialSource", "FactCheckOrg", "Media", "Rule"]

CONSTRAINTS = [f"CREATE CONSTRAINT {l.lower()}_id IF NOT EXISTS FOR (n:{l}) REQUIRE n.id IS UNIQUE"
               for l in LABELS]
INDEXES = [
    "CREATE INDEX account_trust IF NOT EXISTS FOR (n:Account) ON (n.trustLevel)",
    "CREATE INDEX claim_priority IF NOT EXISTS FOR (n:Claim) ON (n.priority)",
    "CREATE TEXT INDEX claim_text IF NOT EXISTS FOR (n:Claim) ON (n.text)",
    "CREATE INDEX verdict_category IF NOT EXISTS FOR (n:Verdict) ON (n.category)",
]

NODE_LOAD = {
    "Account": "SET n.name=r.name, n.kind=r.kind, n.trust=r.trust, n.trustLevel=toInteger(r.trustLevel), "
               "n.followers=toInteger(r.followers), n.createdAt=date(r.createdAt), n.verified=(r.verified='True')",
    "Publication": "SET n.text=r.text, n.shares=toInteger(r.shares), n.platform=r.platform, "
                   "n.publishedAt=date(r.publishedAt)",
    "Claim": "SET n.text=r.text, n.priority=r.priority, n.city=r.city",
    "Narrative": "SET n.name=r.name",
    "Verdict": "SET n.category=r.category, n.confidence=r.confidence, n.decidedAt=date(r.decidedAt)",
    "FactChecker": "SET n.name=r.name, n.specialization=r.specialization",
    "Tool": "SET n.name=r.name, n.kind=r.kind",
    "OfficialSource": "SET n.name=r.name, n.trust=r.trust, n.trustLevel=toInteger(r.trustLevel)",
    "FactCheckOrg": "SET n.name=r.name, n.trust=r.trust, n.trustLevel=toInteger(r.trustLevel)",
    "Media": "SET n.kind=r.kind, n.exifDate=date(r.exifDate), n.reverseSearch=r.reverseSearch",
    "Rule": "SET n.condition=r.condition, n.action=r.action",
}

REL_ENDS = {  # тип: (мітка початку, мітка(и) кінця)
    "PUBLISHED": ("Account", "Publication"), "REPOSTED": ("Account", "Publication"),
    "DERIVED_FROM": ("Publication", "Publication"), "MAKES_CLAIM": ("Publication", "Claim"),
    "CONTAINS": ("Publication", "Media"), "PART_OF": ("Claim", "Narrative"),
    "ABOUT": ("Verdict", "Claim"), "ISSUED": ("FactChecker", "Verdict"),
    "BASED_ON": ("Verdict", "OfficialSource|Tool|FactCheckOrg"),
    "REFUTES": ("OfficialSource", "Claim"), "CONFIRMS": ("OfficialSource", "Claim"),
    "VERIFIED_WITH": ("Media", "Tool"), "USES": ("FactChecker", "Tool"),
    "WORKS_FOR": ("FactChecker", "FactCheckOrg"), "FORMALIZED_IN": ("FactChecker", "Rule"),
}


def node_load(label: str) -> str:
    return (f"LOAD CSV WITH HEADERS FROM 'file:///nodes_{label}.csv' AS r\n"
            f"MERGE (n:{label} {{id: r.id}})\n{NODE_LOAD[label]}")


def rel_load(t: str) -> str:
    a, b = REL_ENDS[t]
    extra = ", x.minutesAfter=toInteger(r.minutesAfter)" if t == "REPOSTED" else ""
    return (f"LOAD CSV WITH HEADERS FROM 'file:///rels_{t}.csv' AS r\n"
            f"MATCH (a:{a} {{id: r.start}})\nMATCH (b:{b} {{id: r.end}})\n"
            f"MERGE (a)-[x:{t}]->(b)\n"
            f"SET x.source=r.source, x.confidence=toFloat(r.confidence), x.validFrom=date(r.validFrom){extra}")


# --------------------------------------------------------------------------- запити (Результат 3)
QUERIES = [
    dict(id="Q01", cq="CQ1", kind="агрегація + WITH + ORDER BY",
         title="Автори зі спростованими публікаціями та їхнє охоплення",
         question="Хто з авторів поширює спростовані твердження, який у них індекс довіри і яке сумарне охоплення?",
         cypher="""MATCH (a:Account)-[:PUBLISHED]->(p:Publication)-[:MAKES_CLAIM]->(c:Claim)<-[:ABOUT]-(v:Verdict)
WHERE v.category IN ['фейк', 'маніпуляція']
WITH a, count(DISTINCT p) AS refutedPubs, sum(p.shares) AS reach
RETURN a.id AS account, a.name AS name, a.kind AS kind, a.trust AS trust, refutedPubs, reach
ORDER BY reach DESC LIMIT 10"""),
    dict(id="Q02", cq="CQ2", kind="кілька типів зв'язку + collect",
         title="Офіційні джерела: що підтвердили, що спростували",
         question="Яке офіційне джерело підтвердило чи спростувало які твердження?",
         cypher="""MATCH (o:OfficialSource)-[r:REFUTES|CONFIRMS]->(c:Claim)
RETURN o.name AS source, type(r) AS action, count(c) AS claims, collect(c.id)[..6] AS examples
ORDER BY source, action"""),
    dict(id="Q03", cq="CQ3", kind="OPTIONAL MATCH + фільтр на null",
         title="Вердикт щодо кожного твердження; незавершені перевірки",
         question="Який вердикт винесено щодо кожного твердження з високим пріоритетом і які ще не перевірені?",
         cypher="""MATCH (c:Claim {priority: 'високий'})
OPTIONAL MATCH (c)<-[:ABOUT]-(v:Verdict)<-[:ISSUED]-(f:FactChecker)
WITH c, v, f
RETURN CASE WHEN v IS NULL THEN 'очікує перевірки' ELSE v.category END AS status,
       count(c) AS claims, collect(c.id)[..8] AS examples
ORDER BY claims DESC"""),
    dict(id="Q04", cq="CQ4", kind="фільтр за датами + duration",
         title="Повторно використані медіафайли (правило RULE-4)",
         question="Які публікації містять медіафайли, зняті більш ніж на 7 днів раніше за публікацію, і чим це виявлено?",
         cypher="""MATCH (p:Publication)-[:CONTAINS]->(m:Media)
WHERE m.exifDate < p.publishedAt - duration({days: 7})
OPTIONAL MATCH (m)-[:VERIFIED_WITH]->(t:Tool)
RETURN p.id AS publication, m.id AS media, m.exifDate AS shot, p.publishedAt AS published,
       duration.inDays(m.exifDate, p.publishedAt).days AS ageDays, collect(t.name) AS tools
ORDER BY ageDays DESC"""),
    dict(id="Q05", cq="CQ5", kind="два OPTIONAL MATCH + агрегація",
         title="Інструменти фактчекерів: заявлені vs використані у вердиктах",
         question="Які інструменти застосовує кожен фактчекер і скільки разів вони стали доказом у його вердиктах?",
         cypher="""MATCH (f:FactChecker)-[:USES]->(t:Tool)
OPTIONAL MATCH (f)-[:ISSUED]->(v:Verdict)-[:BASED_ON]->(t)
WITH f, t, count(v) AS usedInVerdicts
RETURN f.name AS checker, collect(t.name + ' (' + toString(usedInVerdicts) + ')') AS tools,
       sum(usedInVerdicts) AS evidenceCount
ORDER BY evidenceCount DESC"""),
    dict(id="Q06", cq="CQ6", kind="шлях змінної довжини *0..4",
         title="Охоплення наративів з урахуванням похідних публікацій",
         question="Які твердження належать до кожного наративу і яке сумарне охоплення мають усі публікації ланцюжків поширення?",
         cypher="""MATCH (n:Narrative)<-[:PART_OF]-(c:Claim)<-[:MAKES_CLAIM]-(origin:Publication)
WHERE NOT (origin)-[:DERIVED_FROM]->()
MATCH (p:Publication)-[:DERIVED_FROM*0..4]->(origin)
WITH n, collect(DISTINCT c) AS cs, collect(DISTINCT p) AS ps
RETURN n.name AS narrative, size(cs) AS claims, size(ps) AS publications,
       reduce(s = 0, x IN ps | s + x.shares) AS reach
ORDER BY publications DESC"""),
    dict(id="Q07", cq="CQ7", kind="labels() + UNWIND",
         title="На яких доказах ґрунтуються вердикти",
         question="На яких типах доказів (офіційне джерело / інструмент / фактчекінгова організація) ґрунтуються вердикти кожної категорії?",
         cypher="""MATCH (v:Verdict)-[b:BASED_ON]->(e)
WITH v.category AS category, labels(e)[0] AS evidenceType, count(*) AS n, avg(b.confidence) AS avgConf
RETURN category, evidenceType, n, round(avgConf, 2) AS avgConfidence
ORDER BY category, n DESC"""),
    dict(id="Q08", cq="CQ8", kind="OPTIONAL MATCH + collect",
         title="Правила верифікації, формалізовані з досвіду фактчекерів",
         question="Які правила верифікації сформульовано на основі досвіду кожного фактчекера?",
         cypher="""MATCH (f:FactChecker)
OPTIONAL MATCH (f)-[:FORMALIZED_IN]->(r:Rule)
RETURN f.name AS checker, collect(r.id) AS rules, count(r) AS n
ORDER BY n DESC, checker"""),
    dict(id="Q09", cq="CQ9", kind="shortestPath",
         title="Найкоротший шлях від першоджерела до звичайних користувачів",
         question="Через скільки кроків контент анонімного каналу ACC-005 доходить до звичайних користувачів?",
         cypher="""MATCH (src:Account {id: 'ACC-005'}), (u:Account {kind: 'користувач'})
MATCH path = shortestPath((src)-[:PUBLISHED|DERIVED_FROM*..10]-(u))
RETURN u.id AS user, u.name AS name, length(path) AS hops,
       [x IN nodes(path) | x.id] AS route
ORDER BY hops, user LIMIT 5"""),
    dict(id="Q10", cq="CQ10", kind="аналіз впливу, глибина ≥ 3",
         title="Вплив спростування ДСНС: які публікації й акаунти треба позначити",
         question="Якщо ДСНС спростувала твердження, які публікації (з похідними до 4 кроків) і які акаунти їх поширили?",
         cypher="""MATCH (o:OfficialSource {id: 'OFF-01'})-[:REFUTES]->(c:Claim)<-[:MAKES_CLAIM]-(origin:Publication)
WHERE NOT (origin)-[:DERIVED_FROM]->()
MATCH (p:Publication)-[:DERIVED_FROM*0..4]->(origin)
MATCH (acc:Account)-[:PUBLISHED|REPOSTED]->(p)
WITH collect(DISTINCT c) AS cs, collect(DISTINCT p) AS ps, collect(DISTINCT acc) AS accs
RETURN size(cs) AS refutedClaims, size(ps) AS publicationsToLabel, size(accs) AS accountsToNotify,
       reduce(s = 0, x IN ps | s + x.shares) AS reachAffected"""),
    dict(id="Q11", cq="CQ11", kind="аналіз впливу, глибина ≥ 3",
         title="Вплив блокування першоджерела ACC-005",
         question="Якщо акаунт ACC-005 заблокують, які похідні публікації (1–4 кроки), наративи та акаунти це зачепить?",
         cypher="""MATCH (src:Account {id: 'ACC-005'})-[:PUBLISHED]->(own:Publication)
MATCH chain = (d:Publication)-[:DERIVED_FROM*1..4]->(own)
MATCH (d)-[:MAKES_CLAIM]->(:Claim)-[:PART_OF]->(n:Narrative)
MATCH (a:Account)-[:PUBLISHED]->(d)
RETURN count(DISTINCT own) AS ownPublications, count(DISTINCT d) AS derivedPublications,
       max(length(chain)) AS maxDepth, collect(DISTINCT n.name) AS narratives,
       count(DISTINCT a) AS dependentAccounts"""),
]

# Запити для перевірки PROFILE (Результат 4)
PROFILE_Q1 = """MATCH (a:Account)-[:PUBLISHED]->(p:Publication)
WHERE p.shares > 3000
RETURN a.name AS author, p.id AS publication, p.shares AS shares
ORDER BY shares DESC"""
PROFILE_Q2 = QUERIES[9]["cypher"]
OPT_INDEX = "CREATE INDEX publication_shares IF NOT EXISTS FOR (n:Publication) ON (n.shares)"
