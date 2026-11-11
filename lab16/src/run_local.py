"""ЛР16 · запуск демонстратора БЕЗ Docker (резервний режим): ті самі три сервіси як локальні процеси.
  python lab16/src/run_local.py        (потрібні пакети з docker/requirements.txt у поточному Python)
Ctrl+C зупиняє все. Журнали — lab16/logs/local_*.log.
"""
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
HUB = LAB.parent
LOGS = LAB / "logs"
LOGS.mkdir(exist_ok=True)
env = {**os.environ, "GRAPH_URL": "http://127.0.0.1:7878", "API_URL": "http://127.0.0.1:8000", "LOG_DIR": str(LOGS),
       "HUB_DENSE": os.environ.get("HUB_DENSE", "0"), "PYTHONIOENCODING": "utf-8"}
procs = []


def start(name, cmd):
    f = open(LOGS / f"local_{name}.log", "w", encoding="utf-8")
    procs.append(subprocess.Popen(cmd, cwd=HUB, env=env, stdout=f, stderr=subprocess.STDOUT))
    print("старт", name, "→", LOGS / f"local_{name}.log")


def wait(url, limit=180):
    t0 = time.time()
    while time.time() - t0 < limit:
        try:
            urllib.request.urlopen(url, timeout=3)
            return True
        except Exception:  # noqa
            time.sleep(1)
    return False


try:
    start("graph", [sys.executable, "lab16/api/graph_service.py"])
    print("graph:", wait("http://127.0.0.1:7878/health"))
    start("api", [sys.executable, "lab16/api/app.py"])
    print("api:", wait("http://127.0.0.1:8000/health"))
    start("ui", [sys.executable, "-m", "streamlit", "run", "lab16/ui/app.py", "--server.port=8501", "--server.headless=true",
                 "--browser.gatherUsageStats=false"])
    print("ui:", wait("http://127.0.0.1:8501/_stcore/health"))
    print("Готово: UI http://127.0.0.1:8501 · API http://127.0.0.1:8000/docs · Ctrl+C — зупинити")
    while all(p.poll() is None for p in procs):
        time.sleep(2)
finally:
    for p in procs:
        p.terminate()
