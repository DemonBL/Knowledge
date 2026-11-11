# ЛР12 · OLAP-куб на основі таксономії (Domain Knowledge Hub, гілка lab12)

Тематична область: «Аналіз достовірності інформації». Бізнес-процес — перевірка публікацій фактчекерами.

## Структура

| Шлях | Результат | Зміст |
|---|---|---|
| `docs/star_design.md`, `sql/ddl.sql`, `docs/img/star.png` | Р1 | зерно, 6 бізнес-питань, 7 вимірів (таксономія з IRI), міри, SCD, DDL, діаграма |
| `taxonomy/taxonomy.ttl`, `etl/taxonomy.py` | Р1 | таксономія ЛР 4–5 у SKOS (28 понять з IRI) |
| `etl/generate.py`, `etl/load.py`, `data/*.parquet`, `data/VERSION.json`, `results/dq_report.*`, `sql/checks/orphans.sql` | Р2 | генератор (seed 12), ELT, 8 перевірок якості, Parquet + версія |
| `sql/olap/*.sql`, `etl/olap_run.py`, `docs/olap_results.md`, `results/olap/*.csv`, `results/olap_verification.json` | Р3 | 11 OLAP-запитів, drill-down, перевірка в pandas |
| `semantic/metrics.yml`, `semantic/semantic.py`, `semantic/consistency.py`, `docs/semantic_layer.md` | Р4 | 7 метрик, генерація SQL, узгодженість |
| `t2sql/t2sql.py`, `tests/t2sql_gold.jsonl`, `tests/t2sql.jsonl`, `tests/test_guard.py`, `dashboard/*`, `docs/t2sql_eval.md` | Р5 | text-to-SQL із захистами, оцінювання, панель, ризики |
| `llm_log/`, `claims/claims.csv` | протокол | журнал LLM і таблиця тверджень |

## Запуск з нуля

Версії: Python 3.11+, duckdb 2.0.0, pandas ≥ 2.2, sqlglot 30.29.0, rdflib 7, pyyaml, pyarrow, matplotlib, plotly 6+. Text-to-SQL потребує Ollama з моделлю `qwen2.5:7b`.

```bash
pip install duckdb==2.0.0 sqlglot==30.29.0 pandas pyarrow rdflib pyyaml matplotlib plotly
python etl/taxonomy.py            # SKOS-таксономія → taxonomy/taxonomy.ttl
python etl/generate.py            # синтетичні події (seed = 12) → data/raw/*.csv
python etl/load.py                # ELT → data/lab12.duckdb, data/*.parquet, data/VERSION.json, results/dq_report.*
python etl/olap_run.py            # OLAP-запити → docs/olap_results.md + перевірка pandas
python semantic/consistency.py    # семантичний шар → docs/semantic_layer.md
python tests/test_guard.py        # тести захистів text-to-SQL (18)
python t2sql/t2sql.py --mock gold # конвеєр без LLM
python t2sql/t2sql.py --model qwen2.5:7b   # оцінювання на 15 питаннях (на Windows: run_lab12_t2sql.bat)
python dashboard/build_dashboard.py        # панель → dashboard/dashboard.html, v1–v5.png
```

Ключі API не потрібні: модель локальна, Ollama. Персональні дані не використовуються, бо дані синтетичні.
