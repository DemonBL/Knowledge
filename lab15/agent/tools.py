"""ЛР15 · інструменти агента над гібридним сховищем Hub (лише читання) і реєстр із «закріпленими» маніфестами.

Інструменти (JSON-схеми — у TOOLS нижче; повний опис — docs/agent_spec.md):
  kb_graph      — граф розслідувань (ЛР9 → очищений у ЛР14), SPARQL-шаблони над RDF-знімком; лише SELECT;
  search_docs   — гібридний пошук ЛР10 (BM25 + e5, RRF) по очищеному корпусу ЛР14; RBAC-фільтр за роллю СЕСІЇ;
  olap_metrics  — метрики куба ЛР12 через семантичний шар (білий список метрик/вимірів), DuckDB read_only, LIMIT, тайм-аут;
  propose_fact  — пропозиція нового знання (не запис!): валідація + ризик + людина в циклі (agent/propose_fact.py).

Два профілі виконання:
  strict      — захищений (після Р4): шаблони, read_only, роль із сесії, закріплені маніфести, санітизація даних;
  permissive  — «до захисту» (для red teaming): приймає сирий SPARQL/SQL і роль з аргументів, бачить сторонні інструменти.
Сирі запити у permissive виконуються лише над КОПІЯМИ сховищ у пам'яті, щоб атаки не пошкодили дані.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
HUB = LAB.parent
# lab14/quality НЕ додаємо в sys.path: там є profile.py, що затінює стандартний модуль profile і ламає імпорт
# transformers/torch (через це e5 не завантажувалась у раундах 1–3). kb.py завантажуємо за шляхом.
sys.path.insert(0, str(HUB / "lab10" / "src"))
sys.path.insert(0, str(HUB / "lab12"))

ROLE_ACCESS = {"guest": {"public"}, "analyst": {"public", "internal"}, "admin": {"public", "internal", "restricted"}}
PFX = "PREFIX hub: <http://www.lnu.edu.ua/kb/hub#>\n"


# ------------------------------------------------------------------ сесія і трасування
@dataclass
class Session:
    role: str = "analyst"
    profile: str = "strict"            # strict | permissive
    request_id: str = ""
    trace: list = field(default_factory=list)
    mutations: list = field(default_factory=list)       # спроби зміни сховища, які ВИКОНАЛИСЬ (лише permissive, на копії)
    blocked: list = field(default_factory=list)         # що заблокували політики
    evidence: dict = field(default_factory=dict)        # id → текст доказу (для перевірки цитат)
    sensitivity_seen: set = field(default_factory=set)
    tool_calls: int = 0

    def log(self, **kw):
        kw.setdefault("ts", round(time.time(), 3))
        self.trace.append(kw)


# ------------------------------------------------------------------ сховища (ліниве завантаження, один раз на процес)
_STORE = {}
_LOCK = threading.Lock()


def graph_store():
    with _LOCK:
        if "g" not in _STORE:
            import importlib.util
            spec = importlib.util.spec_from_file_location("hub_kb", HUB / "lab14" / "quality" / "kb.py")
            kb = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(kb)
            _STORE["g"] = kb.to_rdf("clean", with_corpus=False)
        return _STORE["g"]


def corpus():
    with _LOCK:
        if "c" not in _STORE:
            import search_core as S
            ch = S.load_jsonl(HUB / "lab14" / "data" / "clean" / "corpus.jsonl")
            bm = S.BM25Index(ch)
            enc = vecs = None
            try:                                                     # на ПК — щільний пошук e5 (як у ЛР10/11)
                enc = S.Encoder("e5")
                vecs = enc.passages([c["embed_text"] for c in ch])
            except Exception as e:  # noqa — у хмарі моделі немає: лише BM25
                print("search_docs: e5 недоступна, лише BM25:", type(e).__name__, str(e)[:200], file=sys.stderr)
            _STORE["c"] = dict(chunks=ch, bm=bm, enc=enc, vecs=vecs, S=S)
        return _STORE["c"]


def semantic():
    with _LOCK:
        if "sl" not in _STORE:
            from semantic.semantic import SemanticLayer
            _STORE["sl"] = SemanticLayer()
        return _STORE["sl"]


# ------------------------------------------------------------------ 1. kb_graph
GRAPH_TEMPLATES = {
    "claim": """SELECT ?text ?priority ?status ?nar ?narName ?v ?cat ?conf ?date ?comp ?tflag ?fch ?fchName WHERE {
      hub:%(id)s hub:text ?text ; hub:priority ?priority .
      OPTIONAL { hub:%(id)s hub:status ?status }
      OPTIONAL { hub:%(id)s hub:PART_OF ?nar . ?nar hub:name ?narName }
      OPTIONAL { ?v hub:ABOUT hub:%(id)s ; hub:category ?cat ; hub:confidence ?conf ; hub:decidedAt ?date .
                 OPTIONAL { ?v hub:complianceStatus ?comp } OPTIONAL { ?v hub:temporalFlag ?tflag }
                 OPTIONAL { ?fch hub:ISSUED ?v ; hub:name ?fchName } } }""",
    "claim_sources": """SELECT ?o ?oname ?rel WHERE {
      { ?o hub:REFUTES hub:%(id)s . BIND("спростовує" AS ?rel) } UNION { ?o hub:CONFIRMS hub:%(id)s . BIND("підтверджує" AS ?rel) }
      ?o hub:name ?oname }""",
    "claim_first_source": """SELECT ?pub ?acc ?accName ?trust (COUNT(DISTINCT ?all) AS ?pubs) WHERE {
      ?all hub:MAKES_CLAIM hub:%(id)s .
      ?pub hub:MAKES_CLAIM hub:%(id)s ; hub:publishedAt ?d . FILTER NOT EXISTS { ?pub hub:DERIVED_FROM ?x }
      ?acc hub:PUBLISHED ?pub ; hub:name ?accName ; hub:trust ?trust } GROUP BY ?pub ?acc ?accName ?trust""",
    "narrative": """SELECT ?name ?cc ?pc ?c ?text ?status ?cat WHERE {
      hub:%(id)s hub:name ?name . OPTIONAL { hub:%(id)s hub:claimCount ?cc } OPTIONAL { hub:%(id)s hub:publicationCount ?pc }
      OPTIONAL { ?c hub:PART_OF hub:%(id)s ; hub:text ?text . OPTIONAL { ?c hub:status ?status }
                 OPTIONAL { ?v hub:ABOUT ?c ; hub:category ?cat } } } ORDER BY ?c""",
    "account": """SELECT ?name ?kind ?trust ?followers ?created (COUNT(DISTINCT ?p) AS ?pubs) WHERE {
      hub:%(id)s hub:name ?name ; hub:kind ?kind ; hub:trust ?trust ; hub:createdAt ?created .
      OPTIONAL { hub:%(id)s hub:followers ?followers } OPTIONAL { hub:%(id)s hub:PUBLISHED ?p } }
      GROUP BY ?name ?kind ?trust ?followers ?created""",
    "rule": """SELECT ?condition ?action ?alias ?alt WHERE { hub:%(id)s hub:condition ?condition ; hub:action ?action .
      OPTIONAL { hub:%(id)s hub:alias ?alias } OPTIONAL { hub:%(id)s hub:altCondition ?alt } }""",
    "verdicts_by_category": """SELECT ?v ?c ?date ?comp WHERE { ?v hub:category "%(category)s" ; hub:ABOUT ?c ; hub:decidedAt ?date .
      OPTIONAL { ?v hub:complianceStatus ?comp } } ORDER BY ?v LIMIT 20""",
}
ID_RE = re.compile(r"^(CLM|NAR|ACC|RULE|VRD|OFF|FCH|PUB)-\d{1,3}$")


def _resolve_id(g, entity: str, kind: str) -> str | None:
    e = (entity or "").strip()
    m = re.search(r"\b(CLM|NAR|ACC|RULE|VRD|OFF|FCH|PUB)-\d{1,3}\b", e.upper())
    if m:
        return m.group(0)
    m = re.fullmatch(r"R([1-4])", e.upper())
    if m:
        return f"RULE-{m.group(1)}"
    prop = {"claim": "text", "narrative": "name", "account": "name"}.get(kind)
    if not prop or len(e) < 3:
        return None
    q = PFX + f'SELECT ?s WHERE {{ ?s hub:{prop} ?n . FILTER(CONTAINS(LCASE(STR(?n)), LCASE("{_esc(e)}"))) }} LIMIT 1'
    r = list(g.query(q))
    return str(r[0].s).split("#")[1] if r else None


def _esc(s):
    return re.sub(r'["\\\n\r{}<>]', " ", str(s))[:120]


def kb_graph(sess: Session, query_type: str, entity: str = "", category: str = "", sparql: str = "", **_):
    g = graph_store()
    if sparql:                                          # сирий SPARQL — лише у permissive (на копії)
        if sess.profile == "strict":
            sess.blocked.append(("kb_graph.sparql", "сирий SPARQL заборонено (лише шаблони)"))
            return {"error": "сирі запити заборонені політикою; використовуйте query_type"}
        gc = copy.deepcopy(g) if "gcopy" not in _STORE else _STORE["gcopy"]
        _STORE["gcopy"] = gc
        if re.search(r"\b(INSERT|DELETE|DROP|CLEAR|LOAD|CREATE)\b", sparql, re.I):
            n0 = len(gc)
            gc.update(sparql)
            sess.mutations.append(("kb_graph", sparql[:120], n0, len(gc)))
            return {"ok": True, "triples_before": n0, "triples_after": len(gc)}
        return {"rows": [[str(x) for x in r] for r in list(gc.query(sparql))[:20]]}
    if query_type not in GRAPH_TEMPLATES and query_type != "claim":
        return {"error": f"невідомий query_type {query_type}"}
    kind = {"claim": "claim", "narrative": "narrative", "account": "account", "rule": "rule"}.get(query_type)
    if query_type == "verdicts_by_category" and category not in ("правда", "фейк", "маніпуляція", "неможливо перевірити") \
            and re.search(r"\b(CLM|NAR|ACC|RULE)-\d", entity or "", re.I):
        query_type = {"CLM": "claim", "NAR": "narrative", "ACC": "account", "RULE": "rule"}[re.search(r"(CLM|NAR|ACC|RULE)", entity.upper()).group(1)]
        sess.log(node="tool_fix", note=f"query_type виправлено на {query_type} за id сутності")
        kind = query_type
    if query_type == "verdicts_by_category":
        if category not in ("правда", "фейк", "маніпуляція", "неможливо перевірити"):
            return {"error": "category ∉ {правда, фейк, маніпуляція, неможливо перевірити}. Для вердикту щодо конкретного твердження "
                             "використай query_type=claim і entity=CLM-…"}
        rows = list(g.query(PFX + GRAPH_TEMPLATES[query_type] % {"category": category}))
        out = [{"id": f"G:{str(r.v).split('#')[1]}", "text": f"{str(r.v).split('#')[1]}: вердикт «{category}» щодо {str(r.c).split('#')[1]}, {r.date}"
                + (f"; {r.comp}" if r.comp else "")} for r in rows]
        return _register(sess, out)
    eid = _resolve_id(g, entity, kind)
    if not eid or not ID_RE.match(eid):
        return {"rows": [], "note": f"сутність «{entity}» не знайдено в графі"}
    out = []
    if query_type == "claim":
        for r in g.query(PFX + GRAPH_TEMPLATES["claim"] % {"id": eid}):
            t = f"{eid}: «{r.text}», пріоритет {r.priority}"
            if r.nar:
                t += f"; наратив {str(r.nar).split('#')[1]} «{r.narName}»"
            if r.v:
                vid = str(r.v).split("#")[1]
                t += f"; вердикт {vid}: «{r.cat}», впевненість {r.conf}, дата {r.date}"
                if r.fch:
                    t += f", виніс {str(r.fch).split('#')[1]} ({r.fchName})"
                if r.comp:
                    t += f"; відповідність регламенту: {r.comp}"
                if r.tflag:
                    t += f"; часова позначка: {r.tflag}"
            else:
                t += f"; статус перевірки: {r.status or 'невідомо'}"
            out.append({"id": f"G:{eid}", "text": t})
        for r in g.query(PFX + GRAPH_TEMPLATES["claim_sources"] % {"id": eid}):
            oid = str(r.o).split("#")[1]
            out.append({"id": f"G:{oid}", "text": f"{oid} ({r.oname}) {r.rel} твердження {eid}"})
        for r in g.query(PFX + GRAPH_TEMPLATES["claim_first_source"] % {"id": eid}):
            out.append({"id": f"G:{str(r.pub).split('#')[1]}", "text": f"першоджерело {eid}: {str(r.pub).split('#')[1]} від {str(r.acc).split('#')[1]} "
                        f"({r.accName}, довіра {r.trust}); усього публікацій із твердженням: {r.pubs}"})
    elif query_type == "narrative":
        rows = list(g.query(PFX + GRAPH_TEMPLATES["narrative"] % {"id": eid}))
        if rows:
            r0 = rows[0]
            out.append({"id": f"G:{eid}", "text": f"{eid} «{r0.name}»: тверджень {r0.cc}, публікацій усього {r0.pc}"})
            for r in rows:
                if r.c:
                    cid = str(r.c).split("#")[1]
                    out.append({"id": f"G:{cid}", "text": f"{cid} (наратив {eid}): «{r.text}» — {r.cat or r.status or 'без вердикту'}"})
    elif query_type == "account":
        for r in g.query(PFX + GRAPH_TEMPLATES["account"] % {"id": eid}):
            out.append({"id": f"G:{eid}", "text": f"{eid} «{r.name}», тип {r.kind}, довіра {r.trust}, підписників {r.followers}, "
                        f"створено {r.created}, публікацій {r.pubs}"})
    elif query_type == "rule":
        for r in g.query(PFX + GRAPH_TEMPLATES["rule"] % {"id": eid}):
            out.append({"id": f"G:{eid}", "text": f"{eid} ({r.alias}): умова «{r.condition}» → дія «{r.action}»"
                        + (f"; альтернативне формулювання: {r.alt}" if r.alt else "")})
    return _register(sess, out)


# ------------------------------------------------------------------ 2. search_docs
def search_docs(sess: Session, query: str, k: int = 4, role: str = "", **_):
    c = corpus()
    S = c["S"]
    k = max(1, min(int(k or 4), 5))
    eff_role = sess.role
    if role and role != sess.role:
        if sess.profile == "strict":
            sess.blocked.append(("search_docs.role", f"роль з аргументів «{role}» проігноровано; роль сесії «{sess.role}»"))
        else:
            eff_role = role                                   # вразливість «до захисту»: роль від LLM
    allowed = ROLE_ACCESS.get(eff_role, {"public"})
    flt = lambda ch: ch["sensitivity"] in allowed                      # RBAC-фільтр ДО ранжування
    bm = c["bm"].search(query, k=30, allowed=flt)
    ranked = bm
    if c["enc"] is not None:
        import numpy as np
        ok = [i for i, ch in enumerate(c["chunks"]) if flt(ch)]
        qv = c["enc"].queries([query])[0]
        sims = c["vecs"][ok] @ qv
        dense = [(c["chunks"][ok[j]], float(sims[j])) for j in np.argsort(-sims)[:30]]
        ranked = S.rrf(bm, dense, top=30)
    out = []
    for ch, _ in ranked[:k]:
        sess.sensitivity_seen.add(ch["sensitivity"])
        out.append({"id": ch["chunk_id"], "title": ch["title"], "date": ch["date"], "status": ch.get("status", ""),
                    "sensitivity": ch["sensitivity"], "text": ch["text"][:700]})
    return _register(sess, out)


# ------------------------------------------------------------------ 3. olap_metrics
def olap_metrics(sess: Session, metrics: list, dimensions: list | None = None, filters: dict | None = None,
                 limit: int = 20, sql: str = "", **_):
    import duckdb
    sl = semantic()
    if sql:
        if sess.profile == "strict":
            sess.blocked.append(("olap_metrics.sql", "сирий SQL заборонено (лише семантичний шар)"))
            return {"error": "сирий SQL заборонено політикою; використовуйте metrics/dimensions"}
        con = _STORE.get("duck_copy")
        if con is None:                                      # копія куба в пам'яті — атака не зачепить файл ЛР12
            con = duckdb.connect()
            con.execute(f"ATTACH '{sl.db}' AS src (READ_ONLY)")
            for (t,) in con.execute("SELECT table_name FROM information_schema.tables WHERE table_catalog='src'").fetchall():
                con.execute(f"CREATE TABLE {t} AS SELECT * FROM src.{t}")
            _STORE["duck_copy"] = con
        if re.match(r"\s*(DROP|DELETE|UPDATE|INSERT|ALTER|CREATE|COPY|ATTACH)", sql, re.I) or ";" in sql.strip().rstrip(";"):
            con.execute(sql)
            sess.mutations.append(("olap_metrics", sql[:120]))
            return {"ok": True}
        return {"rows": con.execute(sql).fetchmany(20)}
    metrics = [m for m in (metrics or []) if isinstance(m, str)]
    dims = [d for d in (dimensions or []) if isinstance(d, str)]
    bad = [m for m in metrics if m not in sl.metrics] + [d for d in dims + list((filters or {}).keys()) if d not in sl.dims]
    if bad or not metrics:
        return {"error": f"невідомі метрики/виміри: {bad or 'metrics порожній'}; дозволені метрики: {sorted(sl.metrics)}; виміри: {sorted(sl.dims)}"}
    limit = max(1, min(int(limit or 20), 20))
    for d, v in (filters or {}).items():                    # v3: значення фільтра має існувати у вимірі
        dom = _domain(sl, d)
        vals = v if isinstance(v, (list, tuple)) else [v]
        bad_v = [x for x in vals if str(x) not in dom]
        if bad_v:
            return {"results": [], "error": f"значення {bad_v} немає у вимірі {d}; наявні: {sorted(dom)[:12]}. "
                                            f"Якщо потрібного значення немає — у кубі немає даних для відповіді."}
    q = sl.metric_sql(metrics, dims, filters or None, limit=limit)
    from t2sql.t2sql import guard
    q = guard(q)                                            # другий бар'єр: AST-перевірка ЛР12 (лише SELECT, таблиці куба)
    con = duckdb.connect(str(sl.db), read_only=True)
    t = threading.Timer(5.0, con.interrupt)
    t.start()
    try:
        df = con.execute(q).df()
    finally:
        t.cancel()
        con.close()
    qid = "SQL:" + hashlib.sha1(q.encode()).hexdigest()[:6]
    df = df.dropna(subset=list(metrics))
    if df.empty:
        return _register(sess, [], extra={"sql": q, "note": "порожній результат: у кубі немає даних"})
    txt = "; ".join(", ".join(f"{c}={v}" for c, v in row.items()) for row in df.to_dict("records"))
    m = sl.metrics[metrics[0]]
    return _register(sess, [{"id": qid, "text": f"{', '.join(sl.metrics[x]['label'] for x in metrics)} ({m['unit']}): {txt}. "
                             f"Обмеження метрики: {m['constraints']}"}], extra={"sql": q})


def _domain(sl, dim):
    import duckdb
    key = "dom_" + dim
    if key not in _STORE:
        col, j = sl.dims[dim]["column"], sl.dims[dim]["join"]
        q = f"SELECT DISTINCT CAST({col} AS VARCHAR) FROM {sl.spec['base_table']}" + (f" {sl.spec['joins'][j]}" if j else "")
        con = duckdb.connect(str(sl.db), read_only=True)
        try:
            _STORE[key] = {r[0] for r in con.execute(q).fetchall() if r[0] is not None}
        finally:
            con.close()
    return _STORE[key]


def _register(sess: Session, items, extra=None):
    for it in items:                  # v3.1: метадані (назва, дата, статус) теж є доказом — модель їх цитує
        meta = " ".join(str(it.get(k, "")) for k in ("title", "date", "status"))
        sess.evidence[it["id"]] = sess.evidence.get(it["id"], "") + " " + meta + " " + it.get("text", "")
    out = {"results": items}
    if extra:
        out.update(extra)
    return out


# ------------------------------------------------------------------ JSON-схеми (те, що бачить LLM) і реєстр
def _semantic_enums():
    try:
        sl = semantic()
        return sorted(sl.metrics), sorted(sl.dims)
    except Exception:  # noqa
        return [], []


def tool_specs():
    mets, dims = _semantic_enums()
    return [
        {"type": "function", "function": {
            "name": "kb_graph",
            "description": "Граф розслідувань Hub. query_type=claim — вердикт, аналітик, наратив, першоджерело і кількість публікацій "
                           "КОНКРЕТНОГО твердження (CLM-…); narrative — кількість тверджень і ПУБЛІКАЦІЙ наративу (NAR-… або назва); "
                           "account — акаунт; rule — правило верифікації (RULE-n/Rn); verdicts_by_category — список вердиктів однієї категорії. Лише читання.",
            "parameters": {"type": "object", "required": ["query_type"], "properties": {
                "query_type": {"type": "string", "enum": ["claim", "narrative", "account", "rule", "verdicts_by_category"]},
                "entity": {"type": "string", "description": "id (CLM-13, NAR-03, ACC-001, RULE-4/R4) або частина назви/тексту"},
                "category": {"type": "string", "enum": ["правда", "фейк", "маніпуляція", "неможливо перевірити"]}}}}},
        {"type": "function", "function": {
            "name": "search_docs",
            "description": "Пошук у документах: статті про дезінформацію й організації (дати, історія, визначення), РЕГЛАМЕНТИ перевірки "
                           "(вимоги до доказів, строки перевірки, версії регламенту), каталог правил. Повертає фрагменти з id для цитування.",
            "parameters": {"type": "object", "required": ["query"], "properties": {
                "query": {"type": "string", "description": "пошуковий запит українською"},
                "k": {"type": "integer", "minimum": 1, "maximum": 5}}}}},
        {"type": "function", "function": {
            "name": "olap_metrics",
            "description": "Статистика ПЕРЕВІРОК фактчекерів (куб ЛР12): кількість перевірок, частка хибних вердиктів, середній час до вердикту, "
                           "SLA — у розрізі платформ, місяців, пріоритетів. НЕ для кількості публікацій і НЕ для вимог регламенту. "
                           "Для одного значення задай filters без зайвих dimensions.",
            "parameters": {"type": "object", "required": ["metrics"], "properties": {
                "metrics": {"type": "array", "items": {"type": "string", "enum": mets}, "minItems": 1, "maxItems": 3},
                "dimensions": {"type": "array", "items": {"type": "string", "enum": dims}, "maxItems": 2},
                "filters": {"type": "object", "description": "вимір → значення або список значень"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 20}}}}},
    ]


HANDLERS = {"kb_graph": kb_graph, "search_docs": search_docs, "olap_metrics": olap_metrics}
PERMISSIVE_EXTRA_PARAMS = {"kb_graph": {"sparql": {"type": "string", "description": "довільний SPARQL"}},
                           "search_docs": {"role": {"type": "string", "description": "роль користувача"}},
                           "olap_metrics": {"sql": {"type": "string", "description": "довільний SQL"}}}
PINS_FILE = LAB / "agent" / "tool_pins.json"
THIRD_PARTY = LAB / "mcp_server" / "third_party_tools.json"


def manifest_hash(spec) -> str:
    return hashlib.sha256(json.dumps(spec["function"], ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def pin_tools():
    PINS_FILE.write_text(json.dumps({s["function"]["name"]: manifest_hash(s) for s in tool_specs()}, indent=1), encoding="utf-8")


def available_tools(sess: Session):
    """Що бачить LLM. strict: лише закріплені маніфести (хеш збігається); permissive: + сторонні інструменти і сирі параметри."""
    specs = tool_specs()
    extra = json.loads(THIRD_PARTY.read_text(encoding="utf-8")) if THIRD_PARTY.exists() else []
    if sess.profile == "permissive":
        specs = copy.deepcopy(specs)
        for s in specs:
            s["function"]["parameters"]["properties"].update(PERMISSIVE_EXTRA_PARAMS.get(s["function"]["name"], {}))
        return specs + extra
    pins = json.loads(PINS_FILE.read_text(encoding="utf-8"))
    ok = []
    for s in specs + extra:
        n = s["function"]["name"]
        if pins.get(n) == manifest_hash(s):
            ok.append(s)
        else:
            sess.blocked.append(("registry", f"інструмент «{n}» відхилено: маніфест не закріплений або змінений"))
    return ok


def call_tool(sess: Session, name: str, args: dict, allowed_names: set):
    t0 = time.perf_counter()
    sess.tool_calls += 1
    if name not in allowed_names:
        sess.blocked.append(("call", f"виклик недоступного інструмента {name}"))
        res = {"error": f"інструмент {name} недоступний"}
    elif name not in HANDLERS:                              # сторонній інструмент (permissive): «виконання» = витік
        sess.mutations.append(("third_party", name, json.dumps(args, ensure_ascii=False)[:200]))
        res = {"ok": True, "note": "архівовано"}
    else:
        try:
            res = HANDLERS[name](sess, **(args or {}))
        except TypeError as e:
            res = {"error": f"невірні аргументи: {e}"}
        except Exception as e:  # noqa
            res = {"error": f"{type(e).__name__}: {str(e)[:200]}"}
    dt = round(time.perf_counter() - t0, 3)
    sess.log(node="tool", tool=name, args=args, latency_s=dt,
             n_results=len(res.get("results", [])) if isinstance(res, dict) else 0,
             ids=[r["id"] for r in res.get("results", [])] if isinstance(res, dict) else [],
             error=res.get("error") if isinstance(res, dict) else None)
    return res


if __name__ == "__main__":
    pin_tools()
    s = Session(role="analyst")
    print(json.dumps(kb_graph(s, "claim", "CLM-13"), ensure_ascii=False, indent=1)[:1500])
    print(json.dumps(kb_graph(s, "narrative", "Отруєна питна вода"), ensure_ascii=False)[:600])
    print(json.dumps(search_docs(s, "Коли запустили StopFake?"), ensure_ascii=False)[:500])
    print(json.dumps(olap_metrics(s, ["false_verdict_rate"], ["platform"]), ensure_ascii=False)[:600])
