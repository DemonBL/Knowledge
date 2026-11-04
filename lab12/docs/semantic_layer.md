# ЛР12 · Семантичний шар

Файл метрик: `semantic/metrics.yml` (версія 1.0.0); генератор SQL: `semantic/semantic.py` (клас `SemanticLayer`, метод `metric_sql`).

## Метрики

| Назва | Визначення | Формула | Одиниця | Адитивність | Власник | Джерела | Обмеження | Перегляд | Статус |
|---|---|---|---|---|---|---|---|---|---|
| `checks_count` | Кількість завершених перевірок публікацій (зерно факту). | `SUM(f.check_count)` | шт. | адитивна | Хоптій Д. (аналітик Hub) | fact_check | Рахує перевірки, а не унікальні публікації; повторна перевірка тієї самої публікації — окремий рядок. | 2026-11-04 | approved |
| `false_verdict_rate` | Відсоток перевірок, що завершилися вердиктом «фейк» або «маніпуляція». | `round(100.0 * SUM(CASE WHEN v.is_false THEN f.check_count ELSE 0 END) / SUM(f.check_count), 1)` | % | неадитивна (відношення; не усереднювати частки підгруп) | Хоптій Д. (аналітик Hub) | fact_check, dim_verdict | Залежить від відбору публікацій на перевірку (перевіряють підозрілі) — це не частка фейків у мережі. «Неможливо перевірити» рахується як не хибний. | 2026-11-04 | approved |
| `false_reach` | Сума поширень на момент перевірки для публікацій із вердиктом «фейк» або «маніпуляція». | `SUM(CASE WHEN v.is_false THEN f.shares_at_check ELSE 0 END)` | поширень | адитивна | Хоптій Д. (аналітик Hub) | fact_check, dim_verdict | Знімок на момент перевірки; подальше поширення не враховано. Одна аудиторія може рахуватися кілька разів. | 2026-11-04 | approved |
| `avg_hours_to_verdict` | Середня тривалість від виявлення публікації до винесення вердикту. | `round(AVG(f.hours_to_verdict), 1)` | год | неадитивна (лише AVG / перцентилі) | Хоптій Д. (аналітик Hub) | fact_check | Чутлива до викидів (запит до експерта до 64 год) — для SLA дивитися також p90. | 2026-11-04 | approved |
| `sla_compliance_rate` | Відсоток перевірок, завершених у межах SLA регламенту v2.0: високий пріоритет ≤ 12 год, середній ≤ 24 год, низький ≤ 48 год. | `round(100.0 * AVG(CASE WHEN f.sla_met THEN 1 ELSE 0 END), 1)` | % | неадитивна (відношення) | Хоптій Д. (аналітик Hub) | fact_check, регламент перевірки v2.0 | Пороги для середнього й низького пріоритету — припущення (у регламенті явно лише 12 год для високого); статус draft до підтвердження. | 2026-11-04 | draft |
| `avg_backlog` | Середня кількість відкритих справ аналітика на момент винесення вердикту. | `round(AVG(f.backlog_open), 2)` | справ | напівадитивна (сумувати лише між аналітиками на один момент; за часом — AVG) | Хоптій Д. (аналітик Hub) | fact_check | Знімок у моменти вердиктів, а не рівномірна вибірка в часі. | 2026-11-04 | approved |
| `evidence_per_false_verdict` | Середня кількість доказів у перевірках із вердиктом «фейк»/«маніпуляція» (регламент вимагає ≥ 2). | `round(SUM(CASE WHEN v.is_false THEN f.evidence_count ELSE 0 END) * 1.0 / NULLIF(SUM(CASE WHEN v.is_false THEN 1 ELSE 0 END), 0), 2)` | доказів | неадитивна (відношення двох адитивних сум) | Хоптій Д. (аналітик Hub) | fact_check, dim_verdict, регламент перевірки v2.0 | Не показує незалежність доказів — лише їх кількість. | 2026-11-04 | approved |

## Як працює генерація SQL

1. Метрика має формулу та список потрібних з'єднань; вимір — колонку і з'єднання.
2. `metric_sql(metrics, dimensions, filters)` перевіряє, що всі назви є в каталозі (білий список). Потім додає лише потрібні JOIN, будує SELECT / WHERE / GROUP BY і екранує літерали фільтрів.
3. Та сама функція формує текстовий каталог для підказки text-to-SQL (`catalog_text()`), тож LLM бачить ті самі визначення, що й аналітик.

Приклад: `metric_sql(['false_verdict_rate', 'checks_count'], ['signal_class'], {'month': [8, 9]})` →

```sql
SELECT s.class_label AS signal_class, round(100.0 * SUM(CASE WHEN v.is_false THEN f.check_count ELSE 0 END) / SUM(f.check_count), 1) AS false_verdict_rate, SUM(f.check_count) AS checks_count
FROM fact_check AS f
JOIN dim_verdict v ON v.verdict_key = f.verdict_key
JOIN dim_taxonomy s ON s.taxonomy_key = f.signal_key
JOIN dim_date d ON d.date_key = f.date_key
WHERE d.month IN (8, 9)
GROUP BY 1
ORDER BY 1
```

## Перевірка узгодженості

**Яка частка хибних вердиктів за класами ознак?** (false_verdict_rate × signal_class). Шляхи: semantic layer; Q01 ROLLUP (grouping_id = 1); pandas. Результат: **збіг**.

```sql
SELECT s.class_label AS signal_class, round(100.0 * SUM(CASE WHEN v.is_false THEN f.check_count ELSE 0 END) / SUM(f.check_count), 1) AS false_verdict_rate, SUM(f.check_count) AS checks_count
FROM fact_check AS f
JOIN dim_verdict v ON v.verdict_key = f.verdict_key
JOIN dim_taxonomy s ON s.taxonomy_key = f.signal_key
GROUP BY 1
ORDER BY 1
```

Значення: `{"За автором": 70.3, "За змістом": 67.7, "За медіа": 60.0}`

**Скільки в середньому триває перевірка і яка частка SLA за класами методів?** (avg_hours_to_verdict, sla_compliance_rate × method_class). Шляхи: semantic layer; Q04 GROUPING SETS (method_class); pandas. Результат: **збіг**.

```sql
SELECT m.class_label AS method_class, round(AVG(f.hours_to_verdict), 1) AS avg_hours_to_verdict, round(100.0 * AVG(CASE WHEN f.sla_met THEN 1 ELSE 0 END), 1) AS sla_compliance_rate
FROM fact_check AS f
JOIN dim_taxonomy m ON m.taxonomy_key = f.method_key
GROUP BY 1
ORDER BY 1
```

Значення: `{"Експертна перевірка": {"avg_hours_to_verdict": 12.8, "sla_compliance_rate": 92.8}, "Звірка з базами": {"avg_hours_to_verdict": 4.6, "sla_compliance_rate": 100.0}, "Технічна верифікація": {"avg_hours_to_verdict": 7.3, "sla_compliance_rate": 99.1}}`

**Яке охоплення хибних публікацій за типами платформ?** (false_reach × platform_type). Шляхи: semantic layer; Q03 CUBE (grouping_id = 1); pandas. Результат: **збіг**.

```sql
SELECT p.platform_type AS platform_type, SUM(CASE WHEN v.is_false THEN f.shares_at_check ELSE 0 END) AS false_reach
FROM fact_check AS f
JOIN dim_verdict v ON v.verdict_key = f.verdict_key
JOIN dim_platform p ON p.platform_key = f.platform_key
GROUP BY 1
ORDER BY 1
```

Значення: `{"відеоплатформа": 114754.0, "месенджер": 706850.0, "соцмережа": 363321.0}`

Без семантичного шару «частку хибних» можна порахувати по-різному: усереднити частки підгруп, рахувати «неможливо перевірити» як хибний, брати поточну довіру замість історичної. Тоді різні звіти дають різні числа. Єдина формула в `metrics.yml` усуває цю неоднозначність.
