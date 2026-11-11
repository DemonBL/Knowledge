"""ЛР9 · повний прогін: імпорт → обмеження/індекси → запити → GDS → PROFILE → SPARQL vs Cypher.

Запуск:  F:\\kms_tools\\venv\\Scripts\\python.exe lab09\\src\\run_lab09.py
Результати: lab09/results/lab09_results.json + docs/*.md
"""
import csv
import collections
import json
import shutil
import statistics
import subprocess
import sys
import time
import traceback
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB.parent / "common"))
sys.path.insert(0, str(LAB / "src"))
from hub_common import neo4j_driver, neo4j_import_dir, write_json, md_table, now_iso  # noqa: E402
import cypher_defs as C  # noqa: E402

RES = {"started": now_iso()}
OUT = LAB / "results"
OUT.mkdir(exist_ok=True)
(LAB / "docs").mkdir(exist_ok=True)


def save():
    write_json(OUT / "lab09_results.json", RES)


def step(name):
    def deco(fn):
        def run(*a, **k):
            print(f"\n===== {name}", flush=True)
            t0 = time.time()
            try:
                r = fn(*a, **k)
                RES.setdefault("steps", {})[name] = {"ok": True, "sec": round(time.time() - t0, 1)}
                return r
            except Exception as e:  # noqa
                traceback.print_exc()
                RES.setdefault("steps", {})[name] = {"ok": False, "error": repr(e)}
            finally:
                save()
        return run
    return deco


def val(v):
    """Перетворює значення Neo4j у JSON-сумісне."""
    if hasattr(v, "iso_format"):
        return v.iso_format()
    if isinstance(v, (list, tuple)):
        return [val(x) for x in v]
    if isinstance(v, float):
        return round(v, 4)
    if hasattr(v, "items"):
        return {k: val(x) for k, x in v.items()}
    return v


def q(drv, cypher, **params):
    recs, summary, keys = drv.execute_query(cypher, params, database_="neo4j")
    return keys, [[val(r[k]) for k in keys] for r in recs], summary


# ======================================================================= R2: дані, імпорт
@step("generate+copy csv")
def prepare():
    subprocess.run([sys.executable, str(LAB / "src" / "generate_data.py")], check=True)
    imp = neo4j_import_dir()
    for f in (LAB / "data").glob("*.csv"):
        shutil.copy(f, imp / f.name)
    # файли Cypher для репозиторію
    (LAB / "import").mkdir(exist_ok=True)
    (LAB / "import" / "01_schema.cypher").write_text(";\n".join(C.CONSTRAINTS + C.INDEXES) + ";\n", encoding="utf-8")
    loads = [C.node_load(l) for l in C.LABELS] + [C.rel_load(t) for t in C.REL_ENDS]
    (LAB / "import" / "02_load.cypher").write_text(";\n\n".join(loads) + ";\n", encoding="utf-8")
    (LAB / "queries").mkdir(exist_ok=True)
    for x in C.QUERIES:
        (LAB / "queries" / f"{x['id']}.cypher").write_text(
            f"// {x['id']} · {x['cq']} · {x['title']}\n// {x['question']}\n{x['cypher']};\n", encoding="utf-8")


def counts(drv):
    _, n, _ = q(drv, "MATCH (n) RETURN labels(n)[0] AS label, count(*) AS n ORDER BY label")
    _, r, _ = q(drv, "MATCH ()-[r]->() RETURN type(r) AS type, count(*) AS n ORDER BY type")
    return {"nodes": sum(x[1] for x in n), "rels": sum(x[1] for x in r), "by_label": n, "by_type": r}


@step("schema+import")
def import_all(drv):
    q(drv, "MATCH (n) DETACH DELETE n")
    q(drv, "DROP INDEX publication_shares IF EXISTS")
    for s in C.CONSTRAINTS + C.INDEXES:
        q(drv, s)
    q(drv, "CALL db.awaitIndexes(300)")
    k, rows, _ = q(drv, "SHOW CONSTRAINTS YIELD name, type, labelsOrTypes, properties RETURN *")
    RES["constraints"] = {"cols": k, "rows": rows}
    k, rows, _ = q(drv, "SHOW INDEXES YIELD name, type, labelsOrTypes, properties, state RETURN *")
    RES["indexes"] = {"cols": k, "rows": rows}
    loads = [C.node_load(l) for l in C.LABELS] + [C.rel_load(t) for t in C.REL_ENDS]
    runs = []
    for i in range(2):  # повторний імпорт для перевірки ідемпотентності
        t0 = time.time()
        for s in loads:
            q(drv, s)
        c = counts(drv)
        c["sec"] = round(time.time() - t0, 2)
        runs.append(c)
        print(f"import run {i+1}: {c['nodes']} nodes, {c['rels']} rels")
    RES["import_runs"] = runs
    RES["idempotent"] = runs[0]["nodes"] == runs[1]["nodes"] and runs[0]["rels"] == runs[1]["rels"]
    # порушення обмеження
    try:
        q(drv, "CREATE (:Account {id: 'ACC-001', name: 'Дублікат для перевірки обмеження'})")
        RES["constraint_violation"] = {"raised": False}
    except Exception as e:  # noqa
        RES["constraint_violation"] = {"raised": True, "code": getattr(e, "code", ""),
                                       "message": getattr(e, "message", str(e))}
    print(RES["constraint_violation"])


# ======================================================================= R3: запити
@step("queries")
def run_queries(drv):
    out = []
    for x in C.QUERIES:
        times = []
        for _ in range(5):
            t0 = time.perf_counter()
            k, rows, _ = q(drv, x["cypher"])
            times.append((time.perf_counter() - t0) * 1000)
        out.append({**x, "cols": k, "rows": rows, "ms_median": round(statistics.median(times), 1)})
        print(x["id"], len(rows), "rows")
    RES["queries"] = out


def R(f):
    return list(csv.DictReader(open(LAB / "data" / f, encoding="utf-8")))


@step("manual verification")
def verify():
    """Незалежна перевірка трьох результатів на CSV (без Neo4j), чистим Python."""
    pub = {r["id"]: r for r in R("nodes_Publication.csv")}
    author = {r["end"]: r["start"] for r in R("rels_PUBLISHED.csv")}
    reposters = collections.defaultdict(set)
    for r in R("rels_REPOSTED.csv"):
        reposters[r["end"]].add(r["start"])
    claim_of = {r["start"]: r["end"] for r in R("rels_MAKES_CLAIM.csv")}
    parent = {r["start"]: r["end"] for r in R("rels_DERIVED_FROM.csv")}
    children = collections.defaultdict(list)
    for c, p in parent.items():
        children[p].append(c)
    verdict = {r["end"]: r["start"] for r in R("rels_ABOUT.csv")}
    vcat = {r["id"]: r["category"] for r in R("nodes_Verdict.csv")}
    narr = {r["start"]: r["end"] for r in R("rels_PART_OF.csv")}

    def desc(p, depth=0, maxd=4):
        res = []
        if depth >= maxd:
            return res
        for c in children[p]:
            res.append((c, depth + 1))
            res += desc(c, depth + 1, maxd)
        return res

    # Q01 — топ-3 автори за охопленням спростованих публікацій
    agg = collections.defaultdict(lambda: [0, 0])
    for p, a in author.items():
        c = claim_of[p]
        if c in verdict and vcat[verdict[c]] in ("фейк", "маніпуляція"):
            agg[a][0] += 1
            agg[a][1] += int(pub[p]["shares"])
    top = sorted(agg.items(), key=lambda kv: -kv[1][1])[:3]
    # Q10 — вплив спростувань ДСНС
    refuted = [r["end"] for r in R("rels_REFUTES.csv") if r["start"] == "OFF-01"]
    origins = [p for p, c in claim_of.items() if c in refuted and p not in parent]
    ps = set(origins) | {d for o in origins for d, _ in desc(o)}
    accs = {author[p] for p in ps} | {a for p in ps for a in reposters[p]}
    q10 = {"refutedClaims": len({claim_of[o] for o in origins}), "publicationsToLabel": len(ps),
           "accountsToNotify": len(accs), "reachAffected": sum(int(pub[p]["shares"]) for p in ps)}
    # Q11 — блокування ACC-005
    own = [p for p, a in author.items() if a == "ACC-005"]
    der = {d: dep for o in own for d, dep in desc(o)}
    q11 = {"ownPublications": len(own), "derivedPublications": len(der),
           "maxDepth": max(der.values()) if der else 0,
           "narratives": sorted({narr[claim_of[d]] for d in der if claim_of[d] in narr}),
           "dependentAccounts": len({author[d] for d in der})}
    RES["manual_check"] = {"Q01_top3": [[a, v[0], v[1]] for a, v in top], "Q10": q10, "Q11": q11,
                           "Q11_chain_example": {o: desc(o) for o in own}}
    print(RES["manual_check"])


# ======================================================================= R4: GDS + PROFILE
@step("gds")
def gds(drv):
    _, v, _ = q(drv, "RETURN gds.version() AS v")
    RES["gds_version"] = v[0][0]
    for g in ("spread", "community"):
        q(drv, f"CALL gds.graph.drop('{g}', false) YIELD graphName RETURN graphName")
    k, r, _ = q(drv, """CALL gds.graph.project('spread', ['Account', 'Publication'],
        {REPOSTED: {orientation: 'NATURAL'}, DERIVED_FROM: {orientation: 'NATURAL'},
         PUBLISHED: {orientation: 'REVERSE'}})
        YIELD nodeCount, relationshipCount RETURN nodeCount, relationshipCount""")
    RES["gds_spread_graph"] = dict(zip(k, r[0]))
    k, r, _ = q(drv, """CALL gds.pageRank.write('spread', {writeProperty: 'pagerank', maxIterations: 20,
        dampingFactor: 0.85, concurrency: 1})
        YIELD nodePropertiesWritten, ranIterations, didConverge RETURN *""")
    RES["pagerank_run"] = dict(zip(k, r[0]))
    k, r, _ = q(drv, """MATCH (n) WHERE n.pagerank IS NOT NULL
        RETURN labels(n)[0] AS label, n.id AS id, coalesce(n.name, n.text) AS name,
               n.kind AS kind, round(n.pagerank, 3) AS pagerank
        ORDER BY n.pagerank DESC LIMIT 10""")
    RES["pagerank_top10"] = {"cols": k, "rows": r}
    k, r, _ = q(drv, """MATCH (a:Account) WHERE a.pagerank IS NOT NULL
        RETURN a.kind AS kind, count(*) AS accounts, round(avg(a.pagerank), 3) AS avgPR,
               round(max(a.pagerank), 3) AS maxPR ORDER BY avgPR DESC""")
    RES["pagerank_by_kind"] = {"cols": k, "rows": r}

    k, r, _ = q(drv, """CALL gds.graph.project('community', ['Account', 'Publication', 'Claim', 'Narrative'],
        {PUBLISHED: {orientation: 'UNDIRECTED'}, REPOSTED: {orientation: 'UNDIRECTED'},
         DERIVED_FROM: {orientation: 'UNDIRECTED'}, MAKES_CLAIM: {orientation: 'UNDIRECTED'},
         PART_OF: {orientation: 'UNDIRECTED'}})
        YIELD nodeCount, relationshipCount RETURN nodeCount, relationshipCount""")
    RES["gds_community_graph"] = dict(zip(k, r[0]))
    k, r, _ = q(drv, """CALL gds.louvain.write('community', {writeProperty: 'community', concurrency: 1})
        YIELD communityCount, modularity, ranLevels RETURN *""")
    RES["louvain_run"] = dict(zip(k, r[0]))
    k, r, _ = q(drv, """MATCH (n) WHERE n.community IS NOT NULL
        WITH n.community AS community, collect(n) AS ns
        WITH community, ns, size(ns) AS size
        ORDER BY size DESC LIMIT 8
        RETURN community, size,
          size([x IN ns WHERE x:Account]) AS accounts,
          size([x IN ns WHERE x:Account AND x.kind = 'бот']) AS bots,
          size([x IN ns WHERE x:Account AND x.kind = 'медіа']) AS mediaAcc,
          size([x IN ns WHERE x:Publication]) AS publications,
          [x IN ns WHERE x:Narrative | x.name] AS narratives,
          [x IN ns WHERE x:Account AND x.kind = 'бот' | x.name][..4] AS botExamples""")
    RES["louvain_top"] = {"cols": k, "rows": r}
    _, r, _ = q(drv, "MATCH (n) WHERE n.pagerank IS NOT NULL OR n.community IS NOT NULL "
                     "RETURN count(n.pagerank) AS withPR, count(n.community) AS withCommunity")
    RES["gds_written"] = r[0]
    for g in ("spread", "community"):
        q(drv, f"CALL gds.graph.drop('{g}', false) YIELD graphName RETURN graphName")


def plan_summary(p):
    """Плоский список операторів профілю з db hits і rows."""
    out = []

    def walk(node, depth=0):
        if node is None:
            return
        get = node.get if isinstance(node, dict) else (lambda k, d=None: getattr(node, k, d))
        op = get("operatorType") or get("operator_type")
        hits = get("dbHits") if get("dbHits") is not None else get("db_hits")
        rows = get("rows")
        args = get("args") or get("arguments") or {}
        detail = args.get("Details", "") if hasattr(args, "get") else ""
        out.append({"depth": depth, "operator": str(op).split("@")[0], "rows": rows, "dbHits": hits,
                    "details": str(detail)[:120]})
        for c in (get("children") or []):
            walk(c, depth + 1)
    walk(p)
    return out


def profile(drv, cypher):
    _, _, s = q(drv, "PROFILE " + cypher)
    ops = plan_summary(s.profile)
    times = []
    for _ in range(20):
        t0 = time.perf_counter()
        q(drv, cypher)
        times.append((time.perf_counter() - t0) * 1000)
    return {"operators": ops, "totalDbHits": sum((o["dbHits"] or 0) for o in ops),
            "ms_median": round(statistics.median(times), 2)}


@step("profile")
def prof(drv):
    q(drv, "DROP INDEX publication_shares IF EXISTS")
    before = profile(drv, C.PROFILE_Q1)
    q(drv, C.OPT_INDEX)
    q(drv, "CALL db.awaitIndexes(300)")
    after = profile(drv, C.PROFILE_Q1)
    RES["profile_q1"] = {"query": C.PROFILE_Q1, "index": C.OPT_INDEX, "before": before, "after": after}
    RES["profile_q2"] = {"query": C.PROFILE_Q2, "plan": profile(drv, C.PROFILE_Q2)}
    # переписування Q2: спершу обмежуємо кореневі публікації, потім розгортаємо шляхи
    rewritten = """MATCH (o:OfficialSource {id: 'OFF-01'})-[:REFUTES]->(c:Claim)
MATCH (c)<-[:MAKES_CLAIM]-(origin:Publication)
WHERE NOT (origin)-[:DERIVED_FROM]->()
WITH collect(DISTINCT c) AS cs, collect(origin) AS origins
UNWIND origins AS origin
MATCH (p:Publication)-[:DERIVED_FROM*0..4]->(origin)
WITH cs, collect(DISTINCT p) AS ps
UNWIND ps AS p
MATCH (acc:Account)-[:PUBLISHED|REPOSTED]->(p)
WITH cs, ps, collect(DISTINCT acc) AS accs
RETURN size(cs) AS refutedClaims, size(ps) AS publicationsToLabel, size(accs) AS accountsToNotify,
       reduce(s = 0, x IN ps | s + x.shares) AS reachAffected"""
    k1, r1, _ = q(drv, C.PROFILE_Q2)
    k2, r2, _ = q(drv, rewritten)
    RES["profile_q2_rewrite"] = {"query": rewritten, "plan": profile(drv, rewritten),
                                 "same_result": r1 == r2, "result": r2}


# ======================================================================= R5: SPARQL vs Cypher
DI = "http://www.lnu.edu.ua/ontologies/disinfo-analysis.owl#"
CLASS = {"Account": "AkauntAvtor", "Publication": "Publikatsiia", "Claim": "Tverdzhennia",
         "Narrative": "Naratyv", "Verdict": "Verdykt", "FactChecker": "Faktcheker",
         "Tool": "InstrumentVeryfikatsii", "OfficialSource": "OfitsiineDzherelo",
         "FactCheckOrg": "FaktchekinhovaOrhanizatsiia", "Media": "Mediafail", "Rule": "PravyloVeryfikatsii"}
PROP = {"PUBLISHED": "publikuie", "REPOSTED": "repostyt", "DERIVED_FROM": "pokhodytVid",
        "MAKES_CLAIM": "vysuvaie", "CONTAINS": "mistyt", "PART_OF": "nalezhytDoNaratyvu",
        "ABOUT": "vynosytsiaSchodo", "ISSUED": "vynosyt", "BASED_ON": "gruntuietsiaNaDokazi",
        "REFUTES": "sprostovuie", "CONFIRMS": "pidtverdzhuie", "VERIFIED_WITH": "pereviriaietsiaZaDopomohoiu",
        "USES": "zastosovuie", "WORKS_FOR": "pratsiuieU", "FORMALIZED_IN": "formalizuietsiaU"}
DATA = {"name": "maieNazvu", "shares": "kilkistPoshyren", "category": "kategoriiaVerdyktu",
        "priority": "priorytetPerevirky", "kind": "typ", "text": "tekst", "trustLevel": "rivenDoviry",
        "followers": "kilkistPidpysnykiv"}
INT_PROPS = {"shares", "trustLevel", "followers"}

PAIRS = [
    dict(id="S1", cq="CQ2", title="Скільки тверджень спростувало/підтвердило кожне офіційне джерело",
         cypher="""MATCH (o:OfficialSource)-[r:REFUTES|CONFIRMS]->(c:Claim)
RETURN o.name AS source, type(r) AS action, count(c) AS n ORDER BY source, action""",
         sparql="""PREFIX : <%s>
SELECT ?source ?action (COUNT(?c) AS ?n) WHERE {
  ?o a :OfitsiineDzherelo ; :maieNazvu ?source .
  { ?o :sprostovuie ?c . BIND("REFUTES" AS ?action) }
  UNION
  { ?o :pidtverdzhuie ?c . BIND("CONFIRMS" AS ?action) }
} GROUP BY ?source ?action ORDER BY ?source ?action""" % DI),
    dict(id="S2", cq="CQ3", title="Статус перевірки тверджень із високим пріоритетом",
         cypher="""MATCH (c:Claim {priority: 'високий'})
OPTIONAL MATCH (c)<-[:ABOUT]-(v:Verdict)
RETURN coalesce(v.category, 'очікує') AS status, count(c) AS n ORDER BY status""",
         sparql="""PREFIX : <%s>
SELECT ?status (COUNT(?c) AS ?n) WHERE {
  ?c a :Tverdzhennia ; :priorytetPerevirky "високий" .
  OPTIONAL { ?v :vynosytsiaSchodo ?c ; :kategoriiaVerdyktu ?cat . }
  BIND(COALESCE(?cat, "очікує") AS ?status)
} GROUP BY ?status ORDER BY ?status""" % DI),
    dict(id="S3", cq="CQ1", title="Топ-5 авторів за охопленням спростованих публікацій",
         cypher="""MATCH (a:Account)-[:PUBLISHED]->(p:Publication)-[:MAKES_CLAIM]->(:Claim)<-[:ABOUT]-(v:Verdict)
WHERE v.category IN ['фейк', 'маніпуляція']
RETURN a.id AS account, sum(p.shares) AS reach ORDER BY reach DESC, account LIMIT 5""",
         sparql="""PREFIX : <%s>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?account (SUM(?s) AS ?reach) WHERE {
  ?a :publikuie ?p ; rdfs:label ?account .
  ?p :kilkistPoshyren ?s ; :vysuvaie ?c .
  ?v :vynosytsiaSchodo ?c ; :kategoriiaVerdyktu ?cat .
  FILTER(?cat IN ("фейк", "маніпуляція"))
} GROUP BY ?account ORDER BY DESC(?reach) ?account LIMIT 5""" % DI),
    dict(id="S4", cq="CQ6", title="Кількість публікацій у ланцюжках поширення кожного наративу",
         cypher="""MATCH (n:Narrative)<-[:PART_OF]-(:Claim)<-[:MAKES_CLAIM]-(o:Publication)
WHERE NOT (o)-[:DERIVED_FROM]->()
MATCH (p:Publication)-[:DERIVED_FROM*0..]->(o)
RETURN n.name AS narrative, count(DISTINCT p) AS publications ORDER BY narrative""",
         sparql="""PREFIX : <%s>
SELECT ?narrative (COUNT(DISTINCT ?p) AS ?publications) WHERE {
  ?n a :Naratyv ; :maieNazvu ?narrative .
  ?c :nalezhytDoNaratyvu ?n . ?o :vysuvaie ?c .
  FILTER NOT EXISTS { ?o :pokhodytVid ?x }
  ?p :pokhodytVid* ?o .
} GROUP BY ?narrative ORDER BY ?narrative""" % DI),
    dict(id="S5", cq="CQ11", title="Похідні публікації від публікацій акаунта ACC-005 (аналіз впливу)",
         cypher="""MATCH (:Account {id: 'ACC-005'})-[:PUBLISHED]->(own:Publication)
MATCH (d:Publication)-[:DERIVED_FROM*1..]->(own)
RETURN count(DISTINCT d) AS derived""",
         sparql="""PREFIX : <%s>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT (COUNT(DISTINCT ?d) AS ?derived) WHERE {
  ?a rdfs:label "ACC-005" ; :publikuie ?own .
  ?d :pokhodytVid+ ?own .
}""" % DI),
]


def build_rdf():
    import pyoxigraph as ox
    store = ox.Store()
    lit_int = ox.NamedNode("http://www.w3.org/2001/XMLSchema#integer")
    rdf_type = ox.NamedNode("http://www.w3.org/1999/02/22-rdf-syntax-ns#type")
    label = ox.NamedNode("http://www.w3.org/2000/01/rdf-schema#label")
    quads = []
    for f in (LAB / "data").glob("nodes_*.csv"):
        lab = f.stem[6:]
        for r in csv.DictReader(open(f, encoding="utf-8")):
            s = ox.NamedNode(DI + r["id"])
            quads.append(ox.Quad(s, rdf_type, ox.NamedNode(DI + CLASS[lab])))
            quads.append(ox.Quad(s, label, ox.Literal(r["id"])))
            for k, p in DATA.items():
                if r.get(k):
                    lit = ox.Literal(r[k], datatype=lit_int) if k in INT_PROPS else ox.Literal(r[k])
                    quads.append(ox.Quad(s, ox.NamedNode(DI + p), lit))
    for f in (LAB / "data").glob("rels_*.csv"):
        t = f.stem[5:]
        for r in csv.DictReader(open(f, encoding="utf-8")):
            quads.append(ox.Quad(ox.NamedNode(DI + r["start"]), ox.NamedNode(DI + PROP[t]),
                                 ox.NamedNode(DI + r["end"])))
    store.extend(quads)
    return store, len(quads)


def sparql_rows(store, text):
    res = store.query(text)
    vars_ = [v.value for v in res.variables]
    rows = []
    for sol in res:
        row = []
        for v in vars_:
            x = sol[v]
            val_ = None if x is None else x.value
            if val_ is not None and val_.lstrip("-").isdigit():
                val_ = int(val_)
            row.append(val_)
        rows.append(row)
    return vars_, rows


@step("sparql vs cypher")
def compare(drv):
    store, n = build_rdf()
    RES["rdf_triples"] = n
    out = []
    for x in PAIRS:
        ct, st = [], []
        for _ in range(10):
            t0 = time.perf_counter(); ck, cr, _ = q(drv, x["cypher"]); ct.append((time.perf_counter() - t0) * 1000)
            t0 = time.perf_counter(); sk, sr = sparql_rows(store, x["sparql"]); st.append((time.perf_counter() - t0) * 1000)
        out.append({**x, "cypher_cols": ck, "cypher_rows": cr, "sparql_cols": sk, "sparql_rows": sr,
                    "match": cr == sr, "match_as_set": sorted(map(str, cr)) == sorted(map(str, sr)), "cypher_ms": round(statistics.median(ct), 2),
                    "sparql_ms": round(statistics.median(st), 2),
                    "cypher_lines": len(x["cypher"].splitlines()), "sparql_lines": len(x["sparql"].splitlines()) - 1,
                    "cypher_chars": len(x["cypher"]), "sparql_chars": len(x["sparql"].split("\n", 1)[1])})
        print(x["id"], "match" if cr == sr else "DIFF", cr[:3], sr[:3])
    RES["sparql_vs_cypher"] = out


# ======================================================================= docs
def write_docs():
    d = LAB / "docs"
    if "queries" in RES:
        parts = ["# Результати запитів Cypher (ЛР9, Результат 3)\n",
                 f"Згенеровано автоматично {now_iso()} скриптом src/run_lab09.py на Neo4j 5.26.\n"]
        for x in RES["queries"]:
            parts += [f"## {x['id']} · {x['cq']} · {x['title']}", f"**Питання.** {x['question']}",
                      f"**Конструкції:** {x['kind']} · медіана {x['ms_median']} мс", "```cypher", x["cypher"], "```",
                      md_table(x["cols"], x["rows"]), ""]
        (d / "cypher_results.md").write_text("\n".join(parts), encoding="utf-8")
    if "pagerank_top10" in RES:
        g = ["# Аналіз графа (GDS) і продуктивність (ЛР9, Результат 4)\n", f"GDS {RES.get('gds_version')}",
             "## PageRank (топ-10)", md_table(RES["pagerank_top10"]["cols"], RES["pagerank_top10"]["rows"]),
             "## PageRank за типом акаунта", md_table(RES["pagerank_by_kind"]["cols"], RES["pagerank_by_kind"]["rows"]),
             "## Louvain", f"Запуск: {RES.get('louvain_run')}",
             md_table(RES["louvain_top"]["cols"], RES["louvain_top"]["rows"])]
        if "profile_q1" in RES:
            p = RES["profile_q1"]
            g += ["## PROFILE: запит 1 до/після індексу", "```cypher", p["query"], "```",
                  f"До: db hits = {p['before']['totalDbHits']}, медіана {p['before']['ms_median']} мс",
                  md_table(["оператор", "rows", "dbHits"], [[("  " * o["depth"]) + o["operator"], o["rows"], o["dbHits"]] for o in p["before"]["operators"]]),
                  f"Після `{p['index']}`: db hits = {p['after']['totalDbHits']}, медіана {p['after']['ms_median']} мс",
                  md_table(["оператор", "rows", "dbHits"], [[("  " * o["depth"]) + o["operator"], o["rows"], o["dbHits"]] for o in p["after"]["operators"]])]
        (d / "gds_report.md").write_text("\n\n".join(g), encoding="utf-8")
    if "sparql_vs_cypher" in RES:
        s = ["# SPARQL vs Cypher (ЛР9, Результат 5)\n"]
        for x in RES["sparql_vs_cypher"]:
            s += [f"## {x['id']} · {x['title']}", "```cypher", x["cypher"], "```", "```sparql", x["sparql"], "```",
                  f"Збіг результатів: **{x['match']}** · Cypher {x['cypher_ms']} мс · SPARQL {x['sparql_ms']} мс",
                  md_table(x["cypher_cols"], x["cypher_rows"])]
        (d / "sparql_vs_cypher.md").write_text("\n\n".join(s), encoding="utf-8")


if __name__ == "__main__":
    prepare()
    drv = neo4j_driver()
    _, v, _ = q(drv, "CALL dbms.components() YIELD name, versions, edition RETURN name, versions[0], edition")
    RES["neo4j"] = v
    import_all(drv)
    run_queries(drv)
    verify()
    gds(drv)
    prof(drv)
    compare(drv)
    RES["finished"] = now_iso()
    save()
    write_docs()
    drv.close()
    print("\nDONE. Steps:", json.dumps(RES.get("steps"), ensure_ascii=False))
