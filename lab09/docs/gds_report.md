# Аналіз графа (GDS) і продуктивність (ЛР9, Результат 4)


GDS 2.13.2

## PageRank (топ-10)

| label | id | name | kind | pagerank |
|---|---|---|---|---|
| Account | ACC-001 | Анонімний Telegram-канал #1 | анонімний канал | 2.246 |
| Account | ACC-008 | Анонімний Telegram-канал #8 | анонімний канал | 2.048 |
| Account | ACC-007 | Анонімний Telegram-канал #7 | анонімний канал | 2.045 |
| Account | ACC-004 | Анонімний Telegram-канал #4 | анонімний канал | 2.037 |
| Account | ACC-002 | Анонімний Telegram-канал #2 | анонімний канал | 1.985 |
| Account | ACC-003 | Анонімний Telegram-канал #3 | анонімний канал | 1.96 |
| Account | ACC-006 | Анонімний Telegram-канал #6 | анонімний канал | 1.899 |
| Account | ACC-005 | Анонімний Telegram-канал #5 | анонімний канал | 1.874 |
| Account | ACC-027 | Суспільне Новини | медіа | 0.79 |
| Account | ACC-028 | Укрінформ | медіа | 0.79 |

## PageRank за типом акаунта

| kind | accounts | avgPR | maxPR |
|---|---|---|---|
| анонімний канал | 8 | 2.012 | 2.246 |
| медіа | 6 | 0.573 | 0.79 |
| бот | 18 | 0.499 | 0.748 |
| користувач | 13 | 0.258 | 0.395 |

## Louvain

Запуск: {'communityCount': 10, 'modularity': 0.5701, 'ranLevels': 3}

| community | size | accounts | bots | mediaAcc | publications | narratives | botExamples |
|---|---|---|---|---|---|---|---|
| 148 | 68 | 11 | 8 | 0 | 43 | ['Отруєна питна вода', 'Втеча місцевої влади', 'Фейкові збори коштів'] | ['Бот-акаунт B1', 'Бот-акаунт B2', 'Бот-акаунт B3', 'Бот-акаунт B4'] |
| 54 | 40 | 5 | 4 | 0 | 27 | ['Повна втрата контролю над містом'] | ['Бот-акаунт A4', 'Бот-акаунт A5', 'Бот-акаунт A7', 'Бот-акаунт A8'] |
| 109 | 24 | 3 | 2 | 0 | 17 | [] | ['Бот-акаунт A1', 'Бот-акаунт A3'] |
| 181 | 24 | 12 | 0 | 4 | 6 | [] | [] |
| 160 | 19 | 3 | 1 | 0 | 12 | ['Небезпека укриттів і пунктів незламності'] | ['Бот-акаунт A6'] |
| 101 | 18 | 3 | 2 | 0 | 11 | ['Колапс критичної інфраструктури'] | ['Бот-акаунт A9', 'Бот-акаунт A10'] |
| 85 | 17 | 4 | 1 | 1 | 10 | [] | ['Бот-акаунт A2'] |
| 153 | 10 | 3 | 0 | 1 | 5 | [] | [] |

## PROFILE: запит 1 до/після індексу

```cypher

MATCH (a:Account)-[:PUBLISHED]->(p:Publication)
WHERE p.shares > 3000
RETURN a.name AS author, p.id AS publication, p.shares AS shares
ORDER BY shares DESC

```

До: db hits = 555, медіана 7.1 мс

| оператор | rows | dbHits |
|---|---|---|
| ProduceResults | 24 | 0 |
|   Projection | 24 | 48 |
|     Sort | 24 | 0 |
|       Projection | 24 | 0 |
|         Filter | 24 | 24 |
|           Expand(All) | 24 | 208 |
|             Filter | 24 | 137 |
|               NodeByLabelScan | 137 | 138 |

Після `CREATE INDEX publication_shares IF NOT EXISTS FOR (n:Publication) ON (n.shares)`: db hits = 305, медіана 5.32 мс

| оператор | rows | dbHits |
|---|---|---|
| ProduceResults | 24 | 0 |
|   Projection | 24 | 48 |
|     Filter | 24 | 24 |
|       Expand(All) | 24 | 208 |
|         NodeIndexSeekByRange | 24 | 25 |