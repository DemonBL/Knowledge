# ЛР9 · Відповідність компетентнісних питань шаблонам Cypher-шляхів

CQ1–CQ8 — це компетентнісні питання KQ1–KQ8 з ЛР7. CQ9–CQ11 додано для графової моделі:
вони стосуються шляхів поширення, яких не було в OWL-моделі.

| CQ | Питання | Шаблон шляху Cypher | Запит |
|---|---|---|---|
| CQ1 | Хто автор кожної публікації, який у нього індекс довіри, скільки спростованих дописів? | `(a:Account)-[:PUBLISHED]->(p:Publication)-[:MAKES_CLAIM]->(c:Claim)<-[:ABOUT]-(v:Verdict)` | Q01 |
| CQ2 | Яке офіційне джерело підтвердило чи спростувало яке твердження? | `(o:OfficialSource)-[:REFUTES\|CONFIRMS]->(c:Claim)` | Q02 |
| CQ3 | Який вердикт винесено щодо кожного твердження, які ще не перевірено? | `(c:Claim)` + `OPTIONAL (c)<-[:ABOUT]-(v:Verdict)<-[:ISSUED]-(f:FactChecker)` | Q03 |
| CQ4 | Які публікації містять повторно використані медіафайли? | `(p:Publication)-[:CONTAINS]->(m:Media)-[:VERIFIED_WITH]->(t:Tool)` + умова на дати | Q04 |
| CQ5 | Які інструменти застосовує кожен фактчекер? | `(f:FactChecker)-[:USES]->(t:Tool)` + `OPTIONAL (f)-[:ISSUED]->(:Verdict)-[:BASED_ON]->(t)` | Q05 |
| CQ6 | Які твердження належать до одного наративу, яке охоплення ланцюжків? | `(n:Narrative)<-[:PART_OF]-(c:Claim)<-[:MAKES_CLAIM]-(o:Publication)<-[:DERIVED_FROM*0..4]-(p)` | Q06 |
| CQ7 | На яких доказах ґрунтується кожен вердикт? | `(v:Verdict)-[:BASED_ON]->(e:OfficialSource\|Tool\|FactCheckOrg)` | Q07 |
| CQ8 | Які правила сформулював кожен фактчекер? | `(f:FactChecker)` + `OPTIONAL (f)-[:FORMALIZED_IN]->(r:Rule)` | Q08 |
| CQ9 | Через скільки кроків контент першоджерела доходить до звичайних користувачів? | `shortestPath((src:Account)-[:PUBLISHED\|DERIVED_FROM*..10]-(u:Account))` | Q09 |
| CQ10 | Що треба позначити після спростування офіційним джерелом? (аналіз впливу) | `(o)-[:REFUTES]->(c)<-[:MAKES_CLAIM]-(origin)<-[:DERIVED_FROM*0..4]-(p)<-[:PUBLISHED\|REPOSTED]-(acc)` | Q10 |
| CQ11 | Кого зачепить блокування акаунта-першоджерела? (аналіз впливу) | `(src)-[:PUBLISHED]->(own)<-[:DERIVED_FROM*1..4]-(d)-[:MAKES_CLAIM]->()-[:PART_OF]->(n)` | Q11 |

## Властивості походження на зв'язках

Кожен зв'язок має три властивості:
- `source` — звідки взято факт: `telegram_export`, `factcheck_registry`, `official_statement`, `analyst_case_file`, `propagation_analysis`, `nlp_claim_extraction` тощо;
- `confidence` — впевненість у факті, від 0 до 1. Наприклад, зв'язок `MAKES_CLAIM`, виділений автоматично, має 0,75–0,98, а запис фактчекінгового реєстру — 1,0;
- `validFrom` — дата, з якої факт чинний (`date`).

У зв'язку `REPOSTED` є ще `minutesAfter`: через скільки хвилин після публікації зроблено репост. Ця властивість потрібна для правила RULE-3.

## Порівняння зі схемою ЛР7 (OWL) і ЛР8 (RDF)

| Елемент ЛР7–8 | У графі LPG (ЛР9) | Чому так |
|---|---|---|
| Класи AkauntAvtor, Publikatsiia, Tverdzhennia, Naratyv, Mediafail, Faktcheker, InstrumentVeryfikatsii, OfitsiineDzherelo, FaktchekinhovaOrhanizatsiia, PravyloVeryfikatsii | Мітки Account, Publication, Claim, Narrative, Media, FactChecker, Tool, OfficialSource, FactCheckOrg, Rule | Основні сутності, між якими будуються шляхи, стали мітками |
| Підкласи Verdykt{Pravda, Manipuliatsiia, Feik, NemozhlyvoPereviryty} | Одна мітка Verdict + властивість `category` | У LPG немає ієрархії класів. Категорію зручніше фільтрувати властивістю з індексом `verdict_category` |
| Надкласи DzhereloInformatsii, ObiektPerevirky, ZasibPerevirky | Не перенесено | Без reasoner'а надкласи нічого не дають. Узагальнені запити пишуться через `labels` (`:OfficialSource\|Tool\|FactCheckOrg`) |
| SKOS-шкала індексу довіри (ЛР8) | Властивості `trust` (мітка) і `trustLevel` (1–4) | Рівень порівнюється числом, як `skos:notation` у ЛР8; окремі вузли-концепти не потрібні |
| Object properties publikuie, vysuvaie, mistyt, nalezhytDoNaratyvu, vynosyt, vynosytsiaSchodo, gruntuietsiaNaDokazi, zastosovuie, formalizuietsiaU | Типи PUBLISHED, MAKES_CLAIM, CONTAINS, PART_OF, ISSUED, ABOUT, BASED_ON, USES, FORMALIZED_IN | Відповідність 1:1. Обернену `maieAvtora` не створюємо: у Cypher зв'язок обходиться в обидва боки |
| pidtverdzhuie / sprostovuie (ЛР8) | CONFIRMS / REFUTES | Два окремі типи, як після розділення властивості в ЛР8 |
| PerevirkaPodii (prov:Activity) | Не перенесено як вузол | Час і джерело факту тепер зберігаються у властивостях зв'язків (`validFrom`, `source`), яких у RDF без реїфікації немає |
| — | Нові типи DERIVED_FROM, REPOSTED, WORKS_FOR | Мережа поширення — головна причина переходу на граф. Шляхи змінної довжини, shortestPath і PageRank по ній природні в LPG |
| Обмеження exactly 1 (OWL), SHACL-шаблони (ЛР8) | Унікальні обмеження `id`, індекси | У Neo4j Community доступні обмеження унікальності, а не кардинальності. Повноту даних перевіряє запит Q03 (OPTIONAL MATCH) |
