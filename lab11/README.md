# ЛР 11 · Чат-бот на основі гібридного сховища (RAG + граф)

Передумови: ЛР 9 (Neo4j з графом) і ЛР 10 (корпус, моделі) виконано; Ollama з qwen2.5:7b і gemma3:4b; venv F:\kms_tools\venv (Python 3.13).
Версії: див. ..\logs\pip_freeze.txt. Seed: генератор 42, суддя 7, дані ЛР9 — 42.

    run_lab11.bat      # демо RAG → «текст» vs «текст + підграф» (12) → 31 тест (k=5) → оптимізація (k=3)   ~45–60 хв
    run_api_demo.bat   # FastAPI (uvicorn) + сценарії: ролі, 401/403/404/422/429, OpenAPI                    ~3–5 хв
    python api\test_rate_limit.py   # перевірка ліміту 10/60 с (TestClient)
    python eval\correct_stem.py     # виправлена метрика правильності
    python eval\manual_check.py     # ручна перевірка судді, κ

Ручний запуск API:  F:\kms_tools\venv\Scripts\python -m uvicorn main:app --app-dir api --port 8000
Ключі генеруються в api\keys.local.json (у .gitignore) — у коді та звіті їх немає.

Артефакти: src/rag.py, prompts/rag_v1.md (Р1); src/graph_context.py, docs/graph_vs_text.md (Р2);
api/main.py, docs/api.md, docs/openapi.json (Р3); eval/rag_eval.jsonl, docs/rag_eval.md, eval/manual_check.json,
eval/failures.json (Р4); docs/rag_optimization.md (Р5); results/*.json, logs/rag_log.jsonl, llm_log/, claims/claims.csv.
