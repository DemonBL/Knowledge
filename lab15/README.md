# ЛР15 · LLM-агент над гібридним сховищем знань (Domain Knowledge Hub, гілка lab15)

Агент-аналітик на LangGraph з інструментами лише для читання (граф, документи, OLAP), MCP-сервер, оцінювання на сценаріях, red teaming і людина в циклі для запису знань.

| Шлях | Результат | Зміст |
|---|---|---|
| `docs/agent_spec.md`, `docs/img/agent_graph.png` | Р1 | інструменти (JSON-схеми), політики, діаграма станів, 12 сценаріїв |
| `agent/tools.py`, `agent/agent.py`, `agent/policies.py`, `agent/llm.py`, `mcp_server/*`, `traces/` | Р2 | агент LangGraph, read-only інструменти, MCP-сервер, траси |
| `tests/agent_scenarios.jsonl`, `agent/run_eval.py`, `agent/replay_verify.py`, `docs/agent_eval.md`, `results/scen_*.json` | Р3 | метрики, невдачі й виправлення v1 → v3.1 |
| `tests/attacks*.jsonl`, `docs/agent_security*.md`, `results/attacks_*.json` | Р4 | 13 атак (7 типів), захисти D1–D6, до/після |
| `agent/propose_fact.py`, `agent/hitl_review.py`, `agent/fact_shapes.ttl`, `data/*`, `docs/hitl.md` | Р5 | propose_fact, ризики, схвалення людиною, аудит |
| `llm_log/`, `claims/claims.csv` | протокол | журнали LLM і таблиця тверджень |

## Запуск

**Залежності.**
- Python 3.13.
- `langgraph 1.2`, `mcp 2.3`, `rdflib 7`, `pyshacl 0.40`, `duckdb`, `sqlglot`, `pyyaml`, `sentence-transformers` (e5), `numpy`, `matplotlib`.
- Ollama з моделями `qwen2.5:7b` (агент) і `gemma3:4b` (червона команда).
- Дані з ЛР9–ЛР14 у сусідніх папках Hub: `lab14/data/clean`, `lab12/data/lab12.duckdb`, `lab12/semantic`.

**Seed і параметри:**
- агент: temperature 0, seed 42;
- червона команда: temperature 0.7, seed 15.

```bat
run_lab15_round1.bat   :: red team, сценарії v1, атаки без захисту (v1), MCP-демо
run_lab15_round2.bat   :: закріплення маніфестів, сценарії v2, атаки без захисту (v2), атаки із захистом, HITL (інтерактивно)
run_lab15_round3.bat   :: діагностика, сценарії v3, доповнення атак без захисту
```

```bash
python agent/replay_verify.py      # v3.1: повторна перевірка чернеток r3 виправленим верифікатором
python agent/make_docs.py          # docs/agent_eval.md, agent_security_table.md, hitl.md, рисунки
python agent/agent.py "Який вердикт щодо CLM-13?" --role analyst --version v3   # одиночний запит
python mcp_server/demo_client.py   # MCP: список інструментів і 3 виклики
```

**Безпека.**
- Ключів API немає: усі моделі локальні.
- Внутрішні документи синтетичні й обробляються лише локально.
- Сирі SPARQL і SQL дозволені тільки в профілі permissive (для red teaming) і лише над копіями сховищ у пам'яті.
