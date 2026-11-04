# ЛР12 · Результати OLAP-запитів

Сховище: DuckDB `data/lab12.duckdb` (версія набору даних — `data/VERSION.json`). Повні результати — `results/olap/*.csv`.

## Q01 · rollup signals

**Бізнес-питання.** BQ1. Які класи й підкласи ознак найчастіше приводять до вердикту «фейк»/«маніпуляція»?

**Конструкція:** ROLLUP + GROUPING().

```sql
SELECT
    CASE WHEN GROUPING(s.class_label) = 1 THEN 'УСЬОГО' ELSE s.class_label END AS class,
    CASE WHEN GROUPING(s.label) = 1 THEN '(разом клас)' ELSE s.notation || ' ' || s.label END AS signal,
    SUM(f.check_count)                                             AS checks,
    SUM(CASE WHEN v.is_false THEN 1 ELSE 0 END)                    AS false_verdicts,
    round(100.0 * SUM(CASE WHEN v.is_false THEN 1 ELSE 0 END) / SUM(f.check_count), 1) AS false_pct,
    GROUPING(s.class_label, s.label)                               AS grouping_id
FROM fact_check f
JOIN dim_taxonomy s ON s.taxonomy_key = f.signal_key
JOIN dim_verdict  v USING (verdict_key)
GROUP BY ROLLUP (s.class_label, (s.notation, s.label))
ORDER BY GROUPING(s.class_label), class, GROUPING(s.label) DESC, false_pct DESC;
```

**Результат** (15 рядків):

| class | signal | checks | false_verdicts | false_pct | grouping_id |
|---|---|---|---|---|---|
| За автором | (разом клас) | 760 | 534 | 70.3 | 1 |
| За автором | S2.2 Масові репости бот-мережі | 287 | 229 | 79.8 | 0 |
| За автором | S2.4 Автор має спростовані дописи | 91 | 63 | 69.2 | 0 |
| За автором | S2.1 Новий неверифікований акаунт | 287 | 194 | 67.6 | 0 |
| За автором | S2.3 Різка зміна тематики акаунта | 95 | 48 | 50.5 | 0 |
| За змістом | (разом клас) | 943 | 638 | 67.7 | 1 |
| За змістом | S1.4 Терміновий збір коштів на приватну картку | 393 | 351 | 89.3 | 0 |
| За змістом | S1.2 Немає першоджерела | 187 | 103 | 55.1 | 0 |
| За змістом | S1.1 Емоційна лексика | 187 | 95 | 50.8 | 0 |
| За змістом | S1.3 Вирваний або змінений контекст | 176 | 89 | 50.6 | 0 |
| За медіа | (разом клас) | 435 | 261 | 60 | 1 |
| За медіа | S3.3 Дипфейк або монтаж | 156 | 135 | 86.5 | 0 |
| За медіа | S3.1 Застаріле фото (EXIF) | 139 | 71 | 51.1 | 0 |
| За медіа | S3.2 Невідповідність геолокації | 140 | 55 | 39.3 | 0 |
| УСЬОГО | (разом клас) | 2138 | 1433 | 67 | 3 |

**Інтерпретація.** Найнадійніші ознаки — S1.4 «Терміновий збір коштів» (89 % хибних) і S3.3 «Дипфейк або монтаж» (86,5 %), далі S2.2 «Бот-мережа» (80 %). На рівні класів «За автором» дає 70 %, «За змістом» — 68 %, «За медіа» — 60 %. Найслабша ознака — «Невідповідність геолокації» (39 %): її варто доповнювати іншими. Рядки з grouping_id = 1/3 — підсумки ROLLUP за класом і загалом (2138 перевірок, 67 % хибних).

## Q02a · drill class

**Бізнес-питання.** Drill-down, крок 1: як змінювалась частка хибних вердиктів за класами ознак по місяцях?

**Конструкція:** drill-down (рівень класу) × час.

```sql
SELECT s.class_label AS class, d.month, d.month_name,
       COUNT(*) AS checks,
       round(100.0 * AVG(CASE WHEN v.is_false THEN 1 ELSE 0 END), 1) AS false_pct
FROM fact_check f
JOIN dim_taxonomy s ON s.taxonomy_key = f.signal_key
JOIN dim_verdict  v USING (verdict_key)
JOIN dim_date     d USING (date_key)
WHERE d.month BETWEEN 7 AND 10
GROUP BY s.class_label, d.month, d.month_name
ORDER BY s.class_label, d.month;
```

**Результат** (12 рядків):

| class | month | month_name | checks | false_pct |
|---|---|---|---|---|
| За автором | 7 | липень | 136 | 58.1 |
| За автором | 8 | серпень | 199 | 74.4 |
| За автором | 9 | вересень | 175 | 72 |
| За автором | 10 | жовтень | 248 | 72.2 |
| За змістом | 7 | липень | 166 | 60.8 |
| За змістом | 8 | серпень | 257 | 61.1 |
| За змістом | 9 | вересень | 253 | 75.1 |
| За змістом | 10 | жовтень | 265 | 71.3 |
| За медіа | 7 | липень | 105 | 59 |
| За медіа | 8 | серпень | 127 | 63 |
| За медіа | 9 | вересень | 76 | 55.3 |
| За медіа | 10 | жовтень | 127 | 60.6 |

**Інтерпретація.** На рівні класів видно зростання частки хибних вердиктів для ознак «За автором» із 58 % у липні до 72–74 % у серпні–жовтні, а для «За змістом» — стрибок у вересні (75 %). Щоб зрозуміти, яке саме поняття дає зростання, спускаємося на рівень нижче (Q02b).

## Q02b · drill subclass

**Бізнес-питання.** Drill-down, крок 2: які конкретні ознаки класу «За автором» (IRI …#Oznaky_ZaAvtorom) дають хибні вердикти й охоплення?

**Конструкція:** drill-down (клас → поняття), фільтр за class_iri.

```sql
SELECT s.notation, s.label AS signal, s.concept_iri,
       COUNT(*) AS checks,
       round(100.0 * AVG(CASE WHEN v.is_false THEN 1 ELSE 0 END), 1) AS false_pct,
       SUM(f.shares_at_check) AS reach
FROM fact_check f
JOIN dim_taxonomy s ON s.taxonomy_key = f.signal_key
JOIN dim_verdict  v USING (verdict_key)
WHERE s.class_iri = 'http://www.lnu.edu.ua/ontologies/disinfo-analysis.owl#Oznaky_ZaAvtorom'
GROUP BY s.notation, s.label, s.concept_iri
ORDER BY s.notation;
```

**Результат** (4 рядків):

| notation | signal | checks | false_pct | reach |
|---|---|---|---|---|
| S2.1 | Новий неверифікований акаунт | 287 | 67.6 | 209314 |
| S2.2 | Масові репости бот-мережі | 287 | 79.8 | 178441 |
| S2.3 | Різка зміна тематики акаунта | 95 | 50.5 | 79697 |
| S2.4 | Автор має спростовані дописи | 91 | 69.2 | 80623 |

**Інтерпретація.** Усередині класу найбільший внесок — «Масові репости бот-мережі» (80 % хибних) і «Новий неверифікований акаунт» (68 %, найбільше охоплення 209 тис.). Фільтр за IRI класу, а не за назвою, робить запит стійким до перейменування поняття в таксономії.

## Q03 · cube reach

**Бізнес-питання.** BQ3. Які типи платформ і акаунтів дають найбільше охоплення хибних публікацій?

**Конструкція:** CUBE + GROUPING().

```sql
SELECT
    COALESCE(p.platform_type, 'УСІ ПЛАТФОРМИ') AS platform_type,
    COALESCE(a.kind, 'УСІ АКАУНТИ')           AS account_kind,
    COUNT(*)                                  AS false_checks,
    SUM(f.shares_at_check)                    AS reach,
    GROUPING(p.platform_type, a.kind)         AS grouping_id
FROM fact_check f
JOIN dim_platform p USING (platform_key)
JOIN dim_account  a USING (account_key)
JOIN dim_verdict  v USING (verdict_key)
WHERE v.is_false
GROUP BY CUBE (p.platform_type, a.kind)
ORDER BY grouping_id, reach DESC;
```

**Результат** (18 рядків):

| platform_type | account_kind | false_checks | reach | grouping_id |
|---|---|---|---|---|
| месенджер | анонімний канал | 407 | 485886 | 0 |
| соцмережа | анонімний канал | 183 | 187271 | 0 |
| месенджер | бот | 346 | 186137 | 0 |
| відеоплатформа | анонімний канал | 94 | 85169 | 0 |
| соцмережа | бот | 151 | 81503 | 0 |
| соцмережа | користувач | 115 | 71398 | 0 |
| месенджер | користувач | 79 | 34827 | 0 |
| соцмережа | медіа | 20 | 23149 | 0 |
| відеоплатформа | бот | 29 | 17394 | 0 |
| відеоплатформа | користувач | 9 | 12191 | 0 |
| месенджер | УСІ АКАУНТИ | 832 | 706850 | 1 |
| соцмережа | УСІ АКАУНТИ | 469 | 363321 | 1 |
| відеоплатформа | УСІ АКАУНТИ | 132 | 114754 | 1 |
| УСІ ПЛАТФОРМИ | анонімний канал | 684 | 758326 | 2 |
| УСІ ПЛАТФОРМИ | бот | 526 | 285034 | 2 |
| УСІ ПЛАТФОРМИ | користувач | 203 | 118416 | 2 |
| УСІ ПЛАТФОРМИ | медіа | 20 | 23149 | 2 |
| УСІ ПЛАТФОРМИ | УСІ АКАУНТИ | 1433 | 1.18492e+06 | 3 |

**Інтерпретація.** Усі комбінації виміру отримано одним запитом. Найбільше охоплення хибних публікацій — анонімні канали в месенджерах (486 тис. із 1,18 млн, 41 %). Загалом месенджери дають 60 % охоплення, а анонімні канали — 64 %. Боти мають багато хибних перевірок (526), але менше охоплення (285 тис.), тобто вони підсилюють, а не створюють поширення. Медіа — лише 20 хибних перевірок.

## Q04 · grouping sets sla

**Бізнес-питання.** BQ2. Скільки триває перевірка залежно від класу методу й пріоритету; чи виконується SLA?

**Конструкція:** GROUPING SETS, quantile_cont.

```sql
SELECT
    CASE WHEN GROUPING(m.class_label) = 1 THEN '—' ELSE m.class_label END AS method_class,
    CASE WHEN GROUPING(f.priority)    = 1 THEN '—' ELSE f.priority    END AS priority,
    COUNT(*)                                        AS checks,
    round(AVG(f.hours_to_verdict), 1)               AS avg_hours,
    round(quantile_cont(f.hours_to_verdict, 0.9), 1) AS p90_hours,
    round(100.0 * AVG(CASE WHEN f.sla_met THEN 1 ELSE 0 END), 1) AS sla_pct
FROM fact_check f
JOIN dim_taxonomy m ON m.taxonomy_key = f.method_key
GROUP BY GROUPING SETS ((m.class_label, f.priority), (m.class_label), (f.priority), ())
ORDER BY GROUPING(m.class_label), method_class, GROUPING(f.priority), priority;
```

**Результат** (16 рядків):

| method_class | priority | checks | avg_hours | p90_hours | sla_pct |
|---|---|---|---|---|---|
| Експертна перевірка | високий | 158 | 7.3 | 12.7 | 87.3 |
| Експертна перевірка | низький | 166 | 19.7 | 36.9 | 95.2 |
| Експертна перевірка | середній | 247 | 11.6 | 21 | 94.7 |
| Експертна перевірка | — | 571 | 12.8 | 23.7 | 92.8 |
| Звірка з базами | високий | 222 | 2.6 | 5.3 | 100 |
| Звірка з базами | низький | 208 | 7.3 | 14.3 | 100 |
| Звірка з базами | середній | 371 | 4.4 | 9.1 | 100 |
| Звірка з базами | — | 801 | 4.6 | 9.9 | 100 |
| Технічна верифікація | високий | 201 | 3.7 | 7.7 | 98.5 |
| Технічна верифікація | низький | 216 | 11.2 | 20.4 | 100 |
| Технічна верифікація | середній | 349 | 7 | 13.3 | 98.9 |
| Технічна верифікація | — | 766 | 7.3 | 15.6 | 99.1 |
| — | високий | 581 | 4.3 | 8.6 | 96 |
| — | низький | 590 | 12.2 | 23.7 | 98.6 |
| — | середній | 967 | 7.2 | 13.9 | 98.2 |
| — | — | 2138 | 7.8 | 16.4 | 97.8 |

**Інтерпретація.** Звірка з базами — найшвидша (у середньому 4,6 год, SLA 100 %), експертна перевірка — найповільніша (12,8 год). Слабке місце — експертна перевірка з високим пріоритетом: SLA 12 год виконано лише в 87 % (p90 = 12,7 год). Для таких справ варто одразу паралельно запускати звірку з базами.

## Q05 · slice august

**Бізнес-питання.** Slice: які наративи домінували в серпні 2026 р.?

**Конструкція:** slice (одне значення виміру часу).

```sql
SELECT n.narrative_id, n.name AS narrative,
       COUNT(*) AS checks,
       SUM(CASE WHEN v.is_false THEN 1 ELSE 0 END) AS false_verdicts,
       SUM(f.shares_at_check) AS reach
FROM fact_check f
JOIN dim_date      d USING (date_key)
JOIN dim_narrative n USING (narrative_key)
JOIN dim_verdict   v USING (verdict_key)
WHERE d.year = 2026 AND d.month = 8                 -- slice
GROUP BY n.narrative_id, n.name
ORDER BY checks DESC;
```

**Результат** (7 рядків):

| narrative_id | narrative | checks | false_verdicts | reach |
|---|---|---|---|---|
| NAR-03 | Отруєна питна вода | 238 | 159 | 226792 |
| NAR-00 | без наративу | 190 | 101 | 102747 |
| NAR-06 | Небезпека укриттів і пунктів незламності | 41 | 35 | 33388 |
| NAR-05 | Фейкові збори коштів | 37 | 29 | 37061 |
| NAR-02 | Колапс критичної інфраструктури | 30 | 22 | 25141 |
| NAR-01 | Повна втрата контролю над містом | 27 | 22 | 27835 |
| NAR-04 | Втеча місцевої влади | 20 | 17 | 22940 |

**Інтерпретація.** Зріз за серпнем показує сплеск NAR-03 «Отруєна питна вода»: 238 перевірок, із них 159 хибних, охоплення 227 тис. — більше, ніж усі інші наративи разом. Це відповідає події, що спричинила хвилю (10–25.08).

## Q06 · dice media

**Бізнес-питання.** Dice: якими методами перевіряють медіафейки високого пріоритету в Telegram і TikTok (III–IV кв.)?

**Конструкція:** dice (фільтр за 4 вимірами).

```sql
SELECT m.notation, m.label AS method,
       COUNT(*) AS checks,
       round(AVG(f.hours_to_verdict), 1) AS avg_hours,
       round(AVG(f.evidence_count), 2) AS avg_evidence,
       round(100.0 * AVG(CASE WHEN v.is_false THEN 1 ELSE 0 END), 1) AS false_pct
FROM fact_check f
JOIN dim_platform p ON p.platform_key = f.platform_key
JOIN dim_taxonomy s ON s.taxonomy_key = f.signal_key
JOIN dim_taxonomy m ON m.taxonomy_key = f.method_key
JOIN dim_verdict  v ON v.verdict_key  = f.verdict_key
JOIN dim_date     d ON d.date_key     = f.date_key
WHERE p.platform IN ('Telegram', 'TikTok')
  AND f.priority = 'високий'
  AND s.class_label = 'За медіа'
  AND d.quarter IN (3, 4)
GROUP BY m.notation, m.label
ORDER BY checks DESC;
```

**Результат** (4 рядків):

| notation | method | checks | avg_hours | avg_evidence | false_pct |
|---|---|---|---|---|---|
| M1.1 | Реверсивний пошук зображень | 31 | 1.5 | 2.84 | 58.1 |
| M1.2 | Аналіз EXIF | 28 | 1.5 | 2.61 | 53.6 |
| M1.3 | Геолокація | 13 | 4.6 | 2.38 | 61.5 |
| M3.3 | Запит до галузевого експерта | 8 | 10.9 | 2 | 37.5 |

**Інтерпретація.** У підкубі домінує технічна верифікація: реверсивний пошук і EXIF дають вердикт у середньому за 1,5 год, геолокація — за 4,6 год, а запит до експерта — 10,9 год. Отже, для медіа з високим пріоритетом експертний запит варто залишати як останній крок.

## Q07 · pivot org verdict

**Бізнес-питання.** Як розподіляються вердикти між фактчекінговими організаціями?

**Конструкція:** PIVOT.

```sql
PIVOT (
    SELECT an.org_name AS organization, v.category, f.check_count
    FROM fact_check f
    JOIN dim_analyst an USING (analyst_key)
    JOIN dim_verdict v  USING (verdict_key)
)
ON category IN ('фейк', 'маніпуляція', 'неможливо перевірити', 'правда')
USING SUM(check_count)
ORDER BY organization;
```

**Результат** (4 рядків):

| organization | фейк | маніпуляція | неможливо перевірити | правда |
|---|---|---|---|---|
| EUvsDisinfo | 196 | 95 | 51 | 111 |
| StopFake | 307 | 143 | 52 | 141 |
| VoxCheck | 256 | 111 | 38 | 134 |
| Детектор медіа | 234 | 91 | 58 | 120 |

**Інтерпретація.** StopFake виносить найбільше вердиктів (643), найбільше з них — «фейк». Частка «неможливо перевірити» найвища в «Детектор медіа» (11,5 %) і EUvsDisinfo (11,3 %) — тема для обміну методиками. PIVOT перетворює значення категорії на стовпці без ручного CASE.

## Q08 · window narratives

**Бізнес-питання.** BQ5. Які наративи зростають: накопичена кількість фейків і 7-денне ковзне середнє?

**Конструкція:** вікна SUM … ROWS UNBOUNDED, AVG … ROWS 6 PRECEDING.

```sql
WITH daily AS (
    SELECT n.narrative_id, d.full_date,
           SUM(CASE WHEN v.category = 'фейк' THEN 1 ELSE 0 END) AS fakes
    FROM dim_date d
    CROSS JOIN (SELECT * FROM dim_narrative WHERE narrative_id IN ('NAR-02', 'NAR-03', 'NAR-05')) n
    LEFT JOIN fact_check f ON f.date_key = d.date_key AND f.narrative_key = n.narrative_key
    LEFT JOIN dim_verdict v ON v.verdict_key = f.verdict_key
    WHERE d.full_date BETWEEN DATE '2026-07-01' AND DATE '2026-10-31'
    GROUP BY n.narrative_id, d.full_date
)
SELECT narrative_id, full_date, fakes,
       SUM(fakes) OVER (PARTITION BY narrative_id ORDER BY full_date
                        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)      AS cum_fakes,
       round(AVG(fakes) OVER (PARTITION BY narrative_id ORDER BY full_date
                        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW), 2)        AS ma7_fakes
FROM daily
ORDER BY narrative_id, full_date;
```

**Результат** (369 рядків; показано вибрані дати):

| narrative_id | full_date | fakes | cum_fakes | ma7_fakes |
|---|---|---|---|---|
| NAR-02 | 2026-08-17 00:00:00 | 0 | 25 | 0.43 |
| NAR-02 | 2026-08-25 00:00:00 | 0 | 28 | 0.43 |
| NAR-02 | 2026-09-30 00:00:00 | 2 | 54 | 1.14 |
| NAR-02 | 2026-10-31 00:00:00 | 3 | 195 | 5.86 |
| NAR-03 | 2026-08-17 00:00:00 | 7 | 76 | 7.29 |
| NAR-03 | 2026-08-25 00:00:00 | 6 | 127 | 6 |
| NAR-03 | 2026-09-30 00:00:00 | 2 | 150 | 0.57 |
| NAR-03 | 2026-10-31 00:00:00 | 0 | 159 | 0.43 |
| NAR-05 | 2026-08-17 00:00:00 | 0 | 26 | 0.29 |
| NAR-05 | 2026-08-25 00:00:00 | 0 | 28 | 0.14 |
| NAR-05 | 2026-09-30 00:00:00 | 4 | 147 | 7.29 |
| NAR-05 | 2026-10-31 00:00:00 | 0 | 209 | 0.71 |

**Інтерпретація.** Ковзне середнє чітко показує три хвилі, що не перетинаються: NAR-03 — пік 18.08 (7,7 фейка/день), NAR-05 — пік 05.10 (7,9/день), NAR-02 — пік 22.10 (8,0/день). Накопичена сума: NAR-05 має найбільше фейків за період (209), а NAR-02 — найбільший приріст у жовтні (із 54 до 195). Для моніторингу кампаній ковзне середнє корисніше за денні значення, бо згладжує ефект вихідних.

## Q09 · window rank analysts

**Бізнес-питання.** BQ4. Як навантаження розподілене між аналітиками в межах організацій?

**Конструкція:** вікна RANK() і SUM() OVER (PARTITION BY); напівадитивна міра.

```sql
SELECT an.org_name AS organization, an.analyst_id, an.specialization,
       COUNT(*)                                     AS checks,
       RANK() OVER (PARTITION BY an.org_name ORDER BY COUNT(*) DESC) AS rank_in_org,
       round(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY an.org_name), 1) AS share_of_org_pct,
       round(AVG(f.hours_to_verdict), 1)            AS avg_hours,
       round(AVG(f.backlog_open), 2)                AS avg_backlog,
       round(SUM(f.effort_minutes) / 60.0, 1)       AS effort_hours
FROM fact_check f
JOIN dim_analyst an USING (analyst_key)
GROUP BY an.org_name, an.analyst_id, an.specialization
ORDER BY organization, rank_in_org;
```

**Результат** (12 рядків):

| organization | analyst_id | specialization | checks | rank_in_org | share_of_org_pct | avg_hours | avg_backlog | effort_hours |
|---|---|---|---|---|---|---|---|---|
| EUvsDisinfo | FCH-10 | соцмережі й боти | 257 | 1 | 56.7 | 10.2 | 1 | 374.7 |
| EUvsDisinfo | FCH-03 | медіа та фото | 196 | 2 | 43.3 | 6.9 | 0.6 | 211.8 |
| StopFake | FCH-06 | фінансові шахрайства | 273 | 1 | 42.5 | 6.9 | 1.62 | 290.1 |
| StopFake | FCH-02 | регіональні новини | 188 | 2 | 29.2 | 7.1 | 0.78 | 208.1 |
| StopFake | FCH-09 | медіа та фото | 182 | 3 | 28.3 | 7 | 0.52 | 194.7 |
| VoxCheck | FCH-08 | регіональні новини | 193 | 1 | 35.8 | 7 | 0.68 | 209.7 |
| VoxCheck | FCH-05 | здоров'я та медицина | 158 | 2 | 29.3 | 6.4 | 0.68 | 161.2 |
| VoxCheck | FCH-01 | військова тематика | 114 | 3 | 21.2 | 8.6 | 0.29 | 145.3 |
| VoxCheck | FCH-12 | загальна тематика | 74 | 4 | 13.7 | 7.3 | 0.11 | 82.7 |
| Детектор медіа | FCH-04 | соцмережі й боти | 251 | 1 | 49.9 | 9.1 | 0.82 | 331.4 |
| Детектор медіа | FCH-11 | здоров'я та медицина | 139 | 2 | 27.6 | 7.5 | 0.64 | 161 |
| Детектор медіа | FCH-07 | військова тематика | 113 | 3 | 22.5 | 8.2 | 0.36 | 135.7 |

**Інтерпретація.** В EUvsDisinfo і «Детектор медіа» один аналітик (соцмережі й боти) виконує 50–57 % перевірок організації і має найдовший час (9–10 год) — ризик вузького місця. backlog_open усереднено (AVG), бо це знімок черги: сума за весь період не має змісту.

## Q10 · scd2 trust

**Бізнес-питання.** BQ6. Чи вища частка хибних вердиктів у менш довірених авторів (довіра на момент перевірки, SCD2)?

**Конструкція:** SCD тип 2: з'єднання з версією виміру.

```sql
WITH cur AS (SELECT account_id, trust_label AS current_trust FROM dim_account WHERE is_current)
SELECT a.trust_level, a.trust_label AS trust_at_check,
       COUNT(*) AS checks,
       round(100.0 * AVG(CASE WHEN v.is_false THEN 1 ELSE 0 END), 1) AS false_pct,
       SUM(CASE WHEN NOT a.is_current THEN 1 ELSE 0 END) AS checks_on_old_version,
       string_agg(DISTINCT CASE WHEN c.current_trust <> a.trust_label THEN c.current_trust END, ', ') AS now_downgraded_to
FROM fact_check f
JOIN dim_account a USING (account_key)
JOIN cur c USING (account_id)
JOIN dim_verdict v USING (verdict_key)
GROUP BY a.trust_level, a.trust_label
ORDER BY a.trust_level;
```

**Результат** (4 рядків):

| trust_level | trust_at_check | checks | false_pct | checks_on_old_version | now_downgraded_to |
|---|---|---|---|---|---|
| 1 | низький | 1403 | 73.1 | 0 | — |
| 2 | знижений | 460 | 63.7 | 94 | низький |
| 3 | середній | 239 | 41.8 | 85 | знижений |
| 4 | високий | 36 | 41.7 | 14 | середній |

**Інтерпретація.** Частка хибних вердиктів спадає від 73 % для «низького» рівня до 42 % для «середнього» та «високого». 193 перевірки (9 %) прив'язані до старих версій акаунтів: після спростувань ці автори вже понижені (стовпець now_downgraded_to). Без SCD2 ці перевірки потрапили б до нижчого рівня довіри і спотворили б залежність.

## Незалежна перевірка (pandas)

1. **Q01, підсумки за класами ознак:** pandas `groupby` по Parquet дав ті самі кількості й частки хибних — **збіг**.
2. **Q08, NAR-05:** накопичена сума `cumsum()` і `rolling(7).mean()` по 123 днях збіглися з віконними функціями SQL — **збіг**; пік ковзного середнього 7.86 — 2026-10-05.
