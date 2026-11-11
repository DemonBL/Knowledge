"""ЛР14 · Результат 3: виявлення суперечностей у сховищі (граф ЛР9 + корпус ЛР10 + RDF ЛР8).

Кожен детектор повертає список випадків; тип: logical | value | temporal | terminological.
Логічні суперечності шукає «reasoner» — правила регламенту, записані як SPARQL-запити над RDF-знімком
(ті самі запити стоять у CI: quality/tests/test_sparql.py).
  python quality/conflicts.py [baseline|clean]  → results/conflicts_<version>.json
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kb  # noqa: E402

PFX = f"PREFIX hub: <{kb.NS}>\nPREFIX xsd: <http://www.w3.org/2001/XMLSchema#>\n"

# Регламент 2.0 (INT-REG-2026, чинний з 2026-09-01): «правда» — ≥ 2 незалежних офіційних джерела;
# «фейк»/«маніпуляція» — ≥ 2 незалежних доказів.
Q_TRUE_SOURCES = PFX + """
SELECT ?v ?c (COUNT(DISTINCT ?o) AS ?n) WHERE {
  ?v a hub:Verdict ; hub:category "правда" ; hub:decidedAt ?d ; hub:ABOUT ?c .
  FILTER (?d >= "2026-09-01"^^xsd:date)
  FILTER NOT EXISTS { ?v hub:complianceStatus ?cs }
  OPTIONAL { ?o hub:CONFIRMS ?c }
} GROUP BY ?v ?c HAVING (COUNT(DISTINCT ?o) < 2) ORDER BY ?v"""

Q_FAKE_EVIDENCE = PFX + """
SELECT ?v (COUNT(DISTINCT ?e) AS ?n) WHERE {
  ?v a hub:Verdict ; hub:category ?cat ; hub:decidedAt ?d .
  FILTER (?cat IN ("фейк", "маніпуляція") && ?d >= "2026-09-01"^^xsd:date)
  OPTIONAL { ?v hub:BASED_ON ?e }
} GROUP BY ?v HAVING (COUNT(DISTINCT ?e) < 2)"""

Q_VERDICT_BEFORE_PUB = PFX + """
SELECT ?v ?c ?d (MIN(?p) AS ?first) WHERE {
  ?v a hub:Verdict ; hub:ABOUT ?c ; hub:decidedAt ?d .
  ?pub hub:MAKES_CLAIM ?c ; hub:publishedAt ?p .
  FILTER NOT EXISTS { ?v hub:temporalFlag ?f }
} GROUP BY ?v ?c ?d HAVING (?d < MIN(?p)) ORDER BY ?v"""

Q_REFUTED_AND_CONFIRMED = PFX + """
SELECT ?c WHERE { ?a hub:REFUTES ?c . ?b hub:CONFIRMS ?c . }"""

Q_VERDICT_VS_OFFICIAL = PFX + """
SELECT ?v ?c ?cat WHERE {
  ?v hub:ABOUT ?c ; hub:category ?cat .
  { ?o hub:REFUTES ?c . FILTER (?cat = "правда") } UNION { ?o hub:CONFIRMS ?c . FILTER (?cat IN ("фейк", "маніпуляція")) }
}"""


def detect(version="baseline"):
    g = kb.to_rdf(version)
    ch, docs = kb.corpus(version)
    out = []
    rows = list(g.query(Q_TRUE_SOURCES))
    if rows:
        out.append(dict(id="K1", type="logical", title="Вердикт «правда» спирається на одне офіційне джерело, а чинний регламент 2.0 вимагає двох",
                        detector="reasoner: SPARQL-правило Q_TRUE_SOURCES (INT-REG-2026 §2)",
                        items=[f"{str(r.v).split('#')[1]}→{str(r.c).split('#')[1]} (джерел: {r.n})" for r in rows]))
    rows = list(g.query(Q_VERDICT_BEFORE_PUB))
    if rows:
        out.append(dict(id="K2", type="temporal", title="Вердикт винесено раніше, ніж з'явилась перша публікація з твердженням",
                        detector="SPARQL Q_VERDICT_BEFORE_PUB (decidedAt < min(publishedAt))",
                        items=[f"{str(r.v).split('#')[1]} {r.d} < {r.first} ({str(r.c).split('#')[1]})" for r in rows]))
    rows = list(g.query(Q_FAKE_EVIDENCE)) + list(g.query(Q_REFUTED_AND_CONFIRMED)) + list(g.query(Q_VERDICT_VS_OFFICIAL))
    if rows:
        out.append(dict(id="K0", type="logical", title="Інші логічні правила (≥2 доказів для «фейк»; спростовано і підтверджено; вердикт проти офіційного джерела)",
                        detector="SPARQL", items=[str(tuple(r)) for r in rows]))
    # значення з різних джерел: версії регламенту без позначки чинності
    regs = {d["doc_id"]: d for d in docs if d["doc_id"].startswith("INT-REG")}
    txt = {c["chunk_id"]: c["text"] for c in ch}
    if len(regs) > 1 and not any(d.get("status") == "superseded" for d in regs.values()):
        vals = []
        for k in ("INT-REG-2025", "INT-REG-2026"):
            t = " ".join(v for cid, v in txt.items() if cid.startswith(k))
            ev = re.search(r"лише за наявності ([^.]+?) доказ", t)
            hr = re.search(r"протягом (\d+) годин", t)
            vals.append(f"{k}: докази для «фейк» — {ev.group(1) if ev else '?'}; строк — {hr.group(1) if hr else '?'} год")
        out.append(dict(id="K3", type="value", title="Два регламенти дають різні значення вимог до доказів і строків; чинність не позначено",
                        detector="порівняння значень однакових полів у документах-версіях (кореляція назв розділів)", items=vals))
    # значення з різних джерел: правило R2 у ЛР8 (RDF) і ЛР9 (граф)
    from rdflib import Graph, Namespace
    D = Namespace("http://www.lnu.edu.ua/ontologies/disinfo-analysis.owl#")
    g8 = Graph().parse(kb.LAB / "data" / "lab08_data.ttl")
    c8 = str(g8.value(D.Pravylo_R2, D.umovaPravyla))
    nodes, _ = kb.graph(version)
    rule = nodes["Rule"].set_index("id").loc["RULE-2"]
    if c8 != rule["condition"] and not rule.get("altCondition", ""):
        out.append(dict(id="K4", type="value", title="Умова правила R2 різниться в RDF ЛР8 і графі ЛР9 (обсяг «спростованого твердження»)",
                        detector="порівняння атрибутів сутностей, злитих ER (G9:RULE-2 ≡ R8:Pravylo_R2)",
                        items=[f"ЛР8: «{c8}»", f"ЛР9: «{rule['condition']}»"]))
    # термінологічні: ідентифікатори правил R1–R4 vs RULE-1…4; ДСНС vs ДСНС України
    bad = sorted({cid for cid, t in txt.items() if re.search(r"\bR[1-4]\b", t) and not re.search(r"RULE-[1-4] \(R[1-4]\)", t)}
                 | {d["doc_id"] for d in docs if re.search(r"\bR1–R4\b", d["title"]) and "RULE" not in d["title"]})
    if bad:
        out.append(dict(id="K5", type="terminological", title="Правила названо і «R1–R4/R2», і «RULE-1…4» (корпус, ЛР8 vs граф)",
                        detector="регулярні вирази по корпусу + словник канонічних ідентифікаторів", items=bad))
    tit = {d["doc_id"]: d["title"] for d in docs}
    if tit.get("W06") == "Дипфейк" and not any(d.get("altLabel") for d in docs if d["doc_id"] == "W06"):
        out.append(dict(id="K6", type="terminological", title="«Дипфейк» (картка документа) vs «Діпфейк» (назва статті-джерела)",
                        detector="порівняння назви картки з назвою джерела (wiki_cache)", items=["W06: Дипфейк / Діпфейк"]))
    return out


if __name__ == "__main__":
    v = sys.argv[1] if len(sys.argv) > 1 else "baseline"
    res = detect(v)
    (kb.LAB / "results" / f"conflicts_{v}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    for c in res:
        print(c["id"], c["type"], c["title"], len(c["items"]))
