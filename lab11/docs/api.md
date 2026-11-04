# REST API (ЛР11, Результат 3)

Сервіс FastAPI, запуск: `python -m uvicorn main:app --app-dir api --port 8000` (з папки lab11).
Повна специфікація OpenAPI 3: `docs/openapi.json` (також інтерактивно: http://127.0.0.1:8000/docs).

## Ендпоінти

| Метод | Шлях | Опис | Автентифікація |
|---|---|---|---|
| GET | /health | стан сервісу, Neo4j, Ollama | ні |
| POST | /ask | питання → відповідь, джерела, валідні/невалідні цитати, токени, затримка | X-API-Key |
| GET | /sources/{id} | повний текст фрагмента або вузла графа з перевіркою прав | X-API-Key |

Тіло /ask (Pydantic): `question` 3–500 символів, `use_graph` (bool, типово true), `k` 1–10 (типово 5).

## Ролі та права

| Роль | Доступні рівні sensitivity | Граф розслідувань |
|---|---|---|
| guest | public | ні |
| analyst | public, internal | так |
| admin | public, internal, restricted | так |

Ключі генеруються при першому запуску у `api/keys.local.json` (у .gitignore); у пам'яті сервера — лише SHA-256 хеші.

## Ліміт і коди помилок

10 запитів / 60 с на ключ (ковзне вікно) → 429 з заголовком Retry-After. 401 — немає/невірний ключ; 403 — недостатньо прав; 404 — джерело не знайдено; 422 — помилка валідації.

## Приклади curl

```bash
curl http://127.0.0.1:8000/health
curl -X POST http://127.0.0.1:8000/ask -H "X-API-Key: $KEY" -H "Content-Type: application/json" \
     -d '{"question": "Коли з'\''явився сайт StopFake?", "k": 5}'
curl http://127.0.0.1:8000/sources/W14:s001 -H "X-API-Key: $KEY"
```

## Результати демо (results/api_demo.json)

| Сценарій | Запит | Ключ | Код | Час, с |
|---|---|---|---|---|
| health | GET /health | — | 200 | 0.17 |
| без ключа → 401 | POST /ask | — | 401 | 0.16 |
| невірний ключ → 401 | POST /ask | <invalid-key> | 401 | 0.16 |
| валідація: закоротке питання → 422 | POST /ask | <analyst-key> | 422 | 0.17 |
| валідація: k=50 → 422 | POST /ask | <analyst-key> | 422 | 0.16 |
| guest: restricted-документи недоступні | POST /ask | <guest-key> | 200 | 86.14 |
| admin: той самий запит бачить звіт restricted | POST /ask | <admin-key> | 200 | 27.46 |
| analyst: питання з цитатами | POST /ask | <analyst-key> | 200 | 10.68 |
| sources: guest → restricted 403 | GET /sources/INT-NAR-03:s000 | <guest-key> | 403 | 0.17 |
| sources: admin → restricted 200 | GET /sources/INT-NAR-03:s000 | <admin-key> | 200 | 0.15 |
| sources: guest → вузол графа 403 | GET /sources/G:ACC-005 | <guest-key> | 403 | 0.15 |
| sources: analyst → вузол графа 200 | GET /sources/G:ACC-005 | <analyst-key> | 200 | 0.15 |
| sources: неіснуючий id → 404 | GET /sources/W99:s000 | <admin-key> | 404 | 0.15 |
| ліміт: запит 1 | GET /sources/W01:s000 | <guest-key> | 200 | 0.15 |
| ліміт: запит 2 | GET /sources/W01:s000 | <guest-key> | 200 | 0.16 |
| ліміт: запит 3 | GET /sources/W01:s000 | <guest-key> | 200 | 0.16 |
| ліміт: запит 4 | GET /sources/W01:s000 | <guest-key> | 200 | 0.15 |
| ліміт: запит 5 | GET /sources/W01:s000 | <guest-key> | 200 | 0.15 |
| ліміт: запит 6 | GET /sources/W01:s000 | <guest-key> | 200 | 0.15 |
| ліміт: запит 7 | GET /sources/W01:s000 | <guest-key> | 200 | 0.16 |
| ліміт: запит 8 | GET /sources/W01:s000 | <guest-key> | 200 | 0.15 |

## Перевірка ліміту (api/test_rate_limit.py, FastAPI TestClient, RAG-заглушка)

У живому демо /ask для guest тривав 86 с, тож 60-секундне вікно звільнилося й 429 не з'явився; ліміт перевірено окремим тестом того самого main.py.

| № запиту (guest) | Код | Retry-After |
|---|---|---|
| 1 | 200 | — |
| 2 | 200 | — |
| 3 | 200 | — |
| 4 | 200 | — |
| 5 | 200 | — |
| 6 | 200 | — |
| 7 | 200 | — |
| 8 | 200 | — |
| 9 | 200 | — |
| 10 | 200 | — |
| 11 | 429 | 60 |
| 12 | 429 | 60 |
| інший ключ (analyst) | 200 | — |
