"""ЛР14 · частина, що потребує ПК (Neo4j + Ollama + модель ембедингів ЛР10). ≈ 20–25 хв на CPU.

Етапи (python lab14/src/pc_run.py [graph|judge|rag|all]):
  graph — відновлює baseline-граф ЛР9 у Neo4j (CSV + GDS, як у ЛР9), рахує Cypher-інваріанти «до»,
          застосовує міграцію data/clean/03_quality_fix.cypher, рахує інваріанти «після»   → results/neo4j_invariants.json
  judge — LLM-суддя (qwen2.5:7b, temperature 0) для пар ER у «сірій зоні»                   → results/dedup_llm_judge.json
  rag   — тестовий набір RAG ЛР11 (31 тест, k = 3, текст + граф) на очищеному сховищі
          (корпус data/clean/corpus.jsonl, граф після міграції, підграф показує нові поля) → results/rag_after.json
Порівняння «до» — збережений прогін ЛР11 opt_k3 (той самий код, моделі, seed і k; граф відновлено з тих самих CSV).
"""
from __future__ import annotations

import json
import shutil
import sys
import time
import traceback
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
HUB = LAB.parent
sys.path.insert(0, str(HUB / "common"))
sys.path.insert(0, str(HUB / "lab10" / "src"))
sys.path.insert(0, str(HUB / "lab11" / "src"))
sys.path.insert(0, str(LAB / "quality"))
from hub_common import LLM, neo4j_driver, neo4j_import_dir, now_iso, write_json  # noqa: E402

RES = LAB / "results"
RES.mkdir(exist_ok=True)
CLEAN = LAB / "data" / "clean"

INVARIANTS = {
    "claims_without_verdict_or_status": "MATCH (c:Claim) WHERE NOT (c)<-[:ABOUT]-(:Verdict) AND c.status IS NULL RETURN count(c) AS n",
    "narratives_without_publicationCount": "MATCH (n:Narrative) WHERE n.publicationCount IS NULL RETURN count(n) AS n",
    "true_verdict_lt2_sources_unflagged": "MATCH (v:Verdict {category:'правда'})-[:ABOUT]->(c:Claim) WHERE v.decidedAt >= date('2026-09-01') "
                                          "AND COUNT { (:OfficialSource)-[:CONFIRMS]->(c) } < 2 AND v.complianceStatus IS NULL RETURN count(v) AS n",
    "verdict_before_first_publication_unflagged": "MATCH (v:Verdict)-[:ABOUT]->(c:Claim)<-[:MAKES_CLAIM]-(p:Publication) WITH v, min(p.publishedAt) AS f "
                                                  "WHERE v.decidedAt < f AND v.temporalFlag IS NULL RETURN count(v) AS n",
    "publications_not_one_author": "MATCH (p:Publication) WITH p, COUNT { (:Account)-[:PUBLISHED]->(p) } AS a WHERE a <> 1 RETURN count(p) AS n",
    "relationships_without_provenance": "MATCH ()-[r]->() WHERE r.source IS NULL OR r.confidence IS NULL OR r.validFrom IS NULL RETURN count(r) AS n",
    "nodes": "MATCH (n) RETURN count(n) AS n",
    "relationships": "MATCH ()-[r]->() RETURN count(r) AS n",
    "accounts_with_pagerank": "MATCH (a:Account) WHERE a.pagerank IS NOT NULL RETURN count(a) AS n",
}


def run_statements(drv, text):
    for st in [s.strip() for s in text.split(";")]:
        body = "\n".join(l for l in st.splitlines() if not l.strip().startswith("//")).strip()
        if body:
            drv.execute_query(body)


def invariants(drv):
    return {k: drv.execute_query(q).records[0]["n"] for k, q in INVARIANTS.items()}


def stage_graph():
    drv = neo4j_driver()
    imp = neo4j_import_dir()
    for f in (HUB / "lab09" / "data").glob("*.csv"):
        shutil.copy(f, imp / f.name)
    drv.execute_query("MATCH (n) DETACH DELETE n")
    run_statements(drv, (HUB / "lab09" / "import" / "01_schema.cypher").read_text(encoding="utf-8"))
    run_statements(drv, (HUB / "lab09" / "import" / "02_load.cypher").read_text(encoding="utf-8"))
    # GDS як у ЛР9 (PageRank і Louvain потрібні шаблонам підграфа ЛР11)
    for g in ("spread", "community"):
        drv.execute_query(f"CALL gds.graph.drop('{g}', false) YIELD graphName RETURN graphName")
    drv.execute_query("""CALL gds.graph.project('spread', ['Account', 'Publication'],
        {REPOSTED: {orientation: 'NATURAL'}, DERIVED_FROM: {orientation: 'NATURAL'}, PUBLISHED: {orientation: 'REVERSE'}})""")
    drv.execute_query("CALL gds.pageRank.write('spread', {writeProperty: 'pagerank', maxIterations: 20, dampingFactor: 0.85, concurrency: 1})")
    drv.execute_query("""CALL gds.graph.project('community', ['Account', 'Publication', 'Claim', 'Narrative'],
        {PUBLISHED: {orientation: 'UNDIRECTED'}, REPOSTED: {orientation: 'UNDIRECTED'}, DERIVED_FROM: {orientation: 'UNDIRECTED'},
         MAKES_CLAIM: {orientation: 'UNDIRECTED'}, PART_OF: {orientation: 'UNDIRECTED'}})""")
    drv.execute_query("CALL gds.louvain.write('community', {writeProperty: 'community', concurrency: 1})")
    for g in ("spread", "community"):
        drv.execute_query(f"CALL gds.graph.drop('{g}', false) YIELD graphName RETURN graphName")
    before = invariants(drv)
    t0 = time.perf_counter()
    run_statements(drv, (CLEAN / "03_quality_fix.cypher").read_text(encoding="utf-8"))
    after = invariants(drv)
    out = {"ts": now_iso(), "before": before, "after": after, "migration_s": round(time.perf_counter() - t0, 2),
           "narratives": [dict(r) for r in drv.execute_query(
               "MATCH (n:Narrative) RETURN n.id AS id, n.claimCount AS claims, n.publicationCount AS pubs ORDER BY id").records]}
    write_json(RES / "neo4j_invariants.json", out)
    print("graph", json.dumps(out, ensure_ascii=False, default=str)[:600])


JUDGE_SYS = ("Ти — експерт з entity resolution у базі знань про дезінформацію. Визнач, чи два записи позначають ОДИН і той самий "
             "об'єкт реального світу (owl:sameAs). Частина/ціле, підрозділ/організація, сервіс/компанія, автор/платформа — це НЕ той самий об'єкт. "
             "Відповідай лише JSON.")


def stage_judge():
    import pandas as pd
    import dedup
    ev = json.loads((RES / "dedup_eval.json").read_text(encoding="utf-8"))
    t = ev["threshold"]
    G = pd.read_csv(LAB / "quality" / "pairs_gold.csv")
    C = pd.read_csv(RES / "dedup_candidates.csv")
    key = lambda a, b: "||".join(sorted([a, b]))
    sc = {key(a, b): s for a, b, s in zip(C.a, C.b, C.score)}
    G["score"] = [sc.get(key(a, b), 0.0) for a, b in zip(G.a, G.b)]
    grey = G[(G.score - t).abs() <= 0.12]
    R = {r["rid"]: r for r in dedup.load_registry()}
    llm = LLM("qwen2.5:7b", LAB / "llm_log" / "er_judge.jsonl", temperature=0.0, seed=42, prompt_version="er_judge_v1")
    out = []
    for g in grey.itertuples():
        a, b = R[g.a], R[g.b]
        desc = lambda r: f"«{r['name']}» (тип {r['type']}, джерело {r['source']}; варіанти: {', '.join(r['attrs'].get('variants', [])[:4]) or '—'})"
        prompt = (f"Запис A: {desc(a)}\nЗапис B: {desc(b)}\n"
                  'Поверни JSON: {"same": true/false, "reason": "коротко"}')
        r = llm.chat([{"role": "system", "content": JUDGE_SYS}, {"role": "user", "content": prompt}], task="er_judge", fmt="json",
                     max_tokens=120, extra={"pair_id": g.pair_id})
        try:
            j = json.loads(r["text"])
            same = bool(j.get("same"))
        except Exception:  # noqa
            j, same = {}, None
        out.append(dict(pair_id=g.pair_id, a=g.a, b=g.b, name_a=a["name"], name_b=b["name"], split=g.split, score=g.score,
                        gold=int(g.label), same=same, reason=j.get("reason", ""), latency_s=r["latency_s"]))
        print("judge", g.pair_id, a["name"], "~", b["name"], "→", same)
    write_json(RES / "dedup_llm_judge.json", {"model": llm.model, "model_version": llm.version(), "threshold": t, "grey_band": 0.12,
                                               "ts": now_iso(), "pairs": out})


def stage_rag():
    import search_core as S
    orig = S.load_jsonl
    S.load_jsonl = lambda p: orig(CLEAN / "corpus.jsonl" if Path(p).name == "corpus.jsonl" else p)   # очищений корпус
    import run_lab11 as R11
    from rag import RAG
    from graph_context import GraphContext

    class GraphContextV2(GraphContext):
        """Шаблони ЛР11 + поля, додані очищенням: статус твердження, агрегати наративу, відповідність регламенту."""

        def _claim(self, cid):
            L = super()._claim(cid)
            r = self._q("MATCH (c:Claim {id:$id}) OPTIONAL MATCH (c)<-[:ABOUT]-(v:Verdict) "
                        "RETURN c.status AS st, v.id AS v, v.complianceStatus AS cs", id=cid)
            if r and r[0]["v"] is None:
                L.append(f"[G:{cid}] Вердикту немає: статус перевірки — «{r[0]['st']}»")
            elif r and r[0]["cs"]:
                L.append(f"[G:{r[0]['v']}] Відповідність регламенту: {r[0]['cs']}")
            return L

        def _narrative(self, nid):
            r = self._q("MATCH (n:Narrative {id:$id}) RETURN n.name AS nn, n.claimCount AS c, n.publicationCount AS p", id=nid)
            head = [f"[G:{nid}] Наратив «{r[0]['nn']}»: тверджень {r[0]['c']}, публікацій усього {r[0]['p']}"] if r and r[0]["p"] is not None else []
            return head + super()._narrative(nid)

    drv = neo4j_driver()
    rag = RAG(k=3, use_graph=True, graph=GraphContextV2(drv), log_name="rag_after_log.jsonl")
    rag.llm = LLM(rag.llm.model, LAB / "llm_log" / "rag_generator.jsonl", temperature=0.1, seed=42, prompt_version=rag.prompt_version)
    rag.log_path = LAB / "logs" / "rag_after_log.jsonl"
    rag.log_path.parent.mkdir(exist_ok=True)
    judge = R11.Judge()
    judge.llm = LLM(R11.JUDGE_MODEL, LAB / "llm_log" / "rag_judge.jsonl", temperature=0.0, seed=7, prompt_version="judge_v1")
    tests = R11.load(HUB / "lab11" / "eval" / "rag_eval.jsonl")
    rows = []
    out = {"started": now_iso(), "config": {"generator": rag.llm.model, "generator_version": rag.llm.version(), "judge": R11.JUDGE_MODEL,
                                             "k": 3, "use_graph": True, "corpus": "lab14/data/clean/corpus.jsonl", "chunks": len(rag.chunks),
                                             "graph": "Neo4j після 03_quality_fix.cypher", "prompt": rag.prompt_version}}
    for t in tests:
        rec = rag.answer(t["question"], t["role"], meta={"stage": "lab14_after", "id": t["id"]})
        m = R11.score_test(t, rec, rag, judge)
        m["answer"], m["sources"] = rec["answer"], [s["id"] for s in rec["sources"]]
        m["graph_lines"] = rec["graph_lines"]
        rows.append(m)
        print("rag", t["id"], t["category"], "pass" if m.get("pass") else "FAIL", "|", rec["answer"][:110].replace("\n", " "))
        out["rows"] = rows
        write_json(RES / "rag_after.json", out)
    out["agg"] = R11.aggregate(rows)
    out["finished"] = now_iso()
    write_json(RES / "rag_after.json", out)
    print("RAG after", out["agg"])


if __name__ == "__main__":
    st = sys.argv[1] if len(sys.argv) > 1 else "all"
    for name, fn in (("graph", stage_graph), ("judge", stage_judge), ("rag", stage_rag)):
        if st in (name, "all"):
            try:
                fn()
            except Exception:  # noqa
                traceback.print_exc()
    print("DONE")
