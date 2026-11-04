"""ЛР10 · ядро пошуку: embeddings + FAISS HNSW, BM25, RRF, reranker, пре-фільтр, upsert/delete.
Використовується також у ЛР11 (RAG)."""
from __future__ import annotations

import json
import math
import re
import time
from pathlib import Path

import numpy as np

MODELS = {"e5": "intfloat/multilingual-e5-small",
          "minilm": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"}
RERANKER = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
HNSW = {"M": 32, "efConstruction": 200, "efSearch": 64}
ROLE_ACCESS = {"guest": {"public"}, "analyst": {"public", "internal"},
               "admin": {"public", "internal", "restricted"}}


def load_jsonl(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


# ------------------------------------------------------------------ embeddings
class Encoder:
    def __init__(self, key: str, device: str | None = None):
        from sentence_transformers import SentenceTransformer
        self.key, self.name = key, MODELS[key]
        self.m = SentenceTransformer(self.name, device=device)
        self.dim = self.m.get_sentence_embedding_dimension()

    def passages(self, texts, bs=32):
        t = [("passage: " + x) if self.key == "e5" else x for x in texts]
        return self.m.encode(t, batch_size=bs, normalize_embeddings=True, show_progress_bar=False).astype("float32")

    def queries(self, texts):
        t = [("query: " + x) if self.key == "e5" else x for x in texts]
        return self.m.encode(t, normalize_embeddings=True, show_progress_bar=False).astype("float32")


# ------------------------------------------------------------------ векторне сховище з upsert/delete
class VectorStore:
    """FAISS HNSW (inner product на нормалізованих векторах = косинус).
    HNSW у FAISS не підтримує видалення, тому: оновлення = додавання нових векторів із новими id +
    «надгробки» для старих; пошук виключає надгробки через IDSelector; перебудова, коли
    частка надгробків > 20 %."""

    def __init__(self, enc: Encoder, chunks: list[dict]):
        import faiss
        self.faiss, self.enc = faiss, enc
        self.meta: dict[int, dict] = {}
        self.dead: set[int] = set()
        self.next_id = 0
        self.index = None
        self.compactions = 0
        t0 = time.perf_counter()
        self._rebuild(chunks)
        self.build_s = round(time.perf_counter() - t0, 2)

    def _new_index(self):
        base = self.faiss.IndexHNSWFlat(self.enc.dim, HNSW["M"], self.faiss.METRIC_INNER_PRODUCT)
        base.hnsw.efConstruction = HNSW["efConstruction"]
        base.hnsw.efSearch = HNSW["efSearch"]
        return self.faiss.IndexIDMap2(base)

    def _rebuild(self, chunks):
        self.index, self.meta, self.dead, self.next_id = self._new_index(), {}, set(), 0
        self.add(chunks)

    def add(self, chunks):
        if not chunks:
            return
        vec = self.enc.passages([c["embed_text"] for c in chunks])
        ids = np.arange(self.next_id, self.next_id + len(chunks)).astype("int64")
        self.index.add_with_ids(vec, ids)
        for i, c in zip(ids, chunks):
            self.meta[int(i)] = c
        self.next_id += len(chunks)

    def live(self):
        return [i for i in self.meta if i not in self.dead]

    def delete_doc(self, doc_id):
        n = 0
        for i, c in self.meta.items():
            if c["doc_id"] == doc_id and i not in self.dead:
                self.dead.add(i); n += 1
        self._maybe_compact()
        return n

    def upsert_doc(self, doc_id, new_chunks):
        removed = self.delete_doc(doc_id)
        self.add(new_chunks)
        return removed, len(new_chunks)

    def _maybe_compact(self):
        if len(self.dead) > 0.2 * max(len(self.meta), 1):
            self.compactions += 1
            self._rebuild([self.meta[i] for i in self.live()])

    def search(self, qvec, k=30, allowed=None):
        """allowed: функція chunk->bool (пре-фільтр за метаданими)."""
        ok = [i for i in self.live() if allowed is None or allowed(self.meta[i])]
        if not ok:
            return []
        sel = self.faiss.IDSelectorBatch(np.array(ok, dtype="int64"))
        params = self.faiss.SearchParametersHNSW(sel=sel, efSearch=max(HNSW["efSearch"], k))
        D, I = self.index.search(qvec.reshape(1, -1), min(k, len(ok)), params=params)
        return [(self.meta[int(i)], float(d)) for d, i in zip(D[0], I[0]) if i >= 0]


# ------------------------------------------------------------------ BM25
STOP = set("і й та а але або що як це у в на з із зі до від по для про при за не ні чи ж же би б "
           "його її їх він вона воно вони цей ця ці той та те також є був була було були бути "
           "яка який які яке як так ще вже лише тільки також тощо".split())


def stem(w: str) -> str:
    return w[:5] if len(w) > 5 else w


def tokenize(text: str) -> list[str]:
    return [stem(w) for w in re.findall(r"[\w'’-]+", text.lower()) if w not in STOP and len(w) > 1]


class BM25Index:
    def __init__(self, chunks):
        from rank_bm25 import BM25Okapi
        self.chunks = chunks
        self.bm = BM25Okapi([tokenize(c["embed_text"]) for c in chunks])

    def search(self, query, k=30, allowed=None):
        sc = self.bm.get_scores(tokenize(query))
        order = np.argsort(-sc)
        out = []
        for i in order:
            c = self.chunks[int(i)]
            if allowed is not None and not allowed(c):
                continue
            if sc[i] <= 0:
                break
            out.append((c, float(sc[i])))
            if len(out) >= k:
                break
        return out


def rrf(*ranked_lists, k=60, top=30):
    score, keep = {}, {}
    for lst in ranked_lists:
        for r, (c, _) in enumerate(lst, 1):
            score[c["chunk_id"]] = score.get(c["chunk_id"], 0) + 1.0 / (k + r)
            keep[c["chunk_id"]] = c
    ids = sorted(score, key=lambda x: -score[x])[:top]
    return [(keep[i], score[i]) for i in ids]


class Reranker:
    def __init__(self, device=None):
        from sentence_transformers import CrossEncoder
        self.m = CrossEncoder(RERANKER, device=device, max_length=512)

    def rerank(self, query, cands, top=None):
        if not cands:
            return []
        sc = self.m.predict([(query, c["text"]) for c, _ in cands], show_progress_bar=False)
        out = sorted(zip([c for c, _ in cands], map(float, sc)), key=lambda x: -x[1])
        return out[:top] if top else out


def make_filter(role="admin", types=None, date_from=None, date_to=None):
    allowed_s = ROLE_ACCESS[role]

    def f(c):
        if c["sensitivity"] not in allowed_s:
            return False
        if types and c["type"] not in types:
            return False
        if date_from and c["date"] < date_from:
            return False
        if date_to and c["date"] > date_to:
            return False
        return True
    return f


class HybridSearcher:
    def __init__(self, chunks, enc: Encoder, reranker: Reranker | None):
        self.chunks, self.enc, self.rr = chunks, enc, reranker
        self.vs = VectorStore(enc, chunks)
        self.bm = BM25Index(chunks)

    def search(self, query, mode="hybrid_rerank", k=10, flt=None, pool=30):
        if mode == "bm25":
            return self.bm.search(query, k, flt)
        qv = self.enc.queries([query])[0]
        dense = self.vs.search(qv, pool if mode != "dense" else k, flt)
        if mode == "dense":
            return dense[:k]
        fused = rrf(dense, self.bm.search(query, pool, flt), k=60, top=pool)
        if mode == "hybrid":
            return fused[:k]
        return self.rr.rerank(query, fused)[:k]


# ------------------------------------------------------------------ релевантність і метрики
def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower().replace("’", "'").replace("\u0301", "")).strip()


def locate(evidence, docs_by_id):
    """Повертає (doc_id, section) для цитати-доказу."""
    q = norm(evidence["quote"])
    d = docs_by_id[evidence["doc_id"]]
    for name, paras in d["sections"]:
        for p in paras:
            if q in norm(p):
                return d["doc_id"], name
    return d["doc_id"], None


def chunk_grade(chunk, item, located) -> int:
    t = norm(chunk["text"])
    for ev in item["evidence"]:
        q = norm(ev["quote"])
        if chunk["doc_id"] == ev["doc_id"] and (q in t or (len(q) > 80 and (q[:len(q)//2] in t or q[len(q)//2:] in t))):
            return 2
    for doc_id, sec in located:
        if chunk["doc_id"] == doc_id and sec and chunk["section"] == sec:
            return 1
    return 0


def evidence_hit(chunk, ev) -> bool:
    q, t = norm(ev["quote"]), norm(chunk["text"])
    return chunk["doc_id"] == ev["doc_id"] and (q in t or (len(q) > 80 and (q[:len(q)//2] in t or q[len(q)//2:] in t)))


def metrics(results, item, located, all_chunks_grades):
    """results: [(chunk, score)]. Повертає recall@5, recall@10, mrr, ndcg@10."""
    ev = item["evidence"]
    out = {}
    for k in (5, 10):
        top = [c for c, _ in results[:k]]
        out[f"recall@{k}"] = sum(any(evidence_hit(c, e) for c in top) for e in ev) / len(ev)
    rr = 0.0
    for r, (c, _) in enumerate(results[:10], 1):
        if any(evidence_hit(c, e) for e in ev):
            rr = 1.0 / r
            break
    out["mrr"] = rr
    gains = [chunk_grade(c, item, located) for c, _ in results[:10]]
    dcg = sum((2 ** g - 1) / math.log2(i + 2) for i, g in enumerate(gains))
    ideal = sorted(all_chunks_grades, reverse=True)[:10]
    idcg = sum((2 ** g - 1) / math.log2(i + 2) for i, g in enumerate(ideal))
    out["ndcg@10"] = dcg / idcg if idcg else 0.0
    return out
