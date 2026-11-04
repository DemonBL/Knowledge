"""ЛР11 · Результат 1: RAG-конвеєр із цитуванням.

запит → гібридний пошук ЛР10 (пре-фільтр за правами ролі) → reranking → [+ підграф Neo4j] →
промпт (prompts/rag_v1.md) → LLM (Ollama, qwen2.5:7b) → відповідь → перевірка цитат → журнал.
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
HUB = LAB.parent
sys.path.insert(0, str(HUB / "common"))
sys.path.insert(0, str(HUB / "lab10" / "src"))
sys.path.insert(0, str(LAB / "src"))
from hub_common import LLM, now_iso  # noqa: E402
import search_core as S  # noqa: E402

GEN_MODEL = "qwen2.5:7b"
CITE_RE = re.compile(r"\[([A-Za-zА-Яа-я0-9\-]+:[A-Za-z0-9\-]+)\]")
IDK = "Не знаю"


class RAG:
    def __init__(self, k: int = 5, use_graph: bool = False, model: str = GEN_MODEL,
                 prompt_file: str = "rag_v1.md", searcher=None, graph=None, log_name="rag_log.jsonl"):
        self.k, self.use_graph = k, use_graph
        self.prompt_version = prompt_file.replace(".md", "")
        self.system = (LAB / "prompts" / prompt_file).read_text(encoding="utf-8")
        self.chunks = S.load_jsonl(HUB / "lab10" / "data" / "corpus.jsonl")
        self.by_id = {c["chunk_id"]: c for c in self.chunks}
        if searcher is None:
            enc = S.Encoder("e5")
            searcher = S.HybridSearcher(self.chunks, enc, S.Reranker())
        self.searcher = searcher
        self.graph = graph
        self.llm = LLM(model, LAB / "llm_log" / "generator.jsonl", temperature=0.1, seed=42,
                       prompt_version=self.prompt_version)
        self.log_path = LAB / "logs" / log_name
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def retrieve(self, question, role):
        flt = S.make_filter(role)
        t0 = time.perf_counter()
        hits = self.searcher.search(question, "hybrid_rerank", k=self.k, flt=flt)
        t_ret = time.perf_counter() - t0
        graph_lines, entities = [], []
        # граф розслідувань містить ідентифікатори акаунтів → лише для ролей analyst/admin
        if self.use_graph and self.graph is not None and role != "guest":
            entities = self.graph.link(question)
            graph_lines = self.graph.subgraph(entities)
        return hits, graph_lines, entities, t_ret

    @staticmethod
    def format_context(hits, graph_lines):
        parts = []
        for c, s in hits:
            parts.append(f"[{c['chunk_id']}] ({c['title']} · {c['section']} · дата {c['date']} · {c['sensitivity']})\n{c['text']}")
        if graph_lines:
            parts.append("ГРАФ ЗНАНЬ (факти з бази Neo4j; посилайся на [G:ID]):\n" + "\n".join(graph_lines))
        return "\n\n".join(parts)

    def answer(self, question: str, role: str = "analyst", meta: dict | None = None) -> dict:
        t0 = time.perf_counter()
        hits, glines, ents, t_ret = self.retrieve(question, role)
        ctx = self.format_context(hits, glines)
        allowed_ids = {c["chunk_id"] for c, _ in hits} | set(re.findall(r"\[(G:[A-Z]+-\d+)\]", "\n".join(glines)))
        msgs = [{"role": "system", "content": self.system},
                {"role": "user", "content": f"КОНТЕКСТ\n{ctx}\n\nПИТАННЯ: {question}"}]
        r = self.llm.chat(msgs, task="rag_answer", max_tokens=450, extra={"meta": meta or {}})
        text = r["text"].strip()
        cited = CITE_RE.findall(text)
        valid = [c for c in cited if c in allowed_ids]
        invalid = [c for c in cited if c not in allowed_ids]
        rec = {"ts": now_iso(), "question": question, "role": role, "k": self.k, "use_graph": self.use_graph,
               "prompt_version": self.prompt_version, "model": self.llm.model,
               "sources": [{"id": c["chunk_id"], "title": c["title"], "sensitivity": c["sensitivity"],
                            "score": round(s, 3)} for c, s in hits],
               "graph_entities": ents, "graph_lines": glines, "answer": text,
               "citations": cited, "citations_valid": valid, "citations_invalid": invalid,
               "abstained": text.startswith(IDK),
               "prompt_tokens": r["prompt_tokens"], "completion_tokens": r["completion_tokens"],
               "latency_s": round(time.perf_counter() - t0, 2), "llm_s": r["latency_s"],
               "retrieval_s": round(t_ret, 3), "context_chars": len(ctx), "meta": meta or {}}
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return rec


if __name__ == "__main__":  # демо ≥ 5 запитів
    rag = RAG()
    demo = ["Коли з'явився сайт StopFake і хто автор ідеї?",
            "Скільки доказів потрібно для вердикту «фейк»?",
            "Що таке інформаційна гігієна?",
            "Яка зарплата фактчекера у VoxCheck?",
            "Хто першоджерело твердження про збір на дрони для Одеси?"]
    for q in demo:
        r = rag.answer(q, "analyst")
        print("\nQ:", q, "\nA:", r["answer"], "\n  valid:", r["citations_valid"], "invalid:", r["citations_invalid"],
              f"| {r['prompt_tokens']}+{r['completion_tokens']} tok, {r['latency_s']} s")
