# ЛР14 · Якість, очищення та оцінювання сховища знань (Domain Knowledge Hub, гілка lab14)

Тематична область: «Аналіз достовірності інформації».

Сховище, яке оцінюємо (усе це використовує RAG з ЛР11):
- граф розслідувань ЛР9 (Neo4j; знімок у `lab09/data/*.csv`);
- корпус ЛР10 (`lab10/data/corpus.jsonl`, `docs.jsonl`);
- реєстр сутностей Hub — ЛР8 RDF (`data/lab08_data.ttl`), вузли ЛР9 і сутності, витягнуті в ЛР13.

Версії сховища:
- **baseline** — `kb-2026.11-v0`, вихідні дані ЛР9/ЛР10;
- **clean** — `kb-2026.11-v1`, результат ЛР14 у `data/clean/` плюс міграція Neo4j.

## Структура

| Шлях | Результат | Зміст |
|---|---|---|
| `quality/kb.py` | — | доступ до сховища, RDF-знімок, реєстр сутностей |
| `quality/profile.py`, `quality/metrics.json`, `quality/profile_baseline.md`, `quality/accuracy_sample.csv`, `data/source_inventory.json` | Р1 | 15 метрик за 8 вимірами, експертна вибірка точності, baseline |
| `quality/dedup.py`, `quality/make_gold.py`, `quality/pairs_gold.csv`, `data/clean/entity_registry.json` | Р2 | entity resolution: blocking, порівняння, поріг на dev, P/R на test, злиття з provenance, unmerge |
| `quality/conflicts.py`, `quality/conflicts.md`, `quality/decisions.csv`, `data/clean/alternatives.jsonl` | Р3 | суперечності, стратегії, альтернативи, журнал рішень |
| `quality/clean.py`, `data/clean/*` (CSV графа, корпус, `03_quality_fix.cypher` / `03_quality_undo.cypher`) | Р3–Р5 | очищення baseline → clean |
| `quality/shapes.ttl`, `quality/schemas.json`, `quality/tests/*`, `quality/gate.py`, `quality/defects.py`, `.github/workflows/quality.yml`, `quality/reports/` | Р4 | 19 перевірок (SHACL, SPARQL, pytest/GE, JSON Schema), gate, тренд, 3 дефекти |
| `src/pc_run.py`, `run_lab14.bat`, `quality/after_report.md` | Р5 | міграція Neo4j, LLM-суддя ER, повтор тестів RAG ЛР11, «до/після» |
| `llm_log/`, `claims/claims.csv` | протокол | журнали LLM і таблиця тверджень |

## Запуск з нуля

**Залежності:**
- Python 3.11+;
- `pandas`, `scikit-learn`, `rdflib 7`, `pyshacl 0.40`, `rapidfuzz 3`, `jsonschema 4`, `pytest 9`, `matplotlib`;
- для частини на ПК — Neo4j 5.26 + GDS, Ollama (`qwen2.5:7b`, `gemma3:4b`), модель ембедингів ЛР10.

**Seed:**
- вибірка пар — 14;
- dev/test — 14;
- LLM: генератор 42 (temperature 0.1), суддя RAG 7 (temperature 0), суддя ER 42 (temperature 0).

Дата виміру фіксована (`REF_DATE = 2026-11-06`).

```bash
pip install pandas scikit-learn rdflib pyshacl rapidfuzz jsonschema pytest matplotlib

# Р1 — профіль baseline
python lab14/quality/make_accuracy.py            # потребує data/clean/entity_registry.json (після dedup)
python lab14/quality/profile.py baseline

# Р2 — entity resolution
python lab14/quality/dedup.py candidates
python lab14/quality/make_gold.py                # розмітка 140 пар (dev 70 / test 70)
python lab14/quality/dedup.py eval               # поріг на dev, P/R/F1 на test (+ LLM-суддя, якщо є results/dedup_llm_judge.json)
python lab14/quality/dedup.py merge              # кластери, журнал злиттів, демонстрація unmerge

# Р3 — суперечності та очищення
python lab14/quality/conflicts.py baseline
python lab14/quality/clean.py                    # → data/clean
python lab14/quality/conflicts.py clean

# Р4 — перевірки й gate
python lab14/quality/gate.py --version baseline --label "до очищення"     # BLOCKED
python lab14/quality/gate.py --version clean --label "після очищення"     # PASSED
python lab14/quality/defects.py
python lab14/quality/gate.py --kb-dir data/defects --label "3 дефекти"   # BLOCKED

# Р5 — повторний вимір і RAG (на ПК: Neo4j + Ollama, ~25 хв)
python lab14/quality/profile.py clean && python lab14/quality/profile.py report
lab14\run_lab14.bat                              # src/pc_run.py: міграція Neo4j, LLM-суддя ER, 31 тест RAG
python lab14/src/make_after.py                   # quality/after_report.md, рисунки
```

## Безпека та доступ

- Ключі API не потрібні: усі моделі локальні.
- Пароль Neo4j береться зі змінної `NEO4J_PASSWORD` або з файлу поза репозиторієм.
- Внутрішні документи синтетичні (ЛР10) і обробляються лише локальними моделями.
