"""ЛР13 · нормалізація + зв'язування сутностей і завантаження графа з походженням.
Вхід: результати витягу (гібрид методів А і Б, див. docs/extraction_eval.md). Вихід:
  data/graph_load.ttl     — RDF 1.2 / RDF-star: кожне відношення — трійка + анотація {| prov |} (source, offset, method, model, prompt, confidence, evidence)
  data/graph_load.cypher  — те саме для Neo4j (MERGE вузлів, властивості походження на ребрах)
  results/entity_linking.json — канонічні сутності, злиті варіанти, правило злиття
  results/graph_proof.json    — відповіді «запитів-доказів» SPARQL (Oxigraph)
Запуск: python src/build_graph.py --inputs results/hybrid_all.jsonl"""
import argparse, json, re, shutil, subprocess, sys, time, urllib.parse, urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from normalize import canon, KB, rel_tail_key  # noqa: E402
from schema import SYMMETRIC  # noqa: E402

KBNS, ONS = "http://www.lnu.edu.ua/kb/entity/", "http://www.lnu.edu.ua/kb/lab13#"
DOCNS = "http://www.lnu.edu.ua/kb/doc/"
CORPUS = {d["doc_id"]: d for d in map(json.loads, open(ROOT / "data" / "corpus.jsonl", encoding="utf-8"))}


def slug(s):
    return re.sub(r"[^\w\-]+", "_", s.strip()).strip("_")[:80]


def esc(s):
    return str(s).replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


def main(inputs, oxbin):
    recs = [json.loads(l) for p in inputs for l in open(ROOT / p, encoding="utf-8")]
    # ---- 1. нормалізація й зв'язування
    groups = defaultdict(lambda: dict(variants=defaultdict(int), types=defaultdict(int), docs=set()))
    for r in recs:
        text = CORPUS[r["doc_id"]]["text"]
        for e in r["entities"]:
            k = (canon(e["text"], e["type"], text), e["type"])
            g = groups[k]; g["variants"][e["text"]] += 1; g["types"][e["type"]] += 1; g["docs"].add(r["doc_id"])
    kb_by_key = {(canon(c, i["type"]), i["type"]): c for c, i in KB.items()}
    ents = {}
    for (k, t), g in groups.items():
        kb_name = kb_by_key.get((k, t))
        label = kb_name or (k if t in ("DATE", "CASE_ID") else max(g["variants"], key=lambda v: (g["variants"][v], -len(v))).strip(" —–-,.:;("))
        rule = ("словник KB (синонім/абревіатура)" if kb_name and any(v != kb_name for v in g["variants"]) else
                "KB: збіг із канонічною назвою" if kb_name else
                "ISO-нормалізація дати" if t == "DATE" else "код CASE_ID / псевдонім → ACC" if t == "CASE_ID" else "лемматизація (5-символьні основи)")
        iri = KB[kb_name]["iri"] if kb_name else KBNS + slug(f"{t}_{label}")
        ents[(k, t)] = dict(iri=iri, label=label, type=t, variants=dict(g["variants"]), docs=sorted(g["docs"]), rule=rule)
    linking = sorted(ents.values(), key=lambda e: (-len(e["variants"]), e["label"]))
    merged = [e for e in linking if len(e["variants"]) > 1]
    (ROOT / "results" / "entity_linking.json").write_text(json.dumps(dict(n_entities=len(ents), n_merged=len(merged), entities=linking),
                                                                      ensure_ascii=False, indent=1), encoding="utf-8")
    # ---- 2. RDF-star і Cypher
    ttl = [f"@prefix kb: <{ONS}> .", "@prefix prov: <http://www.w3.org/ns/prov#> .", "@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .",
           "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .", ""]
    cy = ["// ЛР13 · завантаження графа з походженням (Neo4j 5). Запуск: cypher-shell -f data/graph_load.cypher",
          "CREATE CONSTRAINT kb_entity IF NOT EXISTS FOR (n:KBEntity) REQUIRE n.iri IS UNIQUE;"]
    for e in ents.values():
        ttl.append(f'<{e["iri"]}> a kb:{e["type"]} ; rdfs:label "{esc(e["label"])}" ; kb:linkRule "{esc(e["rule"])}" .')
        for v in e["variants"]:
            if v != e["label"]: ttl.append(f'<{e["iri"]}> kb:altLabel "{esc(v)}" .')
        cy.append(f'MERGE (n:KBEntity {{iri: "{esc(e["iri"])}"}}) SET n:{e["type"]}, n.label = "{esc(e["label"])}", n.variants = {json.dumps(list(e["variants"]), ensure_ascii=False)};')
    for d in {r["doc_id"] for r in recs}:
        c = CORPUS[d]
        ttl.append(f'<{DOCNS}{d}> a prov:Entity ; rdfs:label "{esc(c["title"])}" ; kb:sourceType "{c["source_type"]}" ; kb:url "{esc(c["url"])}" ; kb:license "{esc(c["license"])}" .')
    nrel, seen = 0, set()
    for r in recs:
        text = CORPUS[r["doc_id"]]["text"]
        for x in r["relations"]:
            hk, tk = (canon(x["head"], x["head_type"], text), x["head_type"]), (canon(x["tail"], x["tail_type"], text), x["tail_type"])
            if hk not in ents or tk not in ents:
                for k_, txt in ((hk, x["head"]), (tk, x["tail"])):   # сутність лише у відношенні — додаємо
                    if k_ not in ents:
                        ents[k_] = dict(iri=KBNS + slug(f"{k_[1]}_{txt}"), label=txt, type=k_[1], variants={txt: 1}, docs=[r["doc_id"]], rule="з відношення")
                        ttl.append(f'<{ents[k_]["iri"]}> a kb:{k_[1]} ; rdfs:label "{esc(txt)}" .')
            h, t = ents[hk]["iri"], ents[tk]["iri"]
            if x["relation"] in SYMMETRIC and h > t: h, t = t, h
            key = (h, x["relation"], t, r["doc_id"], x.get("evidence"))
            if key in seen: continue
            seen.add(key); nrel += 1
            ev_s = x.get("ev_start", -1); ev_e = x.get("ev_end", -1)
            conf = x.get("confidence") if x.get("confidence") is not None else 0.5
            status = "candidate" if str(x.get("method", r["method"])).startswith("B") else "accepted"   # рекомендація Р4: Б — кандидати на перевірку
            ann = (f'prov:wasDerivedFrom <{DOCNS}{r["doc_id"]}> ; kb:offsetStart {ev_s} ; kb:offsetEnd {ev_e} ; kb:evidence "{esc(x.get("evidence", ""))}" ; '
                   f'kb:method "{esc(x.get("method", r["method"]))}" ; kb:model "{esc(x.get("model", r["model"]))}" ; kb:promptVersion "{esc(x.get("version", r["version"]))}" ; '
                   f'kb:confidence "{conf}"^^xsd:decimal ; kb:status "{status}" ; prov:generatedAtTime "{r["ts"]}"^^xsd:dateTime')
            ttl.append(f'<{h}> kb:{x["relation"]} <{t}> .')                       # саме твердження
            ttl.append(f'<< <{h}> kb:{x["relation"]} <{t}> >> kb:hasProvenance [ {ann} ] .')   # окремий вузол походження на кожен витяг
            cy.append(f'MATCH (a:KBEntity {{iri: "{esc(h)}"}}), (b:KBEntity {{iri: "{esc(t)}"}}) '
                      f'CREATE (a)-[:{x["relation"]} {{source: "{r["doc_id"]}", offset_start: {ev_s}, offset_end: {ev_e}, evidence: "{esc(x.get("evidence", ""))}", '
                      f'method: "{esc(x.get("method", r["method"]))}", model: "{esc(x.get("model", r["model"]))}", prompt_version: "{esc(x.get("version", r["version"]))}", '
                      f'confidence: {conf}, status: "{status}", extracted_at: "{r["ts"]}"}}]->(b);')
    (ROOT / "data" / "graph_load.ttl").write_text("\n".join(ttl) + "\n", encoding="utf-8")
    (ROOT / "data" / "graph_load.cypher").write_text("\n".join(cy) + "\n", encoding="utf-8")
    # ---- 3. завантаження в Oxigraph і запити-докази
    store = ROOT / "results" / "oxstore"; shutil.rmtree(store, ignore_errors=True)
    subprocess.run([oxbin, "load", "--location", str(store), "--file", str(ROOT / "data" / "graph_load.ttl")], check=True, capture_output=True)
    srv = subprocess.Popen([oxbin, "serve-read-only", "--location", str(store), "--bind", "127.0.0.1:7891"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try: urllib.request.urlopen("http://127.0.0.1:7891/"); break
            except Exception: time.sleep(0.2)
        P = f"PREFIX kb: <{ONS}>\nPREFIX prov: <http://www.w3.org/ns/prov#>\nPREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>\n"
        Q = {
         "counts": "SELECT (COUNT(DISTINCT ?e) AS ?entities) (COUNT(*) AS ?annotated_relations) WHERE { ?e rdfs:label ?l . OPTIONAL {} } ",
         "proof_cpd": """SELECT ?rel ?object ?doc ?start ?end ?method ?model ?conf ?evidence WHERE {
  ?s rdfs:label "Центр протидії дезінформації" .
  << ?s ?p ?o >> kb:hasProvenance ?pv . ?pv prov:wasDerivedFrom ?d ; kb:offsetStart ?start ; kb:offsetEnd ?end ; kb:method ?method ; kb:model ?model ; kb:confidence ?conf ; kb:evidence ?evidence .
  ?o rdfs:label ?object . BIND(REPLACE(STR(?p), ".*#", "") AS ?rel) BIND(REPLACE(STR(?d), ".*/", "") AS ?doc) } ORDER BY ?rel ?object""",
         "by_method": """SELECT ?method ?status (COUNT(*) AS ?relations) (AVG(?c) AS ?avg_conf) WHERE { << ?s ?p ?o >> kb:hasProvenance ?pv . ?pv kb:method ?method ; kb:status ?status ; kb:confidence ?c } GROUP BY ?method ?status""",
         "candidates": """SELECT ?h ?rel ?t ?doc ?conf ?evidence WHERE { << ?s ?p ?o >> kb:hasProvenance ?pv . ?pv kb:status "candidate" ; prov:wasDerivedFrom ?d ; kb:confidence ?conf ; kb:evidence ?evidence .
  ?s rdfs:label ?h . ?o rdfs:label ?t . BIND(REPLACE(STR(?p), ".*#", "") AS ?rel) BIND(REPLACE(STR(?d), ".*/", "") AS ?doc) } ORDER BY DESC(?conf) LIMIT 8""",
         "refuted_claims": """SELECT ?org (COUNT(DISTINCT ?clm) AS ?claims) (GROUP_CONCAT(DISTINCT ?doc; separator=", ") AS ?docs) WHERE {
  << ?o kb:REFUTES ?c >> kb:hasProvenance/prov:wasDerivedFrom ?d . ?o rdfs:label ?org . ?c rdfs:label ?clm . BIND(REPLACE(STR(?d), ".*/", "") AS ?doc) } GROUP BY ?org ORDER BY DESC(?claims)""",
        }
        Q["counts"] = "SELECT (COUNT(DISTINCT ?e) AS ?entities) WHERE { ?e rdfs:label ?l FILTER(!STRSTARTS(STR(?e), \"" + DOCNS + "\")) }"
        Q["relations"] = "SELECT (COUNT(DISTINCT ?pv) AS ?provenance_records) (COUNT(DISTINCT ?s) AS ?subjects) WHERE { << ?s ?p ?o >> kb:hasProvenance ?pv }"
        proof = {}
        for k, q in Q.items():
            req = urllib.request.Request("http://127.0.0.1:7891/query", data=urllib.parse.urlencode({"query": P + q}).encode(),
                                         headers={"Accept": "application/sparql-results+json"})
            j = json.loads(urllib.request.urlopen(req).read())
            vs = j["head"]["vars"]
            proof[k] = dict(query=q, rows=[[b.get(v, {}).get("value") for v in vs] for b in j["results"]["bindings"]], vars=vs)
    finally:
        srv.terminate()
    (ROOT / "results" / "graph_proof.json").write_text(json.dumps(proof, ensure_ascii=False, indent=1), encoding="utf-8")
    print("entities", len(ents), "merged", len(merged), "relations", nrel)
    for k, v in proof.items(): print(k, v["rows"][:6])


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--inputs", nargs="+", required=True)
    ap.add_argument("--ox", default=str(ROOT.parent / "fuseki" / "ox")); a = ap.parse_args()
    main(a.inputs, a.ox)
