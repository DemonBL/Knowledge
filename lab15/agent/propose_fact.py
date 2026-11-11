"""ЛР15 · Р5: інструмент propose_fact — пропозиція нового знання з людиною в циклі (HITL).

Конвеєр: пропозиція → валідація (схема предиката, існування сутностей, джерело + дослівна цитата, SHACL на графі з
кандидатом і на записі provenance) → оцінка ризику → рішення:
  low     — автоматичний запис (лише з provenance);
  medium  — черга, запис тільки після схвалення людини (agent/hitl_review.py);
  high    — черга з рекомендацією «відхилити»; рішення приймає лише людина.
Сховище фактів: data/accepted_facts.ttl (RDF + PROV-O, реіфікація) і data/accepted_facts.cypher (для Neo4j);
черга: data/pending.jsonl; журнал аудиту: data/audit_log.jsonl.

  python agent/propose_fact.py demo      # 3 сценарії: низький / середній / високий ризик
  python agent/propose_fact.py metrics   # метрики аудиту → results/hitl_metrics.json
"""
from __future__ import annotations

import json
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tools as T  # noqa: E402

LAB = T.LAB
DATA = LAB / "data"
AUDIT, PENDING = DATA / "audit_log.jsonl", DATA / "pending.jsonl"
ACCEPTED_TTL, ACCEPTED_CY = DATA / "accepted_facts.ttl", DATA / "accepted_facts.cypher"
NS = "http://www.lnu.edu.ua/kb/hub#"

# предикат → (тип суб'єкта, тип об'єкта, базовий ризик). Решта предикатів заборонені.
PREDICATES = {
    "altLabel": ("any", "literal", "low"),             # синонім / альтернативна назва — не змінює висновків
    "COOPERATES_WITH": ("FactCheckOrg|OfficialSource", "entity_or_new", "medium"),
    "USES": ("FactChecker|FactCheckOrg", "Tool", "medium"),
    "PART_OF": ("Claim", "Narrative", "medium"),
    "REFUTES": ("OfficialSource", "Claim", "high"),     # впливає на вердикти
    "CONFIRMS": ("OfficialSource", "Claim", "high"),
    "category": ("Verdict", "literal", "high"),         # зміна вердикту
    "trust": ("Account", "literal", "high"),            # зміна рівня довіри автора
}
RISK_ORDER = ["low", "medium", "high"]
FUNCTIONAL = {"category", "trust"}                     # пропозиція = заміна значення


def now():
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def audit(event, pid, **kw):
    DATA.mkdir(exist_ok=True)
    with open(AUDIT, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": now(), "event": event, "proposal_id": pid, **kw}, ensure_ascii=False) + "\n")


def _type_of(g, eid):
    from rdflib import RDF, URIRef
    t = list(g.objects(URIRef(NS + eid), RDF.type))
    return str(t[0]).split("#")[1] if t else None


def _norm(s):
    return re.sub(r"\s+", " ", (s or "").lower()).strip(" .«»\"")


def validate(fact):
    """Повертає (checks, ok). Кожна перевірка — dict(name, ok, detail)."""
    g = T.graph_store()
    checks = []
    p, s, o = fact.get("predicate"), fact.get("subject", "").strip(), str(fact.get("object", "")).strip()
    spec = PREDICATES.get(p)
    checks.append(dict(name="предикат у білому списку", ok=spec is not None, detail=p))
    st = _type_of(g, s)
    checks.append(dict(name="суб'єкт існує в графі", ok=st is not None, detail=f"{s}: {st}"))
    if spec:
        okt = spec[0] == "any" or (st and st in spec[0].split("|"))
        checks.append(dict(name="тип суб'єкта відповідає сигнатурі", ok=bool(okt), detail=f"{st} ∈ {spec[0]}"))
        if spec[1] not in ("literal", "entity_or_new"):
            ot = _type_of(g, o)
            checks.append(dict(name="тип об'єкта відповідає сигнатурі", ok=ot == spec[1], detail=f"{o}: {ot} = {spec[1]}"))
    checks.append(dict(name="об'єкт непорожній", ok=bool(o), detail=o[:60]))
    # джерело: id фрагмента корпусу + дослівна цитата (provenance)
    c = T.corpus()
    ch = next((x for x in c["chunks"] if x["chunk_id"] == fact.get("source_id")), None)
    checks.append(dict(name="джерело існує в корпусі", ok=ch is not None, detail=fact.get("source_id")))
    quote_ok = bool(ch) and len(_norm(fact.get("quote"))) >= 15 and _norm(fact.get("quote")) in _norm(ch["text"])
    checks.append(dict(name="цитата дослівно є в джерелі", ok=quote_ok, detail=(fact.get("quote") or "")[:80]))
    if ch:
        checks.append(dict(name="джерело чинне", ok=ch.get("status", "чинний") != "superseded", detail=ch.get("status")))
    # SHACL: граф + кандидат не повинен давати нових порушень (кардинальність, типи) + форма запису provenance
    checks.append(shacl_check(g, fact))
    return checks, all(x["ok"] for x in checks)


def shacl_check(g, fact):
    import pyshacl
    from rdflib import Graph, Literal, Namespace, URIRef
    H = Namespace(NS)
    shapes = Graph().parse(T.HUB / "lab14" / "quality" / "shapes.ttl")
    shapes.parse(LAB / "agent" / "fact_shapes.ttl")
    cand = Graph()
    s, p, o = H[fact["subject"]], H[fact["predicate"]], fact["object"]
    spec = PREDICATES.get(fact["predicate"], ("", "literal", ""))
    obj = Literal(o) if spec[1] == "literal" else URIRef(NS + re.sub(r"\W+", "_", o))
    cand.add((s, p, obj))
    rec = H["proposal_" + fact.get("id", "x")]
    from rdflib import RDF
    cand.add((rec, RDF.type, H.FactProposal))
    for k in ("source_id", "quote", "proposer"):
        if fact.get(k):
            cand.add((rec, H[k], Literal(fact[k])))
    cand.add((rec, H.predicate, Literal(fact["predicate"])))
    focus = {s, rec}
    data = g + cand
    if fact["predicate"] in FUNCTIONAL:          # заміна значення: старе значення прибирається з кандидата
        for old in list(g.objects(s, p)):
            data.remove((s, p, old))
    _, rg, _ = pyshacl.validate(data, shacl_graph=shapes, inference="none")
    SH = Namespace("http://www.w3.org/ns/shacl#")
    viol = [str(rg.value(r, SH.resultMessage)) for r in rg.subjects(SH.resultSeverity, SH.Violation) if rg.value(r, SH.focusNode) in focus]
    return dict(name="SHACL (форми ЛР14 + fact_shapes.ttl) для кандидата", ok=not viol, detail="; ".join(viol)[:200] or "0 порушень")


def risk(fact, checks):
    spec = PREDICATES.get(fact["predicate"])
    level = spec[2] if spec else "high"
    why = [f"базовий ризик предиката {fact['predicate']}: {level}"]
    c = T.corpus()
    ch = next((x for x in c["chunks"] if x["chunk_id"] == fact.get("source_id")), None)
    if ch and ch["sensitivity"] != "public" and level == "low":
        level, _ = "medium", why.append("джерело не публічне → щонайменше medium")
    if fact["predicate"] == "COOPERATES_WITH" and T.graph_store().value(None, None, None) is not None:
        why.append("нове відношення (можливо, з новою сутністю) → потрібне схвалення людини")
    return level, why


def propose(fact, proposer="agent"):
    pid = "F" + uuid.uuid4().hex[:6]
    fact = dict(fact, id=pid, proposer=proposer)
    audit("proposal_received", pid, fact=fact)
    checks, ok = validate(fact)
    audit("validated", pid, ok=ok, checks=checks)
    if not ok:
        audit("rejected_by_validation", pid, reasons=[c["name"] for c in checks if not c["ok"]])
        return {"proposal_id": pid, "status": "rejected", "reason": "валідація не пройдена", "checks": checks}
    level, why = risk(fact, checks)
    audit("risk_scored", pid, risk=level, why=why)
    if level == "low":
        apply_fact(fact, approved_by="автоматично (політика: низький ризик)")
        return {"proposal_id": pid, "status": "applied", "risk": level, "checks": checks}
    item = dict(fact, risk=level, why=why, checks=checks, queued_at=now(),
                recommendation="відхилити (змінює висновки/вердикти)" if level == "high" else "схвалити, якщо цитата підтверджує")
    with open(PENDING, "a", encoding="utf-8") as f:
        f.write(json.dumps(item, ensure_ascii=False) + "\n")
    audit("queued_for_human", pid, risk=level)
    return {"proposal_id": pid, "status": "pending_human_approval", "risk": level, "checks": checks}


def apply_fact(fact, approved_by):
    """Запис ЛИШЕ з provenance: реіфікований вислів + PROV-O (джерело, цитата, хто запропонував, хто схвалив, коли)."""
    pid, s, p, o = fact["id"], fact["subject"], fact["predicate"], str(fact["object"])
    spec = PREDICATES[p]
    obj = f'"{o}"' if spec[1] == "literal" else f"hub:{re.sub(r'\\W+', '_', o)}"
    ts = now()
    ttl = f"""
hub:{s} hub:{p} {obj} .
hub:stmt_{pid} a rdf:Statement, prov:Entity ; rdf:subject hub:{s} ; rdf:predicate hub:{p} ; rdf:object {obj} ;
  prov:wasDerivedFrom hub:chunk_{fact['source_id'].replace(':', '_')} ; hub:quote {json.dumps(fact['quote'], ensure_ascii=False)} ;
  prov:wasAttributedTo {json.dumps(fact['proposer'], ensure_ascii=False)} ; hub:approvedBy {json.dumps(approved_by, ensure_ascii=False)} ;
  prov:generatedAtTime "{ts}"^^xsd:dateTime ; hub:proposalId "{pid}" .
"""
    if not ACCEPTED_TTL.exists():
        ACCEPTED_TTL.write_text("@prefix hub: <http://www.lnu.edu.ua/kb/hub#> .\n@prefix prov: <http://www.w3.org/ns/prov#> .\n"
                                "@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .\n@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .\n",
                                encoding="utf-8")
    with open(ACCEPTED_TTL, "a", encoding="utf-8") as f:
        f.write(ttl)
    prov = f"source:'{fact['source_id']}', quote:{json.dumps(fact['quote'], ensure_ascii=False)}, proposedBy:{json.dumps(fact['proposer'], ensure_ascii=False)}, approvedBy:{json.dumps(approved_by, ensure_ascii=False)}, ts:'{ts}', proposalId:'{pid}'"
    cy = (f"MATCH (s {{id:'{s}'}}) SET s.altLabels = coalesce(s.altLabels, []) + ['{o}'], s.altLabelProv = coalesce(s.altLabelProv, []) + ['{pid}'];"
          if p == "altLabel" else f"MATCH (s {{id:'{s}'}}) MERGE (o {{id:'{o}'}}) MERGE (s)-[r:{p}]->(o) SET r += {{{prov}}};")
    with open(ACCEPTED_CY, "a", encoding="utf-8") as f:
        f.write(cy + "\n")
    audit("applied", pid, approved_by=approved_by, triple=[s, p, o])


DEMO = [
    dict(subject="ORG-02", predicate="altLabel", object="stopfake.org", source_id="W14:s001",
         quote="Сайт для перевіряння фактів stopfake.org запустили 2 березня 2014 року"),
    dict(subject="ORG-02", predicate="COOPERATES_WITH", object="Facebook", source_id="W14:s004",
         quote="журналісти StopFake стали партнером Facebook у сфері інформаційного захисту"),
    dict(subject="VRD-28", predicate="category", object="неможливо перевірити", source_id="INT-REG-2026:s001",
         quote="Вердикт «правда» підтверджується двома незалежними офіційними джерелами"),
    dict(subject="ORG-02", predicate="altLabel", object="СтопФейк-2014", source_id="W14:s001",
         quote="StopFake було засновано у 2015 році"),          # невалідна: цитати немає в джерелі
    dict(subject="CLM-17", predicate="PART_OF", object="NAR-01", source_id="W26:s000",
         quote="Пандемія COVID-19 супроводжувалася поширенням дезінформації"),   # невалідна: SHACL (2 наративи) і цитата
]


def demo():
    for f in (PENDING, ACCEPTED_TTL, ACCEPTED_CY, AUDIT):
        if f.exists():
            f.unlink()
    out = []
    for fact in DEMO:
        r = propose(fact, proposer="агент Hub (демо-сценарій Р5)")
        out.append({"fact": fact, **{k: v for k, v in r.items() if k != "checks"},
                    "failed_checks": [c["name"] for c in r["checks"] if not c["ok"]]})
        print(fact["predicate"], fact["object"], "→", r["status"], r.get("risk", ""))
    (LAB / "results").mkdir(exist_ok=True)
    (LAB / "results" / "hitl_demo.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")


def metrics():
    ev = [json.loads(l) for l in open(AUDIT, encoding="utf-8")]
    by = {}
    for e in ev:
        by.setdefault(e["proposal_id"], []).append(e)
    rows = []
    for pid, es in by.items():
        get = lambda name: next((e for e in es if e["event"] == name), None)
        q, d = get("queued_for_human"), get("human_decision")
        risk_ = (get("risk_scored") or {}).get("risk")
        final = "applied" if get("applied") else ("rejected" if get("rejected_by_validation") or (d and d["decision"] == "reject") else "pending")
        dt = None
        if q and d:
            dt = (datetime.fromisoformat(d["ts"]) - datetime.fromisoformat(q["ts"])).total_seconds()
        rows.append(dict(proposal_id=pid, risk=risk_, final=final, human=(d or {}).get("reviewer"), decision=(d or {}).get("decision"),
                         seconds_to_decision=dt, auto=bool(get("applied")) and not d))
    n = len(rows)
    hum = [r for r in rows if r["decision"]]
    out = {"proposals": n, "applied": sum(r["final"] == "applied" for r in rows), "auto_applied": sum(r["auto"] for r in rows),
           "rejected_validation": sum(1 for r in rows if r["final"] == "rejected" and not r["decision"]),
           "human_reviewed": len(hum), "human_approved_share": round(sum(r["decision"] == "approve" for r in hum) / len(hum), 3) if hum else None,
           "approved_share_all": round(sum(r["final"] == "applied" for r in rows) / n, 3) if n else None,
           "mean_seconds_to_decision": round(sum(r["seconds_to_decision"] for r in hum) / len(hum), 1) if hum else None,
           "pending": sum(r["final"] == "pending" for r in rows), "rows": rows}
    (LAB / "results" / "hitl_metrics.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "rows"}, ensure_ascii=False))
    return out


if __name__ == "__main__":
    {"demo": demo, "metrics": metrics}[sys.argv[1] if len(sys.argv) > 1 else "demo"]()
