# ЛР 11 · Чат-бот на основі гібридного сховища (RAG + граф)

Тематична область: «Аналіз достовірності інформації» (Domain Knowledge Hub).

## Передумови

- ЛР 9: граф у Neo4j 5.26 (пароль — змінна середовища `NEO4J_PASSWORD` або файл `neo4j_password.txt` у `KMS_TOOLS`).
- ЛР 10: корпус `lab10/data/corpus.jsonl` і модуль пошуку `lab10/src/search_core.py` (додано в цю гілку як залежність).
- Ollama з моделями `qwen2.5:7b` (генератор) і `gemma3:4b` (суддя).
- Python 3.11+, залежності — `requirements.txt` у корені. Seed: генератор 42, суддя 7.

## Запуск (з кореня репозиторію)

```bash
pip install -r requirements.txt
python lab11/src/run_lab11.py                 # демо RAG → «текст» vs «текст + підграф» (12) → 31 тест (k=5) → оптимізація (k=3)
cd lab11
python -m uvicorn main:app --app-dir api --port 8000   # API (FastAPI); ключі генеруються в api/keys.local.json (у .gitignore)
python api/api_demo.py                        # сценарії: ролі, 401/403/404/422/429, OpenAPI
python api/test_rate_limit.py                 # перевірка ліміту 10 запитів / 60 с
python eval/correct_stem.py                   # виправлена метрика правильності
python eval/manual_check.py                   # ручна перевірка судді, κ
```

## Артефакти

| Результат | Файли |
|---|---|
| Р1 | `src/rag.py`, `prompts/rag_v1.md` |
| Р2 | `src/graph_context.py`, `docs/graph_vs_text.md` |
| Р3 | `api/main.py`, `docs/api.md`, `docs/openapi.json` |
| Р4 | `eval/rag_eval.jsonl`, `docs/rag_eval.md`, `eval/manual_check.json`, `eval/failures.json` |
| Р5 | `docs/rag_optimization.md` |
| Результати | `results/*.json`, `logs/rag_log.jsonl`, `logs/api_log.jsonl` |
| Протокол «LLM-експерт» | `llm_log/`, `claims/claims.csv` |
