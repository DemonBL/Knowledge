"""ЛР14 · доступ до сховища знань Hub (знімок для перевірок якості).

Сховище = три частини, що їх використовує RAG з ЛР11:
  G — граф розслідувань ЛР9 (Neo4j; знімок — CSV у lab09/data або очищена версія lab14/data/clean/graph);
  T — корпус ЛР10 (фрагменти corpus.jsonl + картки документів docs.jsonl);
  E — реєстр сутностей Hub: вузли ЛР9 з назвами + індивіди ЛР8 (RDF) + сутності, витягнуті в ЛР13.
Функції повертають pandas/списки; to_rdf() будує RDF-знімок для SHACL і SPARQL-інваріантів.
"""
from __future__ import annotations

import glob
import json
import os
from pathlib import Path

import pandas as pd

LAB = Path(__file__).resolve().parents[1]
HUB = LAB.parent
RAW_GRAPH = HUB / "lab09" / "data"
RAW_CORPUS = HUB / "lab10" / "data" / "corpus.jsonl"
RAW_DOCS = HUB / "lab10" / "data" / "docs.jsonl"
CLEAN = LAB / "data" / "clean"
NS = "http://www.lnu.edu.ua/kb/hub#"
REF_DATE = "2026-11-06"          # дата вимірювання (фіксована, щоб метрики відтворювались)

# Версія сховища: baseline — сирі дані ЛР9/ЛР10; clean — після виправлень ЛР14.
VERSIONS = {"baseline": {"graph": RAW_GRAPH, "corpus": RAW_CORPUS, "docs": RAW_DOCS},
            "clean": {"graph": CLEAN / "graph", "corpus": CLEAN / "corpus.jsonl", "docs": CLEAN / "docs.jsonl"}}


def paths(version: str):
    v = os.environ.get("KB_VERSION", version)
    p = dict(VERSIONS[v])
    if os.environ.get("KB_DIR"):                       # довільний знімок (демонстрація дефектів у CI)
        d = Path(os.environ["KB_DIR"])
        p = {"graph": d / "graph", "corpus": d / "corpus.jsonl", "docs": d / "docs.jsonl"}
    return p


def load_jsonl(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


def graph(version="baseline"):
    d = paths(version)["graph"]
    nodes = {Path(f).stem[6:]: pd.read_csv(f, dtype=str, keep_default_na=False) for f in glob.glob(str(d / "nodes_*.csv"))}
    rels = {Path(f).stem[5:]: pd.read_csv(f, dtype=str, keep_default_na=False) for f in glob.glob(str(d / "rels_*.csv"))}
    return nodes, rels


def corpus(version="baseline"):
    p = paths(version)
    return load_jsonl(p["corpus"]), load_jsonl(p["docs"])


# ------------------------------------------------------------------ RDF-знімок для SHACL / SPARQL
def to_rdf(version="baseline", with_corpus=True):
    from rdflib import Graph, Literal, Namespace, RDF, URIRef, XSD
    H = Namespace(NS)
    g = Graph()
    g.bind("hub", H)
    nodes, rels = graph(version)
    num = {"trustLevel": XSD.integer, "followers": XSD.integer, "shares": XSD.integer,
           "publicationCount": XSD.integer, "minutesAfter": XSD.integer}
    dates = {"createdAt", "publishedAt", "decidedAt", "exifDate", "validFrom", "firstSeenAt"}

    def lit(k, v):
        if v == "":
            return None
        if k in num:
            try:
                return Literal(int(v), datatype=XSD.integer)
            except ValueError:
                return Literal(v)                                 # хибний тип → зловить SHACL
        if k in dates:
            return Literal(v, datatype=XSD.date)
        if k == "confidence":
            try:
                from decimal import Decimal
                return Literal(Decimal(v), datatype=XSD.decimal)
            except Exception:
                return Literal(v)
        if k == "verified":
            return Literal(v == "True", datatype=XSD.boolean)
        return Literal(v)

    for label, df in nodes.items():
        for r in df.to_dict("records"):
            s = H[r["id"]]
            g.add((s, RDF.type, H[label]))
            for k, v in r.items():
                o = lit(k, v)
                if o is not None:
                    g.add((s, H[k], o))
    for rtype, df in rels.items():
        for i, r in enumerate(df.to_dict("records")):
            s, o = H[r["start"]], H[r["end"]]
            g.add((s, H[rtype], o))
            st = H[f"st_{rtype}_{i}"]                              # реіфікація: походження ребра
            g.add((st, RDF.type, H.Statement))
            g.add((st, H.subject, s)); g.add((st, H.predicate, H[rtype])); g.add((st, H.object, o))
            for k in ("source", "confidence", "validFrom"):
                x = lit(k, r.get(k, ""))
                if x is not None:
                    g.add((st, H[k], x))
    if with_corpus:
        ch, docs = corpus(version)
        for d in docs:
            s = H["doc_" + d["doc_id"]]
            g.add((s, RDF.type, H.Document))
            for k in ("doc_id", "title", "type", "sensitivity", "license", "status", "supersededBy", "source_url"):
                if d.get(k):
                    g.add((s, H[k], Literal(d[k])))
            if d.get("date"):
                g.add((s, H.date, Literal(d["date"], datatype=XSD.date)))
        for c in ch:
            s = H["chunk_" + c["chunk_id"].replace(":", "_")]
            g.add((s, RDF.type, H.Chunk))
            g.add((s, H.chunkId, Literal(c["chunk_id"])))
            g.add((s, H.inDocument, H["doc_" + c["doc_id"]]))
            g.add((s, H.text, Literal(c["text"])))
            g.add((s, H.sensitivity, Literal(c["sensitivity"])))
            if c.get("date"):
                g.add((s, H.date, Literal(c["date"], datatype=XSD.date)))
    return g


# ------------------------------------------------------------------ реєстр сутностей (вхід для entity resolution)
G9_TYPES = {"Account": "ACCOUNT", "OfficialSource": "ORG", "FactCheckOrg": "ORG", "FactChecker": "ANALYST",
            "Tool": "METHOD", "Narrative": "NARRATIVE", "Rule": "RULE"}
E13_TYPES = {"ORG": "ORG", "PERSON": "PERSON", "PLATFORM": "PLATFORM", "METHOD": "METHOD",
             "PHENOMENON": "PHENOMENON", "CASE_ID": "CASE_ID"}


def registry():
    """Записи з трьох джерел: id, source, name, type, attrs (для порівняння атрибутів), provenance."""
    from rdflib import Graph, Namespace, RDFS
    out = []
    nodes, _ = graph("baseline")
    for lab, t in G9_TYPES.items():
        for r in nodes[lab].to_dict("records"):
            name = r.get("name") or r.get("condition")
            out.append(dict(rid=f"G9:{r['id']}", source="ЛР9 граф Neo4j", name=name, type=t,
                            code=r["id"], attrs={k: v for k, v in r.items() if k not in ("id", "name")}))
    D = Namespace("http://www.lnu.edu.ua/ontologies/disinfo-analysis.owl#")
    g = Graph().parse(LAB / "data" / "lab08_data.ttl")
    cls = {"AkauntAvtor": "ACCOUNT", "OfitsiineDzherelo": "ORG", "FaktchekinhovaOrhanizatsiia": "ORG",
           "Faktcheker": "ANALYST", "InstrumentVeryfikatsii": "METHOD", "Naratyv": "NARRATIVE",
           "PravyloVeryfikatsii": "RULE"}
    for s, _, c in g.triples((None, None, None)):
        pass
    from rdflib import RDF
    for c, t in cls.items():
        for s in g.subjects(RDF.type, D[c]):
            lab = str(g.value(s, RDFS.label))
            name = g.value(s, D.maieNazvu) or g.value(s, D.umovaPravyla)
            out.append(dict(rid=f"R8:{s.split('#')[1]}", source="ЛР8 RDF", name=str(name), type=t, code=lab,
                            attrs={"label": lab}))
    el = json.load(open(HUB / "lab13" / "results" / "entity_linking.json", encoding="utf-8"))
    for e in el["entities"]:
        if e["type"] not in E13_TYPES:
            continue
        label = " ".join(e["label"].split()).strip("#—–-:;,.( ")
        if not label or label.lower() in ("твердження", "центру", "програма"):
            continue
        out.append(dict(rid=f"E13:{e['iri'].rsplit('/', 1)[1]}|{e['type']}", source="ЛР13 витяг", name=label,
                        type=E13_TYPES[e["type"]], code="",
                        attrs={"variants": [" ".join(v.split()) for v in list(e["variants"])[:6]], "docs": e["docs"]}))
    return out
