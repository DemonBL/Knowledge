# ЛР16 · Рекомендаційна система та фінальний демонстратор Domain Knowledge Hub

Тема: аналіз достовірності інформації. Ця лабораторна завершує Hub:
- рекомендації фрагментів знань із поясненнями зі шляхів графа;
- офлайн-оцінка;
- холодний старт;
- демонстратор у Docker Compose (граф + API + UI, агент ЛР15);
- whitepaper.

| Шлях | Результат | Зміст |
|---|---|---|
| `reco/items.py`, `reco/models.py`, `reco/filters_demo.py`, `docs/reco_design.md` | Р1 | каталог і граф, 4 підходи, фільтри, гібрид, обмеження |
| `reco/data_gen.py`, `reco/eval.py`, `reco/make_docs.py`, `docs/reco_eval.md`, `results/reco_eval_*.json` | Р2 | дані, часове розбиття, метрики, інтервали, вибір конфігурації |
| `reco/explain.py`, `reco/cold_start.py`, `docs/cold_start.md`, `results/explanations.json`, `results/cold_start_*.json` | Р3 | пояснення + перевірка, два сценарії холодного старту |
| `docker-compose.yml`, `docker/*`, `api/*`, `ui/app.py`, `demo/*`, `docs/demo_script.md`, `logs/` | Р4 | демонстратор, сценарій на 7 хв, журнали запуску |
| `docs/whitepaper.pdf` (джерело `whitepaper/`) | Р5 | whitepaper, 10 сторінок |
| `llm_log/`, `claims/claims.csv` | протокол | журнал LLM-експерта, таблиця тверджень |

## Передумови

- **Docker Desktop** (Windows/macOS) або Docker Engine + Compose v2. Перевірено на Docker Desktop for Windows (WSL2).
- **Ollama** на хості з моделлю `qwen2.5:7b`. Потрібна лише для `/ask` (агент) і перефразування пояснень; рекомендації, пошук і граф працюють без неї.
- Сусідні теки Hub з даними попередніх ЛР; потрібне лише це:
  - `common/`;
  - `lab10/src/`;
  - `lab12/semantic/`, `lab12/t2sql/`, `lab12/data/lab12.duckdb`;
  - `lab13/results/entity_linking.json`;
  - `lab14/quality/`, `lab14/data/`;
  - `lab15/agent/`.
- Для офлайн-оцінки поза Docker: Python 3.12+ з пакетами з `docker/requirements.txt`. Для e5 також `sentence-transformers` і кеш моделі `intfloat/multilingual-e5-small`.

## Запуск однією командою

```bash
cd lab16
docker compose -p hub16 up -d --build
```

| Адреса | Що там |
|---|---|
| http://127.0.0.1:8501 | UI (Streamlit) |
| http://127.0.0.1:8000/docs | API (OpenAPI) |

Граф доступний лише всередині мережі compose (`graph:7878`).

| Дія | Команда |
|---|---|
| Зупинка | `docker compose -p hub16 down` |
| Повне очищення: образи, том графа | `docker compose -p hub16 down -v --rmi all` |
| Журнали сервісів | `docker compose -p hub16 logs -f` |
| Журнал запитів API | `logs/api_requests.jsonl` |

**Запуск з нуля з журналом.** Скрипт `run_lab16.bat` виконує все по черзі:
1. e5-вектори;
2. оцінка;
3. пояснення LLM;
4. `down -v --rmi all` → `build --no-cache --pull` → `up -d`;
5. очікування health;
6. 5 демо-запитів.

Лише етап Docker (з нуля + демо) — `run_lab16_docker.bat`.

Журнали: `logs/lab16_run.log`, `logs/lab16_docker.log`, `logs/compose.log`, `logs/demo.log`, `results/docker_run.json`, `demo/demo_run.md`.

**Без Docker (резервний режим):** `python src/run_local.py` — ті самі три сервіси як локальні процеси.

## Сервіси

| Сервіс | Образ / команда | Порт | Залежить від |
|---|---|---|---|
| graph | `hub16` · `python lab16/api/graph_service.py` — pyoxigraph, SPARQL лише SELECT/ASK, персистентний том `graph_data` | 7878 (внутр.) | — |
| api | `hub16` · `python lab16/api/app.py` — FastAPI: `/health`, `/recommend`, `/explain`, `/topics`, `/search`, `/ask`, `/sparql` | 127.0.0.1:8000 | graph (healthy), Ollama на хості |
| ui | `hub16` · `streamlit run lab16/ui/app.py` | 127.0.0.1:8501 | api (healthy) |

Один образ `python:3.12-slim` без torch: e5-вектори фрагментів рахуються заздалегідь і копіюються в образ. Порти прив'язані до 127.0.0.1, контейнери працюють від непривілейованого користувача.

## Змінні середовища (`.env.example`)

| Змінна | Типово | Призначення |
|---|---|---|
| `OLLAMA_URL` | `http://host.docker.internal:11434` | Ollama на хості |
| `OLLAMA_MODEL` | `qwen2.5:7b` | модель агента |
| `RECO_EMB` | `auto` | `e5`, якщо є `data/item_vecs_e5.npy`, інакше `lsa` |
| `API_PORT`, `UI_PORT` | 8000, 8501 | порти на хості |
| `GRAPH_URL`, `LOG_DIR`, `HUB_DENSE` | задаються в compose | адреса графа, тека журналів, e5 у пошуку (0 у контейнері) |

Секретів немає: ключів API не потрібно, LLM локальна.

## Тестові дані

| Файл | Зміст |
|---|---|
| `data/interactions.csv`, `data/users.csv` | синтетичні журнали (seed 16; `python reco/data_gen.py --seed 16`) |
| `data/hub_graph.nt` | RDF-знімок очищеного графа ЛР14 (8322 трійки) |
| `data/item_vecs_e5.npy` (+`.ids`) | e5-вектори фрагментів (`python src/pc_run.py e5`) |

Тестові користувачі:
- admin: U001–U004;
- analyst: U005–U046 (наприклад, U010);
- guest: U047–U060 (наприклад, U050).

Теми для холодного старту — `GET /topics`.

## Відтворення результатів

```bash
python reco/eval.py --emb lsa           # або --emb e5 (на ПК); 5 seed → results/reco_eval_*.json
python reco/cold_start.py --emb lsa     # → results/cold_start_*.json
python reco/explain.py [--llm]          # → results/explanations.json (з --llm потрібна Ollama)
python reco/filters_demo.py             # → results/filters_demo.json
python reco/make_docs.py                # рисунки docs/img і таблиці docs/reco_eval.md
python demo/run_demo.py                 # 5 кроків демонстрації проти запущеного API
```

Seed: генератор 16–20, LSA `random_state = 16`, бутстреп `seed = 0`; LLM `temperature = 0`, `seed = 42`.
