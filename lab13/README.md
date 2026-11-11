# ЛР13 · Видобування знань із текстів (Domain Knowledge Hub, гілка lab13)

Тематична область: «Аналіз достовірності інформації».

Задачі:
- розпізнавання сутностей (8 типів);
- витяг відношень (10 типів) двома методами — А (правила + spaCy) і Б (LLM + JSON-схема);
- золотий набір;
- оцінювання;
- граф із походженням і патерни.

## Структура

| Шлях | Результат | Зміст |
|---|---|---|
| `docs/extraction_schema.md`, `src/schema.py` | Р1 | типи, відношення, інструкція розмітки, JSON-схема, нормалізація, пілот |
| `annotation/gold_spec.py`, `annotation/build_gold.py`, `data/corpus.jsonl`, `data/docs/*.txt`, `data/gold.jsonl`, `docs/gold_card.md` | Р2 | корпус (23 документи), золотий набір, розділення dev/test |
| `data/kappa_items.jsonl`, `annotation/annotate_b.py`, `annotation/kappa.py`, `results/kappa.json` | Р2 | другий розмітник, κ |
| `src/extract_rules.py`, `src/extract_llm.py`, `results/rules_*.jsonl`, `results/llm_*.jsonl` | Р3 | два методи витягу з provenance |
| `src/evaluate.py`, `src/hybrid.py`, `docs/extraction_eval.md` | Р4 | P/R/F1, цитати, вартість, помилки, рекомендація |
| `src/normalize.py`, `data/kb_aliases.json`, `src/build_graph.py`, `data/graph_load.ttl`, `data/graph_load.cypher`, `results/graph_proof.json` | Р5 | нормалізація, зв'язування, граф із походженням |
| `src/patterns.py`, `docs/patterns.md` | Р5 | асоціативні правила, перевірка, рішення |
| `llm_log/`, `claims/claims.csv` | протокол | журнали LLM і таблиця тверджень |

## Запуск з нуля

Залежності:
- Python 3.11+;
- spaCy 3.8 і `uk_core_news_sm` 3.8.0 (з pymorphy3 та pymorphy3-dicts-uk);
- scikit-learn, mlxtend, pandas, scipy;
- Oxigraph 0.4 (CLI `ox`) — для графа;
- Ollama з моделями `qwen2.5:7b` і `gemma3:4b` — для методу Б і розмітника B.

Seed: генерація вибірки κ — 13; LLM — seed 42 (qwen) і 7 (gemma), temperature 0 (повтори — 0,3).

```bash
pip install spacy==3.8.* pymorphy3 pymorphy3-dicts-uk scikit-learn mlxtend pandas scipy
pip install https://github.com/explosion/spacy-models/releases/download/uk_core_news_sm-3.8.0/uk_core_news_sm-3.8.0-py3-none-any.whl

python annotation/build_gold.py                   # корпус і золотий набір із специфікації
python annotation/make_kappa_items.py             # 42 пари для κ
python src/extract_rules.py --split dev           # метод А на dev (налаштування) …
python src/extract_rules.py --split test          # … і один прогін на test після заморожування
python src/extract_rules.py --split all
python annotation/annotate_b.py                   # розмітник B (gemma3:4b, Ollama)
python src/extract_llm.py --stage all             # метод Б: v1/v2 на dev → вибір → test (qwen2.5:7b, Ollama)
python annotation/kappa.py                        # κ
python src/evaluate.py --split test --pred results/rules_test.jsonl --pred results/llm_test.jsonl
python src/hybrid.py                              # маршрутизація за dev, гібрид на test
python src/make_eval_doc.py                       # docs/extraction_eval.md
python src/build_graph.py --inputs results/hybrid_all.jsonl --ox <шлях до ox>
python src/patterns.py && python src/patterns_doc.py
```

На Windows кроки з Ollama запускає `run_lab13.bat`. Ключі API не потрібні: моделі локальні. Внутрішні документи синтетичні (створені в ЛР 10, реальних персональних даних немає); у методі Б їх обробляє лише локальна модель.
