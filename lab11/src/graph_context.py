"""ЛР11 · Результат 2: entity linking запиту до вузлів графа (Neo4j, ЛР9) і витяг підграфа.

Entity linking: 1) явні ідентифікатори (CLM-11, ACC-005, PUB-014, NAR-02 …);
2) назви наративів, офіційних джерел, фактчекінгових організацій, акаунтів (збіг основ слів);
3) твердження — схожість основ слів запиту й тексту твердження (≥ 0.5) з обов'язковим збігом міста.
Підграф: 1–2 кроки від кожної знайденої сутності за шаблонами для її мітки; ліміт 40 рядків.
Кожен рядок має ідентифікатор вузла [G:ID], на який модель може посилатися.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

HUB = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(HUB / "common"))
sys.path.insert(0, str(HUB / "lab10" / "src"))
from search_core import tokenize  # noqa: E402

ID_RE = re.compile(r"\b(CLM|ACC|PUB|NAR|VRD|OFF|ORG|FCH|MED|TOOL|RULE)-\d+\b", re.I)
MAX_LINES = 40


class GraphContext:
    def __init__(self, driver):
        self.drv = driver
        recs = driver.execute_query(
            "MATCH (n) RETURN n.id AS id, labels(n)[0] AS label, "
            "coalesce(n.name, n.text, n.condition) AS name, n.city AS city").records
        self.nodes = {r["id"]: dict(r) for r in recs}
        self.by_label = {}
        for n in self.nodes.values():
            self.by_label.setdefault(n["label"], []).append(n)

    # ------------------------------------------------------------ entity linking
    def link(self, question: str, max_entities: int = 3):
        found = []
        for m in ID_RE.finditer(question):
            nid = m.group(0).upper()
            if nid in self.nodes:
                found.append((nid, 1.0, "id"))
        q_tok = set(tokenize(question))
        for lab in ("Narrative", "OfficialSource", "FactCheckOrg", "Account", "FactChecker"):
            for n in self.by_label.get(lab, []):
                nt = set(tokenize(re.sub(r"\(.*?\)|#\d+", " ", n["name"] or "")))
                if nt and len(nt & q_tok) / len(nt) >= 0.6:
                    found.append((n["id"], len(nt & q_tok) / len(nt) * 0.9, "name"))
        for n in self.by_label.get("Claim", []):
            ct = set(tokenize(n["name"]))
            city = (n["city"] or "").lower()[:4]   # основа міста: «Одеса/Одесі» → «одес»
            if ct and city and any(t.startswith(city) for t in q_tok):
                score = len(ct & q_tok) / len(ct)
                if score >= 0.5:
                    found.append((n["id"], score * 0.95, "claim"))
        best = {}
        for nid, s, how in found:
            if s > best.get(nid, (0, ""))[0]:
                best[nid] = (s, how)
        ranked = sorted(best.items(), key=lambda kv: -kv[1][0])[:max_entities]
        return [{"id": k, "label": self.nodes[k]["label"], "name": self.nodes[k]["name"],
                 "score": round(v[0], 2), "how": v[1]} for k, v in ranked]

    # ------------------------------------------------------------ підграф
    def _q(self, cypher, **p):
        return [dict(r) for r in self.drv.execute_query(cypher, p).records]

    def subgraph(self, entities) -> list[str]:
        lines = []
        for e in entities:
            lines += getattr(self, "_" + e["label"].lower(), self._generic)(e["id"])
        out, seen = [], set()
        for l in lines:
            if l not in seen:
                seen.add(l)
                out.append(l)
        return out[:MAX_LINES]

    def _claim(self, cid):
        L = []
        for r in self._q("""MATCH (c:Claim {id:$id}) OPTIONAL MATCH (c)-[:PART_OF]->(n:Narrative)
            RETURN c.text AS t, c.priority AS p, n.id AS nid, n.name AS nn""", id=cid):
            L.append(f"[G:{cid}] Твердження «{r['t']}», пріоритет перевірки: {r['p']}"
                     + (f"; належить до наративу [G:{r['nid']}] «{r['nn']}»" if r["nid"] else ""))
        for r in self._q("""MATCH (c:Claim {id:$id})<-[:ABOUT]-(v:Verdict)<-[:ISSUED]-(f:FactChecker)
            OPTIONAL MATCH (v)-[b:BASED_ON]->(e)
            RETURN v.id AS v, v.category AS cat, v.confidence AS conf, toString(v.decidedAt) AS d, f.id AS f,
                   f.name AS fn, collect(e.id + ' (' + coalesce(e.name, '') + ')') AS ev""", id=cid):
            L.append(f"[G:{r['v']}] Вердикт щодо [G:{cid}]: «{r['cat']}», впевненість {r['conf']}, дата {r['d']}; "
                     f"виніс [G:{r['f']}] {r['fn']}; докази: {', '.join(r['ev'])}")
        for r in self._q("""MATCH (o:OfficialSource)-[x:REFUTES|CONFIRMS]->(c:Claim {id:$id})
            RETURN o.id AS o, o.name AS on, type(x) AS t""", id=cid):
            act = "спростовує" if r["t"] == "REFUTES" else "підтверджує"
            L.append(f"[G:{r['o']}] {r['on']} {act} твердження [G:{cid}]")
        for r in self._q("""MATCH (c:Claim {id:$id})<-[:MAKES_CLAIM]-(p:Publication)
            WITH c, collect(p) AS ps
            UNWIND ps AS o WITH c, ps, o WHERE NOT (o)-[:DERIVED_FROM]->()
            MATCH (a:Account)-[:PUBLISHED]->(o)
            OPTIONAL MATCH (b:Account)-[:REPOSTED]->(o)
            RETURN size(ps) AS n, o.id AS o, o.shares AS sh, a.id AS a, a.name AS an, a.trust AS tr,
                   count(DISTINCT b) AS reposts""", id=cid):
            L.append(f"[G:{r['o']}] Першоджерело твердження [G:{cid}]: публікація {r['o']} акаунта "
                     f"[G:{r['a']}] {r['an']} (довіра: {r['tr']}), поширень {r['sh']}, репостів {r['reposts']}; "
                     f"усього публікацій із цим твердженням: {r['n']}")
        return L

    def _narrative(self, nid):
        L = []
        for r in self._q("""MATCH (n:Narrative {id:$id})<-[:PART_OF]-(c:Claim)
            OPTIONAL MATCH (c)<-[:ABOUT]-(v:Verdict)
            RETURN n.name AS nn, c.id AS c, c.text AS t, coalesce(v.category, 'не перевірено') AS cat
            ORDER BY c.id""", id=nid):
            L.append(f"[G:{r['c']}] Твердження наративу [G:{nid}] «{r['nn']}»: «{r['t']}» — {r['cat']}")
        for r in self._q("""MATCH (n:Narrative {id:$id})<-[:PART_OF]-(:Claim)<-[:MAKES_CLAIM]-(p:Publication)
            WHERE NOT (p)-[:DERIVED_FROM]->()
            MATCH (a:Account)-[:PUBLISHED]->(p)
            RETURN a.id AS a, a.name AS an, count(p) AS n ORDER BY n DESC""", id=nid):
            L.append(f"[G:{r['a']}] Акаунт {r['an']} — першоджерело {r['n']} публікацій наративу [G:{nid}]")
        return L

    def _account(self, aid):
        L = []
        for r in self._q("""MATCH (a:Account {id:$id})
            OPTIONAL MATCH (a)-[:PUBLISHED]->(p:Publication)
            OPTIONAL MATCH (a)-[:REPOSTED]->(rp:Publication)
            RETURN a.name AS an, a.kind AS k, a.trust AS tr, a.followers AS f, round(a.pagerank, 3) AS pr,
                   a.community AS com, count(DISTINCT p) AS np, count(DISTINCT rp) AS nr""", id=aid):
            L.append(f"[G:{aid}] Акаунт {r['an']}: тип «{r['k']}», довіра {r['tr']}, підписників {r['f']}, "
                     f"PageRank {r['pr']}, спільнота Louvain {r['com']}; публікацій {r['np']}, репостів {r['nr']}")
        for r in self._q("""MATCH (a:Account {id:$id})-[:PUBLISHED]->(p:Publication)-[:MAKES_CLAIM]->(c:Claim)
            OPTIONAL MATCH (c)-[:PART_OF]->(n:Narrative)
            OPTIONAL MATCH (d:Publication)-[:DERIVED_FROM*1..4]->(p)
            RETURN p.id AS p, c.id AS c, c.text AS t, n.id AS n, count(DISTINCT d) AS der
            ORDER BY der DESC LIMIT 10""", id=aid):
            L.append(f"[G:{r['p']}] Публікація акаунта [G:{aid}] з твердженням [G:{r['c']}] «{r['t']}»"
                     + (f" (наратив [G:{r['n']}])" if r["n"] else "") + f"; похідних публікацій: {r['der']}")
        return L

    def _officialsource(self, oid):
        return [f"[G:{oid}] {r['on']} {'спростовує' if r['t']=='REFUTES' else 'підтверджує'} [G:{r['c']}] «{r['ct']}»"
                for r in self._q("""MATCH (o:OfficialSource {id:$id})-[x:REFUTES|CONFIRMS]->(c:Claim)
                RETURN o.name AS on, type(x) AS t, c.id AS c, c.text AS ct ORDER BY c.id LIMIT 15""", id=oid)]

    def _factchecker(self, fid):
        return [f"[G:{r['v']}] {r['fn']} виніс вердикт «{r['cat']}» щодо [G:{r['c']}] «{r['ct']}»"
                for r in self._q("""MATCH (f:FactChecker {id:$id})-[:ISSUED]->(v:Verdict)-[:ABOUT]->(c:Claim)
                RETURN f.name AS fn, v.id AS v, v.category AS cat, c.id AS c, c.text AS ct LIMIT 15""", id=fid)]

    def _publication(self, pid):
        L = []
        for r in self._q("""MATCH (p:Publication {id:$id})<-[:PUBLISHED]-(a:Account), (p)-[:MAKES_CLAIM]->(c:Claim)
            OPTIONAL MATCH (p)-[:DERIVED_FROM]->(par:Publication)
            OPTIONAL MATCH (d:Publication)-[:DERIVED_FROM*1..4]->(p)
            OPTIONAL MATCH (r:Account)-[:REPOSTED]->(p)
            RETURN a.id AS a, a.name AS an, c.id AS c, c.text AS t, par.id AS par, p.shares AS sh,
                   count(DISTINCT d) AS der, collect(DISTINCT r.id) AS rep""", id=pid):
            L.append(f"[G:{pid}] Публікація акаунта [G:{r['a']}] {r['an']} з твердженням [G:{r['c']}] «{r['t']}», "
                     f"поширень {r['sh']}" + (f", похідна від [G:{r['par']}]" if r["par"] else ", першоджерело")
                     + f"; похідних: {r['der']}; репостили: {', '.join(r['rep']) or 'ніхто'}")
        return L

    def _generic(self, nid):
        n = self.nodes[nid]
        return [f"[G:{nid}] {n['label']} «{n['name']}»"]
