# Результати запитів Cypher (ЛР9, Результат 3)

Згенеровано автоматично 2026-10-20T01:44:19+03:00 скриптом src/run_lab09.py на Neo4j 5.26.

## Q01 · CQ1 · Автори зі спростованими публікаціями та їхнє охоплення
**Питання.** Хто з авторів поширює спростовані твердження, який у них індекс довіри і яке сумарне охоплення?
**Конструкції:** агрегація + WITH + ORDER BY · медіана 9.3 мс
```cypher
MATCH (a:Account)-[:PUBLISHED]->(p:Publication)-[:MAKES_CLAIM]->(c:Claim)<-[:ABOUT]-(v:Verdict)
WHERE v.category IN ['фейк', 'маніпуляція']
WITH a, count(DISTINCT p) AS refutedPubs, sum(p.shares) AS reach
RETURN a.id AS account, a.name AS name, a.kind AS kind, a.trust AS trust, refutedPubs, reach
ORDER BY reach DESC LIMIT 10
```
| account | name | kind | trust | refutedPubs | reach |
|---|---|---|---|---|---|
| ACC-005 | Анонімний Telegram-канал #5 | анонімний канал | знижений | 4 | 13046 |
| ACC-007 | Анонімний Telegram-канал #7 | анонімний канал | низький | 4 | 12364 |
| ACC-002 | Анонімний Telegram-канал #2 | анонімний канал | низький | 3 | 12029 |
| ACC-006 | Анонімний Telegram-канал #6 | анонімний канал | знижений | 3 | 11603 |
| ACC-003 | Анонімний Telegram-канал #3 | анонімний канал | низький | 3 | 11196 |
| ACC-001 | Анонімний Telegram-канал #1 | анонімний канал | низький | 3 | 10403 |
| ACC-008 | Анонімний Telegram-канал #8 | анонімний канал | низький | 3 | 9885 |
| ACC-015 | Бот-акаунт A7 | бот | низький | 6 | 6030 |
| ACC-004 | Анонімний Telegram-канал #4 | анонімний канал | низький | 3 | 5837 |
| ACC-023 | Бот-акаунт B5 | бот | низький | 6 | 5730 |

## Q02 · CQ2 · Офіційні джерела: що підтвердили, що спростували
**Питання.** Яке офіційне джерело підтвердило чи спростувало які твердження?
**Конструкції:** кілька типів зв'язку + collect · медіана 9.0 мс
```cypher
MATCH (o:OfficialSource)-[r:REFUTES|CONFIRMS]->(c:Claim)
RETURN o.name AS source, type(r) AS action, count(c) AS claims, collect(c.id)[..6] AS examples
ORDER BY source, action
```
| source | action | claims | examples |
|---|---|---|---|
| ДСНС України | CONFIRMS | 1 | ['CLM-34'] |
| ДСНС України | REFUTES | 9 | ['CLM-08', 'CLM-30', 'CLM-29', 'CLM-31', 'CLM-03', 'CLM-02'] |
| МОЗ України | REFUTES | 3 | ['CLM-18', 'CLM-17', 'CLM-19'] |
| Національна поліція України | REFUTES | 3 | ['CLM-28', 'CLM-25', 'CLM-27'] |
| Офіційні канали міських рад | REFUTES | 11 | ['CLM-13', 'CLM-12', 'CLM-10', 'CLM-23', 'CLM-14', 'CLM-24'] |
| Повітряні сили ЗСУ | CONFIRMS | 5 | ['CLM-38', 'CLM-33', 'CLM-36', 'CLM-37', 'CLM-35'] |

## Q03 · CQ3 · Вердикт щодо кожного твердження; незавершені перевірки
**Питання.** Який вердикт винесено щодо кожного твердження з високим пріоритетом і які ще не перевірені?
**Конструкції:** OPTIONAL MATCH + фільтр на null · медіана 7.8 мс
```cypher
MATCH (c:Claim {priority: 'високий'})
OPTIONAL MATCH (c)<-[:ABOUT]-(v:Verdict)<-[:ISSUED]-(f:FactChecker)
WITH c, v, f
RETURN CASE WHEN v IS NULL THEN 'очікує перевірки' ELSE v.category END AS status,
       count(c) AS claims, collect(c.id)[..8] AS examples
ORDER BY claims DESC
```
| status | claims | examples |
|---|---|---|
| фейк | 13 | ['CLM-03', 'CLM-04', 'CLM-05', 'CLM-07', 'CLM-10', 'CLM-13', 'CLM-15', 'CLM-18'] |
| очікує перевірки | 5 | ['CLM-06', 'CLM-11', 'CLM-20', 'CLM-26', 'CLM-32'] |
| маніпуляція | 3 | ['CLM-02', 'CLM-22', 'CLM-23'] |

## Q04 · CQ4 · Повторно використані медіафайли (правило RULE-4)
**Питання.** Які публікації містять медіафайли, зняті більш ніж на 7 днів раніше за публікацію, і чим це виявлено?
**Конструкції:** фільтр за датами + duration · медіана 7.4 мс
```cypher
MATCH (p:Publication)-[:CONTAINS]->(m:Media)
WHERE m.exifDate < p.publishedAt - duration({days: 7})
OPTIONAL MATCH (m)-[:VERIFIED_WITH]->(t:Tool)
RETURN p.id AS publication, m.id AS media, m.exifDate AS shot, p.publishedAt AS published,
       duration.inDays(m.exifDate, p.publishedAt).days AS ageDays, collect(t.name) AS tools
ORDER BY ageDays DESC
```
| publication | media | shot | published | ageDays | tools |
|---|---|---|---|---|---|
| PUB-011 | MED-02 | 2022-11-14 | 2026-09-14 | 1400 | ['Реверсивний пошук зображень'] |
| PUB-080 | MED-09 | 2022-11-12 | 2026-09-04 | 1392 | ['Геолокація за супутниковими знімками'] |
| PUB-111 | MED-12 | 2023-01-31 | 2026-09-23 | 1331 | ['Геолокація за супутниковими знімками'] |
| PUB-067 | MED-07 | 2023-05-04 | 2026-10-07 | 1252 | ['Геолокація за супутниковими знімками'] |
| PUB-105 | MED-11 | 2024-04-22 | 2026-09-17 | 878 | ['Геолокація за супутниковими знімками'] |
| PUB-036 | MED-06 | 2024-10-09 | 2026-09-21 | 712 | ['Реверсивний пошук зображень'] |
| PUB-123 | MED-13 | 2024-09-25 | 2026-09-07 | 712 | ['Реверсивний пошук зображень', 'Геолокація за супутниковими знімками'] |

## Q05 · CQ5 · Інструменти фактчекерів: заявлені vs використані у вердиктах
**Питання.** Які інструменти застосовує кожен фактчекер і скільки разів вони стали доказом у його вердиктах?
**Конструкції:** два OPTIONAL MATCH + агрегація · медіана 6.9 мс
```cypher
MATCH (f:FactChecker)-[:USES]->(t:Tool)
OPTIONAL MATCH (f)-[:ISSUED]->(v:Verdict)-[:BASED_ON]->(t)
WITH f, t, count(v) AS usedInVerdicts
RETURN f.name AS checker, collect(t.name + ' (' + toString(usedInVerdicts) + ')') AS tools,
       sum(usedInVerdicts) AS evidenceCount
ORDER BY evidenceCount DESC
```
| checker | tools | evidenceCount |
|---|---|---|
| Аналітик Ф-04 (соцмережі й боти) | ['Геолокація за супутниковими знімками (2)', 'Реверсивний пошук зображень (1)', 'Архів вебсторінок (Wayback Machine) (3)'] | 6 |
| Аналітик Ф-02 (регіональні новини) | ['Реверсивний пошук зображень (1)', 'Геолокація за супутниковими знімками (1)', 'Аналіз EXIF-метаданих (1)'] | 3 |
| Аналітик Ф-06 (фінансові шахрайства) | ['Реверсивний пошук зображень (0)', 'Архів вебсторінок (Wayback Machine) (1)', 'Аналіз мережі поширення (2)'] | 3 |
| Аналітик Ф-05 (здоров'я та медицина) | ['Аналіз мережі поширення (1)', 'Реверсивний пошук зображень (1)'] | 2 |
| Аналітик Ф-01 (військова тематика) | ['Архів вебсторінок (Wayback Machine) (1)', 'Реверсивний пошук зображень (0)'] | 1 |
| Аналітик Ф-03 (медіа та фото) | ['Реверсивний пошук зображень (0)', 'Аналіз EXIF-метаданих (0)'] | 0 |

## Q06 · CQ6 · Охоплення наративів з урахуванням похідних публікацій
**Питання.** Які твердження належать до кожного наративу і яке сумарне охоплення мають усі публікації ланцюжків поширення?
**Конструкції:** шлях змінної довжини *0..4 · медіана 7.3 мс
```cypher
MATCH (n:Narrative)<-[:PART_OF]-(c:Claim)<-[:MAKES_CLAIM]-(origin:Publication)
WHERE NOT (origin)-[:DERIVED_FROM]->()
MATCH (p:Publication)-[:DERIVED_FROM*0..4]->(origin)
WITH n, collect(DISTINCT c) AS cs, collect(DISTINCT p) AS ps
RETURN n.name AS narrative, size(cs) AS claims, size(ps) AS publications,
       reduce(s = 0, x IN ps | s + x.shares) AS reach
ORDER BY publications DESC
```
| narrative | claims | publications | reach |
|---|---|---|---|
| Колапс критичної інфраструктури | 8 | 35 | 43359 |
| Повна втрата контролю над містом | 8 | 31 | 34092 |
| Отруєна питна вода | 4 | 17 | 25314 |
| Небезпека укриттів і пунктів незламності | 4 | 16 | 19564 |
| Втеча місцевої влади | 4 | 15 | 19855 |
| Фейкові збори коштів | 4 | 15 | 23016 |

## Q07 · CQ7 · На яких доказах ґрунтуються вердикти
**Питання.** На яких типах доказів (офіційне джерело / інструмент / фактчекінгова організація) ґрунтуються вердикти кожної категорії?
**Конструкції:** labels() + UNWIND · медіана 5.4 мс
```cypher
MATCH (v:Verdict)-[b:BASED_ON]->(e)
WITH v.category AS category, labels(e)[0] AS evidenceType, count(*) AS n, avg(b.confidence) AS avgConf
RETURN category, evidenceType, n, round(avgConf, 2) AS avgConfidence
ORDER BY category, n DESC
```
| category | evidenceType | n | avgConfidence |
|---|---|---|---|
| маніпуляція | Tool | 4 | 0.87 |
| маніпуляція | OfficialSource | 4 | 0.95 |
| маніпуляція | FactCheckOrg | 4 | 0.9 |
| правда | OfficialSource | 6 | 0.94 |
| фейк | Tool | 22 | 0.82 |
| фейк | OfficialSource | 22 | 0.92 |
| фейк | FactCheckOrg | 12 | 0.9 |

## Q08 · CQ8 · Правила верифікації, формалізовані з досвіду фактчекерів
**Питання.** Які правила верифікації сформульовано на основі досвіду кожного фактчекера?
**Конструкції:** OPTIONAL MATCH + collect · медіана 5.1 мс
```cypher
MATCH (f:FactChecker)
OPTIONAL MATCH (f)-[:FORMALIZED_IN]->(r:Rule)
RETURN f.name AS checker, collect(r.id) AS rules, count(r) AS n
ORDER BY n DESC, checker
```
| checker | rules | n |
|---|---|---|
| Аналітик Ф-01 (військова тематика) | ['RULE-1', 'RULE-2'] | 2 |
| Аналітик Ф-03 (медіа та фото) | ['RULE-4'] | 1 |
| Аналітик Ф-04 (соцмережі й боти) | ['RULE-3'] | 1 |
| Аналітик Ф-02 (регіональні новини) | [] | 0 |
| Аналітик Ф-05 (здоров'я та медицина) | [] | 0 |
| Аналітик Ф-06 (фінансові шахрайства) | [] | 0 |

## Q09 · CQ9 · Найкоротший шлях від першоджерела до звичайних користувачів
**Питання.** Через скільки кроків контент анонімного каналу ACC-005 доходить до звичайних користувачів?
**Конструкції:** shortestPath · медіана 5.9 мс
```cypher
MATCH (src:Account {id: 'ACC-005'}), (u:Account {kind: 'користувач'})
MATCH path = shortestPath((src)-[:PUBLISHED|DERIVED_FROM*..10]-(u))
RETURN u.id AS user, u.name AS name, length(path) AS hops,
       [x IN nodes(path) | x.id] AS route
ORDER BY hops, user LIMIT 5
```
| user | name | hops | route |
|---|---|---|---|
| ACC-037 | Користувач #5 | 5 | ['ACC-005', 'PUB-014', 'PUB-015', 'PUB-017', 'PUB-018', 'ACC-037'] |
| ACC-044 | Користувач #12 | 5 | ['ACC-005', 'PUB-049', 'PUB-050', 'PUB-052', 'PUB-053', 'ACC-044'] |
| ACC-034 | Користувач #2 | 6 | ['ACC-005', 'PUB-014', 'PUB-015', 'ACC-015', 'PUB-121', 'PUB-122', 'ACC-034'] |
| ACC-036 | Користувач #4 | 6 | ['ACC-005', 'PUB-014', 'PUB-015', 'ACC-015', 'PUB-006', 'PUB-007', 'ACC-036'] |
| ACC-042 | Користувач #10 | 6 | ['ACC-005', 'PUB-049', 'PUB-050', 'PUB-052', 'PUB-053', 'PUB-054', 'ACC-042'] |

## Q10 · CQ10 · Вплив спростування ДСНС: які публікації й акаунти треба позначити
**Питання.** Якщо ДСНС спростувала твердження, які публікації (з похідними до 4 кроків) і які акаунти їх поширили?
**Конструкції:** аналіз впливу, глибина ≥ 3 · медіана 5.5 мс
```cypher
MATCH (o:OfficialSource {id: 'OFF-01'})-[:REFUTES]->(c:Claim)<-[:MAKES_CLAIM]-(origin:Publication)
WHERE NOT (origin)-[:DERIVED_FROM]->()
MATCH (p:Publication)-[:DERIVED_FROM*0..4]->(origin)
MATCH (acc:Account)-[:PUBLISHED|REPOSTED]->(p)
WITH collect(DISTINCT c) AS cs, collect(DISTINCT p) AS ps, collect(DISTINCT acc) AS accs
RETURN size(cs) AS refutedClaims, size(ps) AS publicationsToLabel, size(accs) AS accountsToNotify,
       reduce(s = 0, x IN ps | s + x.shares) AS reachAffected
```
| refutedClaims | publicationsToLabel | accountsToNotify | reachAffected |
|---|---|---|---|
| 9 | 36 | 22 | 42694 |

## Q11 · CQ11 · Вплив блокування першоджерела ACC-005
**Питання.** Якщо акаунт ACC-005 заблокують, які похідні публікації (1–4 кроки), наративи та акаунти це зачепить?
**Конструкції:** аналіз впливу, глибина ≥ 3 · медіана 6.0 мс
```cypher
MATCH (src:Account {id: 'ACC-005'})-[:PUBLISHED]->(own:Publication)
MATCH chain = (d:Publication)-[:DERIVED_FROM*1..4]->(own)
MATCH (d)-[:MAKES_CLAIM]->(:Claim)-[:PART_OF]->(n:Narrative)
MATCH (a:Account)-[:PUBLISHED]->(d)
RETURN count(DISTINCT own) AS ownPublications, count(DISTINCT d) AS derivedPublications,
       max(length(chain)) AS maxDepth, collect(DISTINCT n.name) AS narratives,
       count(DISTINCT a) AS dependentAccounts
```
| ownPublications | derivedPublications | maxDepth | narratives | dependentAccounts |
|---|---|---|---|---|
| 4 | 15 | 4 | ['Колапс критичної інфраструктури', 'Повна втрата контролю над містом', 'Небезпека укриттів і пунктів незламності', 'Втеча місцевої влади'] | 11 |
