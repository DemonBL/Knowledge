"""ЛР11 · Результат 3: демонстрація API — справжній HTTP-сервер uvicorn + запити httpx.
Ключі читаються з api/keys.local.json і НЕ потрапляють у результати (замінюються на <guest-key> тощо).
Вихід: results/api_demo.json, docs/openapi.json
"""
import json
import subprocess
import sys
import time
from pathlib import Path

import httpx

LAB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB / "api"))
PORT = 8011
BASE = f"http://127.0.0.1:{PORT}"


def main():
    import main as m  # створює keys.local.json, якщо його ще немає
    keys = {role: k for k, role in json.loads(m.KEYS_FILE.read_text(encoding="utf-8")).items()}
    srv = subprocess.Popen([sys.executable, "-m", "uvicorn", "main:app", "--port", str(PORT), "--app-dir", str(LAB / "api")],
                           stdout=open(LAB / "logs" / "uvicorn.log", "w"), stderr=subprocess.STDOUT)
    try:
        for _ in range(120):
            try:
                httpx.get(BASE + "/health", timeout=1)
                break
            except Exception:  # noqa
                time.sleep(1)
        log = []

        def call(name, method, path, role=None, key=None, body=None):
            h = {}
            if role:
                h["X-API-Key"] = keys[role]
            if key is not None:
                h["X-API-Key"] = key
            t0 = time.perf_counter()
            r = httpx.request(method, BASE + path, headers=h, json=body, timeout=900)
            dt = round(time.perf_counter() - t0, 2)
            try:
                data = r.json()
            except Exception:  # noqa
                data = r.text
            shown_key = f"<{role}-key>" if role else ("<invalid-key>" if key else None)
            log.append({"name": name, "request": {"method": method, "path": path, "X-API-Key": shown_key, "json": body},
                        "status": r.status_code, "seconds": dt, "response": data,
                        "retry_after": r.headers.get("retry-after")})
            print(name, r.status_code, dt, str(data)[:160])
            return r

        call("health", "GET", "/health")
        call("без ключа → 401", "POST", "/ask", body={"question": "Що таке фактчекінг?"})
        call("невірний ключ → 401", "POST", "/ask", key="not-a-real-key", body={"question": "Що таке фактчекінг?"})
        call("валідація: закоротке питання → 422", "POST", "/ask", role="analyst", body={"question": "?"})
        call("валідація: k=50 → 422", "POST", "/ask", role="analyst", body={"question": "Що таке дипфейк?", "k": 50})
        q = {"question": "Скільки публікацій наративу «Отруєна питна вода» виявлено загалом і хто першоджерела?"}
        call("guest: restricted-документи недоступні", "POST", "/ask", role="guest", body=q)
        call("admin: той самий запит бачить звіт restricted", "POST", "/ask", role="admin", body=q)
        call("analyst: питання з цитатами", "POST", "/ask", role="analyst",
             body={"question": "Коли з'явився сайт StopFake і хто автор ідеї?", "use_graph": False})
        call("sources: guest → restricted 403", "GET", "/sources/INT-NAR-03:s000", role="guest")
        call("sources: admin → restricted 200", "GET", "/sources/INT-NAR-03:s000", role="admin")
        call("sources: guest → вузол графа 403", "GET", "/sources/G:ACC-005", role="guest")
        call("sources: analyst → вузол графа 200", "GET", "/sources/G:ACC-005", role="analyst")
        call("sources: неіснуючий id → 404", "GET", "/sources/W99:s000", role="admin")
        # ліміт 10/60 с: /ask для guest триває >60 с, тому вікно могло звільнитися — робимо до 12 швидких запитів
        for i in range(12):
            r = call(f"ліміт: запит {i+1}", "GET", "/sources/W01:s000", role="guest")
            if r.status_code == 429:
                break
        openapi = httpx.get(BASE + "/openapi.json").json()
        (LAB / "docs").mkdir(exist_ok=True)
        (LAB / "docs" / "openapi.json").write_text(json.dumps(openapi, ensure_ascii=False, indent=1), encoding="utf-8")
        (LAB / "results").mkdir(exist_ok=True)
        (LAB / "results" / "api_demo.json").write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
    finally:
        srv.terminate()


if __name__ == "__main__":
    main()
