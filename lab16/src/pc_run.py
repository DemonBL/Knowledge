"""ЛР16 · частина, що потребує ПК (модель e5, Ollama, Docker). ≈ 15–20 хв, більшість — збірка образу Docker.

Етапи (python lab16/src/pc_run.py [e5|eval|explain|docker|all]):
  e5      — вектори e5 для 529 фрагментів                                   → data/item_vecs_e5.npy (+ .ids)
  eval    — офлайн-оцінка (5 seed) і холодний старт з e5-ембедингами          → results/reco_eval_e5.json, cold_start_e5.json
  explain — qwen2.5:7b перефразовує пояснення шляхів; автоперевірка сутностей → results/explanations.json, llm_log/explain_llm.jsonl
  docker  — запуск «з нуля»: compose down -v --rmi all → build --no-cache --pull → up -d → очікування health
            → прогін demo/run_demo.py (5 запитів, включно з «не знаю» та атакою) → logs/*.log, demo/demo_run.md
Секретів не потрібно; дані користувачів синтетичні; зовнішніх API немає (LLM локальна).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import traceback
import urllib.request
from datetime import datetime
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
HUB = LAB.parent
PY = sys.executable
LOGS = LAB / "logs"
LOGS.mkdir(exist_ok=True)
RESULTS = LAB / "results"
RESULTS.mkdir(exist_ok=True)


def say(*a):
    print(datetime.now().strftime("%H:%M:%S"), *a, flush=True)


def sh(cmd, log=None, cwd=LAB, timeout=3600, env=None):
    say("$", " ".join(cmd))
    t0 = time.time()
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
                       env={**os.environ, **(env or {})})
    out = (p.stdout or "") + (p.stderr or "")
    if log:
        with open(LOGS / log, "a", encoding="utf-8") as f:
            f.write(f"\n### {datetime.now().isoformat(timespec='seconds')} $ {' '.join(cmd)}\n{out}\n### exit {p.returncode}, {time.time() - t0:.1f} s\n")
    print(out[-3000:], flush=True)
    return p.returncode, out, round(time.time() - t0, 1)


def e5():
    out = LAB / "data" / "item_vecs_e5.npy"
    if out.exists():
        say("e5: вже є", out)
        return
    # lab14/quality НЕ додаємо в sys.path (там profile.py затінює стандартний модуль → ламає transformers)
    sys.path.insert(0, str(HUB / "lab10" / "src"))
    sys.path.insert(0, str(LAB / "reco"))
    import numpy as np
    import items as IT
    import search_core as S
    its = IT.load_items()
    t0 = time.time()
    enc = S.Encoder("e5")
    v = np.asarray(enc.passages([it["embed_text"] for it in its]), dtype="float32")
    v /= np.linalg.norm(v, axis=1, keepdims=True) + 1e-9
    np.save(out, v)
    (LAB / "data" / "item_vecs_e5.ids").write_text("\n".join(it["id"] for it in its), encoding="utf-8", newline="\n")
    say(f"e5: {v.shape} за {time.time() - t0:.1f} с")


def evaluate():
    sh([PY, "-u", "reco/eval.py", "--emb", "e5"], log="eval_e5.log", timeout=3600)
    sh([PY, "-u", "reco/cold_start.py", "--emb", "e5"], log="eval_e5.log", timeout=3600)


def explain():
    sys.path.insert(0, str(HUB / "common"))
    from hub_common import ensure_ollama
    ensure_ollama()
    sh([PY, "-u", "reco/explain.py", "--llm", "--emb", "e5"], log="explain.log", timeout=3600)


def wait_health(url, limit=900):
    t0 = time.time()
    while time.time() - t0 < limit:
        try:
            with urllib.request.urlopen(url, timeout=5) as r:
                return json.load(r), round(time.time() - t0, 1)
        except Exception:  # noqa
            time.sleep(3)
    return None, round(time.time() - t0, 1)


def docker():
    rec = {"started": datetime.now().isoformat(timespec="seconds")}
    if not shutil.which("docker"):
        rec["error"] = "docker не знайдено в PATH"
        (RESULTS / "docker_run.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
        say("Docker не знайдено — пропускаю етап. Локальний режим: python lab16/src/run_local.py")
        return
    c, out, _ = sh(["docker", "version", "--format", "{{.Server.Version}}"], log="compose.log")
    if c != 0:
        rec["error"] = "Docker Engine не запущений (відкрийте Docker Desktop і повторіть)"
        (RESULTS / "docker_run.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
        say(rec["error"])
        return
    rec["docker_server"] = out.strip().splitlines()[-1]
    sys.path.insert(0, str(HUB / "common"))
    try:
        from hub_common import ensure_ollama
        ensure_ollama()
    except Exception as e:  # noqa
        say("Ollama:", e)
    P = ["docker", "compose", "-p", "hub16"]
    rec["down"] = sh(P + ["down", "-v", "--rmi", "all", "--remove-orphans"], log="compose.log")[2]
    c, out, rec["build_s"] = sh(P + ["build", "--no-cache", "--pull"], log="compose.log", timeout=3600)
    rec["build_exit"] = c
    c, out, rec["up_s"] = sh(P + ["up", "-d"], log="compose.log", timeout=900)
    rec["up_exit"] = c
    h, rec["health_wait_s"] = wait_health("http://127.0.0.1:8000/health")
    rec["health"] = h
    ui, _ = wait_health("http://127.0.0.1:8501/_stcore/health", limit=180) if h else (None, 0)
    rec["ui_ok"] = ui is not None or _probe("http://127.0.0.1:8501/_stcore/health")
    rec["ps"] = sh(P + ["ps", "--format", "table {{.Service}}\t{{.Status}}\t{{.Ports}}"], log="compose.log")[1]
    rec["image"] = sh(["docker", "image", "ls", "hub16", "--format", "{{.Repository}}:{{.Tag}} {{.Size}}"], log="compose.log")[1].strip()
    if h:
        c, out, rec["demo_s"] = sh([PY, "-u", "demo/run_demo.py"], log="demo.log", timeout=3600)
        rec["demo_tail"] = out[-400:]
    sh(P + ["logs", "--no-color", "--timestamps"], log="compose_services.log")
    rec["finished"] = datetime.now().isoformat(timespec="seconds")
    (RESULTS / "docker_run.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    say("Демонстратор працює: UI http://127.0.0.1:8501 , API http://127.0.0.1:8000/docs . Зупинка: docker compose -p hub16 down")


def _probe(url):
    try:
        urllib.request.urlopen(url, timeout=5)
        return True
    except Exception:  # noqa
        return False


STAGES = {"e5": e5, "eval": evaluate, "explain": explain, "docker": docker}

if __name__ == "__main__":
    which = sys.argv[1:] or ["all"]
    order = list(STAGES) if "all" in which else which
    for s in order:
        say("=====", s)
        try:
            STAGES[s]()
        except Exception:  # noqa
            traceback.print_exc()
    say("ГОТОВО")
