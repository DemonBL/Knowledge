# SPARQL vs Cypher (ЛР9, Результат 5)


## S1 · Скільки тверджень спростувало/підтвердило кожне офіційне джерело

```cypher

MATCH (o:OfficialSource)-[r:REFUTES|CONFIRMS]->(c:Claim)
RETURN o.name AS source, type(r) AS action, count(c) AS n ORDER BY source, action

```

```sparql

PREFIX : <http://www.lnu.edu.ua/ontologies/disinfo-analysis.owl#>
SELECT ?source ?action (COUNT(?c) AS ?n) WHERE {
  ?o a :OfitsiineDzherelo ; :maieNazvu ?source .
  { ?o :sprostovuie ?c . BIND("REFUTES" AS ?action) }
  UNION
  { ?o :pidtverdzhuie ?c . BIND("CONFIRMS" AS ?action) }
} GROUP BY ?source ?action ORDER BY ?source ?action

```

Збіг результатів: **True** · Cypher 3.91 мс · SPARQL 0.35 мс

| source | action | n |
|---|---|---|
| ДСНС України | CONFIRMS | 1 |
| ДСНС України | REFUTES | 9 |
| МОЗ України | REFUTES | 3 |
| Національна поліція України | REFUTES | 3 |
| Офіційні канали міських рад | REFUTES | 11 |
| Повітряні сили ЗСУ | CONFIRMS | 5 |

## S2 · Статус перевірки тверджень із високим пріоритетом

```cypher

MATCH (c:Claim {priority: 'високий'})
OPTIONAL MATCH (c)<-[:ABOUT]-(v:Verdict)
RETURN coalesce(v.category, 'очікує') AS status, count(c) AS n ORDER BY status

```

```sparql

PREFIX : <http://www.lnu.edu.ua/ontologies/disinfo-analysis.owl#>
SELECT ?status (COUNT(?c) AS ?n) WHERE {
  ?c a :Tverdzhennia ; :priorytetPerevirky "високий" .
  OPTIONAL { ?v :vynosytsiaSchodo ?c ; :kategoriiaVerdyktu ?cat . }
  BIND(COALESCE(?cat, "очікує") AS ?status)
} GROUP BY ?status ORDER BY ?status

```

Збіг результатів: **True** · Cypher 3.4 мс · SPARQL 0.52 мс

| status | n |
|---|---|
| маніпуляція | 3 |
| очікує | 5 |
| фейк | 13 |

## S3 · Топ-5 авторів за охопленням спростованих публікацій

```cypher

MATCH (a:Account)-[:PUBLISHED]->(p:Publication)-[:MAKES_CLAIM]->(:Claim)<-[:ABOUT]-(v:Verdict)
WHERE v.category IN ['фейк', 'маніпуляція']
RETURN a.id AS account, sum(p.shares) AS reach ORDER BY reach DESC, account LIMIT 5

```

```sparql

PREFIX : <http://www.lnu.edu.ua/ontologies/disinfo-analysis.owl#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?account (SUM(?s) AS ?reach) WHERE {
  ?a :publikuie ?p ; rdfs:label ?account .
  ?p :kilkistPoshyren ?s ; :vysuvaie ?c .
  ?v :vynosytsiaSchodo ?c ; :kategoriiaVerdyktu ?cat .
  FILTER(?cat IN ("фейк", "маніпуляція"))
} GROUP BY ?account ORDER BY DESC(?reach) ?account LIMIT 5

```

Збіг результатів: **True** · Cypher 4.53 мс · SPARQL 1.88 мс

| account | reach |
|---|---|
| ACC-005 | 13046 |
| ACC-007 | 12364 |
| ACC-002 | 12029 |
| ACC-006 | 11603 |
| ACC-003 | 11196 |

## S4 · Кількість публікацій у ланцюжках поширення кожного наративу

```cypher

MATCH (n:Narrative)<-[:PART_OF]-(:Claim)<-[:MAKES_CLAIM]-(o:Publication)
WHERE NOT (o)-[:DERIVED_FROM]->()
MATCH (p:Publication)-[:DERIVED_FROM*0..]->(o)
RETURN n.name AS narrative, count(DISTINCT p) AS publications ORDER BY narrative

```

```sparql

PREFIX : <http://www.lnu.edu.ua/ontologies/disinfo-analysis.owl#>
SELECT ?narrative (COUNT(DISTINCT ?p) AS ?publications) WHERE {
  ?n a :Naratyv ; :maieNazvu ?narrative .
  ?c :nalezhytDoNaratyvu ?n . ?o :vysuvaie ?c .
  FILTER NOT EXISTS { ?o :pokhodytVid ?x }
  ?p :pokhodytVid* ?o .
} GROUP BY ?narrative ORDER BY ?narrative

```

Збіг результатів: **True** · Cypher 4.84 мс · SPARQL 1.14 мс

| narrative | publications |
|---|---|
| Втеча місцевої влади | 15 |
| Колапс критичної інфраструктури | 35 |
| Небезпека укриттів і пунктів незламності | 16 |
| Отруєна питна вода | 17 |
| Повна втрата контролю над містом | 31 |
| Фейкові збори коштів | 15 |

## S5 · Похідні публікації від публікацій акаунта ACC-005 (аналіз впливу)

```cypher

MATCH (:Account {id: 'ACC-005'})-[:PUBLISHED]->(own:Publication)
MATCH (d:Publication)-[:DERIVED_FROM*1..]->(own)
RETURN count(DISTINCT d) AS derived

```

```sparql

PREFIX : <http://www.lnu.edu.ua/ontologies/disinfo-analysis.owl#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT (COUNT(DISTINCT ?d) AS ?derived) WHERE {
  ?a rdfs:label "ACC-005" ; :publikuie ?own .
  ?d :pokhodytVid+ ?own .
}

```

Збіг результатів: **True** · Cypher 3.79 мс · SPARQL 0.25 мс

| derived |
|---|
| 15 |