"""Спільні утиліти Domain Knowledge Hub (ЛР9–ЛР11).

Важкі інструменти лежать у F:\\kms_tools (див. setup.ps1):
  neo4j\\        — Neo4j Community 5.26 + GDS (запуск на Java 17)
  ollama\\       — Ollama (локальні LLM), моделі в ollama-models\\
  hf\\           — кеш моделей HuggingFace
Пароль Neo4j генерується під час встановлення і НЕ зберігається в коді:
F:\\kms_tools\\neo4j_password.txt (або змінна середовища NEO4J_PASSWORD).
"""
from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

TOOLS = Path(os.environ.get("KMS_TOOLS", r"F:\kms_tools"))
HUB = Path(__file__).resolve().parents[1]
NEO4J_HOME = TOOLS / "neo4j"
NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")

os.environ.setdefault("HF_HOME", str(TOOLS / "hf"))
os.environ.setdefault("OLLAMA_MODELS", str(TOOLS / "ollama-models"))


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def port_open(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket() as s:
        s.settimeout(1)
        return s.connect_ex((host, port)) == 0


# ------------------------------------------------------------------ Neo4j
def neo4j_password() -> str:
    pw = os.environ.get("NEO4J_PASSWORD")
    if pw:
        return pw
    return (TOOLS / "neo4j_password.txt").read_text(encoding="ascii").strip()


def java_home() -> str:
    if os.environ.get("JAVA_HOME"):
        return os.environ["JAVA_HOME"]
    java = shutil.which("java")
    return str(Path(java).resolve().parents[1])


def ensure_neo4j(timeout: int = 180) -> None:
    """Запускає Neo4j у фоновому вікні, якщо він ще не працює."""
    if port_open(7687):
        return
    env = dict(os.environ, JAVA_HOME=java_home(), NEO4J_HOME=str(NEO4J_HOME))
    log = open(HUB / "logs" / "neo4j_console.log", "a", encoding="utf-8")
    subprocess.Popen([str(NEO4J_HOME / "bin" / "neo4j.bat"), "console"], env=env,
                     stdout=log, stderr=subprocess.STDOUT,
                     creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0))
    t0 = time.time()
    while time.time() - t0 < timeout:
        if port_open(7687):
            time.sleep(5)
            return
        time.sleep(2)
    raise RuntimeError("Neo4j не стартував за %d с — див. logs/neo4j_console.log" % timeout)


def neo4j_driver():
    from neo4j import GraphDatabase
    ensure_neo4j()
    drv = GraphDatabase.driver(NEO4J_URI, auth=("neo4j", neo4j_password()))
    drv.verify_connectivity()
    return drv


def neo4j_import_dir() -> Path:
    d = NEO4J_HOME / "import"
    d.mkdir(exist_ok=True)
    return d


# ------------------------------------------------------------------ Ollama
def ensure_ollama(timeout: int = 60) -> None:
    if port_open(11434):
        return
    exe = TOOLS / "ollama" / "ollama.exe"
    subprocess.Popen([str(exe), "serve"], env=dict(os.environ),
                     creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0))
    t0 = time.time()
    while time.time() - t0 < timeout:
        if port_open(11434):
            return
        time.sleep(1)
    raise RuntimeError("Ollama не стартувала")


def ollama_models() -> list[str]:
    ensure_ollama()
    with urllib.request.urlopen(OLLAMA_URL + "/api/tags") as r:
        return [m["name"] for m in json.load(r)["models"]]


class LLM:
    """Виклик локальної моделі Ollama з обов'язковим журналом (протокол «LLM-експерт»)."""

    def __init__(self, model: str, log_path: Path, temperature: float = 0.0, seed: int = 42,
                 num_ctx: int = 8192, prompt_version: str = "v1"):
        self.model, self.temperature, self.seed, self.num_ctx = model, temperature, seed, num_ctx
        self.prompt_version = prompt_version
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        ensure_ollama()
        self._version = None

    def version(self) -> str:
        if self._version is None:
            try:
                req = urllib.request.Request(OLLAMA_URL + "/api/show",
                                             data=json.dumps({"model": self.model}).encode(),
                                             headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req) as r:
                    info = json.load(r)
                d = info.get("details", {})
                self._version = f"{d.get('family','?')} {d.get('parameter_size','?')} {d.get('quantization_level','?')}"
            except Exception as e:  # noqa
                self._version = "unknown"
        return self._version

    def chat(self, messages: list[dict], task: str = "", fmt: str | None = None,
             max_tokens: int = 700, extra: dict | None = None) -> dict:
        body = {"model": self.model, "messages": messages, "stream": False,
                "options": {"temperature": self.temperature, "seed": self.seed,
                            "num_ctx": self.num_ctx, "num_predict": max_tokens}}
        if fmt:
            body["format"] = fmt
        t0 = time.perf_counter()
        req = urllib.request.Request(OLLAMA_URL + "/api/chat", data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=900) as r:
            out = json.load(r)
        dt = time.perf_counter() - t0
        res = {"text": out["message"]["content"],
               "prompt_tokens": out.get("prompt_eval_count", 0),
               "completion_tokens": out.get("eval_count", 0),
               "latency_s": round(dt, 3)}
        rec = {"ts": now_iso(), "task": task, "model": self.model, "model_version": self.version(),
               "params": {"temperature": self.temperature, "seed": self.seed, "num_ctx": self.num_ctx,
                          "num_predict": max_tokens, "format": fmt},
               "prompt_version": self.prompt_version, "messages": messages,
               "raw_output": res["text"], "prompt_tokens": res["prompt_tokens"],
               "completion_tokens": res["completion_tokens"], "latency_s": res["latency_s"],
               "human_decision": None}
        if extra:
            rec.update(extra)
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return res


def write_json(path: Path, obj) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


def md_table(cols, rows) -> str:
    out = ["| " + " | ".join(map(str, cols)) + " |", "|" + "---|" * len(cols)]
    for r in rows:
        out.append("| " + " | ".join(str(x).replace("|", "\\|").replace("\n", " ") for x in r) + " |")
    return "\n".join(out)
