"""ЛР11 · перевірка ліміту запитів (10 / 60 с) справжнього api/main.py через FastAPI TestClient.
RAG підмінено заглушкою (лише by_id), бо перевіряється шар auth + rate limit, а не генерація.
Запуск (з lab11): python api\\test_rate_limit.py  → results/api_ratelimit_test.json"""
import json, sys, types
from pathlib import Path
HERE = Path(__file__).resolve().parents[1]  # lab11
sys.path.insert(0, str(HERE / "api"))
import main as m
from fastapi.testclient import TestClient
m.STATE["rag"] = types.SimpleNamespace(by_id={"W01:s000": {"chunk_id": "W01:s000", "doc_id": "W01", "title": "Дезінформація",
    "section": "Вступ", "type": "encyclopedia", "date": "2026-05-10", "sensitivity": "public", "source_url": "-", "text": "…"}}, graph=None)
keys = {role: k for k, role in json.loads(m.KEYS_FILE.read_text(encoding="utf-8")).items()}
c = TestClient(m.app)
log = []
for i in range(1, 13):
    r = c.get("/sources/W01:s000", headers={"X-API-Key": keys["guest"]})
    log.append({"n": i, "status": r.status_code, "retry_after": r.headers.get("retry-after"),
                "error": r.json().get("error") if r.status_code != 200 else None})
    print(i, r.status_code, r.headers.get("retry-after") or "", log[-1]["error"] or "")
r = c.get("/sources/W01:s000", headers={"X-API-Key": keys["analyst"]})
log.append({"n": "інший ключ (analyst)", "status": r.status_code, "retry_after": None, "error": None})
print("analyst", r.status_code)
(HERE / "results").mkdir(exist_ok=True)
(HERE / "results" / "api_ratelimit_test.json").write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
