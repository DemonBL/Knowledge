"""T08–T15 · перевірки даних у стилі Great Expectations (pytest + pandas): унікальність, повнота,
посилальна цілісність, діапазони, походження, актуальність, регресія доказів тестового набору RAG."""
import json
import re
from pathlib import Path

import pandas as pd
import pytest

HUB = Path(__file__).resolve().parents[3]


@pytest.mark.critical
def test_T08_chunk_ids_unique(corpus):
    ids = [c["chunk_id"] for c in corpus[0]]
    dup = [i for i in set(ids) if ids.count(i) > 1]
    assert not dup, f"неунікальні chunk_id: {dup}"


@pytest.mark.critical
def test_T09_no_exact_duplicate_chunks(corpus):
    seen, dup = {}, []
    for c in corpus[0]:
        k = re.sub(r"\W+", "", c["text"].lower())
        if k in seen:
            dup.append((c["chunk_id"], seen[k]))
        seen.setdefault(k, c["chunk_id"])
    assert not dup, f"точні дублікати фрагментів: {dup[:5]} (усього {len(dup)})"


@pytest.mark.critical
def test_T10_chunk_provenance(corpus):
    bad = [c["chunk_id"] for c in corpus[0] if not c.get("source_url") or not c.get("license")]
    assert not bad, f"фрагменти без source_url/license: {len(bad)} (напр. {bad[:3]})"


@pytest.mark.critical
def test_T11_superseded_flagged(corpus):
    docs = {d["doc_id"]: d for d in corpus[1]}
    regs = sorted(k for k in docs if k.startswith("INT-REG"))
    older = regs[:-1]
    bad = [k for k in older if docs[k].get("status") != "superseded" or not docs[k].get("supersededBy")]
    assert not bad, f"нечинні версії регламенту без позначки: {bad}"


@pytest.mark.critical
def test_T12_claim_status_complete(graph):
    nodes, rels = graph
    has_v = set(rels["ABOUT"].end)
    st = nodes["Claim"].get("status", pd.Series([""] * len(nodes["Claim"])))
    bad = [c for c, s in zip(nodes["Claim"].id, st) if c not in has_v and not s]
    assert not bad, f"твердження без вердикту й без статусу: {bad}"


@pytest.mark.critical
def test_T13_referential_integrity(graph):
    nodes, rels = graph
    ids = set().union(*[set(df.id) for df in nodes.values()])
    bad = [(t, r.start, r.end) for t, df in rels.items() for r in df.itertuples() if r.start not in ids or r.end not in ids]
    assert not bad, f"ребра до неіснуючих вузлів: {bad[:5]}"


@pytest.mark.critical
def test_T14_confidence_range(graph):
    _, rels = graph
    bad = [(t, r.start, r.end, r.confidence) for t, df in rels.items() for r in df.itertuples()
           if not (0 <= float(r.confidence) <= 1)]
    assert not bad, f"confidence поза [0, 1]: {bad[:5]}"


@pytest.mark.critical
def test_T15_rag_evidence_preserved(corpus):
    """Регресія: очищення не повинно видалити цитати-докази тестового набору RAG (ЛР11)."""
    norm = lambda s: re.sub(r"\s+", " ", s.lower())
    tests = [json.loads(l) for l in open(HUB / "lab11" / "eval" / "rag_eval.jsonl", encoding="utf-8")]
    miss = [(t["id"], e["doc_id"]) for t in tests for e in t.get("evidence", [])
            if not any(c["doc_id"] == e["doc_id"] and norm(e["quote"]) in norm(c["text"]) for c in corpus[0])]
    assert not miss, f"втрачено докази тестів RAG: {miss}"


@pytest.mark.warning
def test_T16_freshness(corpus):
    from datetime import date
    stale = [d["doc_id"] for d in corpus[1] if (date(2026, 11, 6) - date.fromisoformat(d["date"])).days > 730]
    assert len(stale) / len(corpus[1]) <= 0.1, f"застарілі документи (> 24 міс.): {stale}"
