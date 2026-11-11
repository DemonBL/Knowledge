"""ЛР15 · клієнт LLM для агента: Ollama /api/chat з нативними викликами інструментів (tools) + журнал llm_log/.
FakeLLM — детерміноване «заглушкове» ядро для перевірки графа агента без моделі (лише для розробки в хмарі; не для метрик)."""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")


def now_iso():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


class OllamaLLM:
    def __init__(self, model="qwen2.5:7b", log_name="agent_llm.jsonl", temperature=0.0, seed=42, num_ctx=8192, prompt_version="agent_v1"):
        self.model, self.temperature, self.seed, self.num_ctx, self.prompt_version = model, temperature, seed, num_ctx, prompt_version
        self.log_path = LAB / "llm_log" / log_name
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            sys_path = Path(__file__).resolve().parents[2] / "common"
            import sys
            sys.path.insert(0, str(sys_path))
            from hub_common import ensure_ollama
            ensure_ollama()
        except Exception as e:  # noqa
            print("ensure_ollama:", e)
        self._version = None

    def version(self):
        if self._version is None:
            try:
                req = urllib.request.Request(OLLAMA_URL + "/api/show", data=json.dumps({"model": self.model}).encode(),
                                             headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=30) as r:
                    d = json.load(r).get("details", {})
                self._version = f"{d.get('family', '?')} {d.get('parameter_size', '?')} {d.get('quantization_level', '?')}"
            except Exception:  # noqa
                self._version = "unknown"
        return self._version

    def chat(self, messages, tools=None, fmt=None, max_tokens=400, task="", meta=None):
        body = {"model": self.model, "messages": messages, "stream": False,
                "options": {"temperature": self.temperature, "seed": self.seed, "num_ctx": self.num_ctx, "num_predict": max_tokens}}
        if tools:
            body["tools"] = tools
        if fmt:
            body["format"] = fmt
        t0 = time.perf_counter()
        req = urllib.request.Request(OLLAMA_URL + "/api/chat", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=600) as r:
                out = json.load(r)
        except urllib.error.HTTPError as e:              # напр. модель згенерувала некоректний виклик інструмента
            out = {"message": {"content": "", "tool_calls": []}, "error": f"HTTP {e.code}: {e.read()[:200]!r}"}
        msg = out.get("message", {})
        res = {"text": msg.get("content", ""), "tool_calls": [
            {"name": tc["function"]["name"], "arguments": tc["function"].get("arguments") or {}} for tc in (msg.get("tool_calls") or [])],
            "prompt_tokens": out.get("prompt_eval_count", 0), "completion_tokens": out.get("eval_count", 0),
            "latency_s": round(time.perf_counter() - t0, 3)}
        for tc in res["tool_calls"]:
            if isinstance(tc["arguments"], str):
                try:
                    tc["arguments"] = json.loads(tc["arguments"])
                except Exception:  # noqa
                    tc["arguments"] = {}
        rec = {"ts": now_iso(), "task": task, "model": self.model, "model_version": self.version(),
               "params": {"temperature": self.temperature, "seed": self.seed, "num_ctx": self.num_ctx, "num_predict": max_tokens},
               "prompt_version": self.prompt_version, "messages": messages, "tools": [t["function"]["name"] for t in tools or []],
               "raw_output": res["text"], "tool_calls": res["tool_calls"], "prompt_tokens": res["prompt_tokens"],
               "completion_tokens": res["completion_tokens"], "latency_s": res["latency_s"], "human_decision": None}
        if out.get("error"):
            rec["error"] = out["error"]
        if meta:
            rec.update(meta)
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return res


class FakeLLM:
    """Ключові слова → виклики інструментів; чернетка = перший доказ із цитатою. Лише для тестів конвеєра."""
    model = "fake"
    prompt_version = "fake"

    def version(self):
        return "fake"

    def chat(self, messages, tools=None, fmt=None, max_tokens=400, task="", meta=None):
        user = next(m["content"] for m in messages if m["role"] == "user")
        q = user.split("ПИТАННЯ:")[-1].split("\n")[0] if "ПИТАННЯ:" in user else user
        res = {"text": "", "tool_calls": [], "prompt_tokens": sum(len(m["content"]) // 4 for m in messages), "completion_tokens": 20, "latency_s": 0.0}
        if task == "plan":
            if any(m["role"] == "tool" for m in messages):
                return res
            names = {t["function"]["name"] for t in tools or []}
            m = re.search(r"\b(CLM|NAR|ACC|RULE)-\d+", q)
            if "export_report" in names and "архів" in q.lower():
                res["tool_calls"].append({"name": "export_report", "arguments": {"content": q}})
            if m:
                kind = {"CLM": "claim", "NAR": "narrative", "ACC": "account", "RULE": "rule"}[m.group(1)]
                res["tool_calls"].append({"name": "kb_graph", "arguments": {"query_type": kind, "entity": m.group(0)}})
            elif re.search(r"частк|скільки перевір|середн", q.lower()):
                res["tool_calls"].append({"name": "olap_metrics", "arguments": {"metrics": ["false_verdict_rate"], "dimensions": ["platform"]}})
            else:
                res["tool_calls"].append({"name": "search_docs", "arguments": {"query": q, "k": 3}})
            return res
        ev = re.findall(r"\[([A-Z]+[:\w\-]+)\] ([^\n]{0,160})", user)
        res["text"] = f"{ev[0][1]} [{ev[0][0]}]" if ev else "Не знаю: у наданих джерелах немає відповіді."
        return res
