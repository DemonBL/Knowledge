"""ЛР16 · сервіс графа знань: SPARQL-ендпоінт лише для читання над pyoxigraph (RDF-знімок очищеного графа ЛР14).

Під час старту (і лише якщо сховище порожнє) завантажує data/hub_graph.nt у персистентне сховище GRAPH_STORE
(у Docker — том graph_data). Ендпоінти: GET /health, GET|POST /sparql?query=... (лише SELECT/ASK, тайм-аут, LIMIT ≤ 500).
  uvicorn lab16.api.graph_service:app --port 7878     (або python lab16/api/graph_service.py)
"""
from __future__ import annotations

import os
import re
import time
from pathlib import Path

import pyoxigraph as ox
from fastapi import FastAPI, HTTPException, Request

LAB = Path(__file__).resolve().parents[1]
STORE_DIR = Path(os.environ.get("GRAPH_STORE", LAB / "data" / "graph_store"))
SRC = LAB / "data" / "hub_graph.nt"
WRITE_RE = re.compile(r"\b(INSERT|DELETE|LOAD|CLEAR|CREATE|DROP|COPY|MOVE|ADD)\b", re.I)

app = FastAPI(title="Hub graph (read-only SPARQL)")
STORE: ox.Store | None = None
LOADED = {}


def store():
    global STORE
    if STORE is None:
        STORE_DIR.mkdir(parents=True, exist_ok=True)
        STORE = ox.Store(str(STORE_DIR))
        if len(STORE) == 0:
            t0 = time.time()
            STORE.bulk_load(path=str(SRC), format=ox.RdfFormat.N_TRIPLES)
            STORE.flush()
            LOADED.update(loaded_from=str(SRC.name), load_s=round(time.time() - t0, 2))
        LOADED["triples"] = len(STORE)
    return STORE


@app.on_event("startup")
def _startup():
    store()


@app.get("/health")
def health():
    return {"status": "ok", **LOADED}


def _term(t):
    if t is None:
        return None
    return t.value if hasattr(t, "value") else str(t)


@app.api_route("/sparql", methods=["GET", "POST"])
async def sparql(request: Request, query: str = ""):
    if not query and request.method == "POST":
        body = await request.body()
        query = body.decode("utf-8")
        if query.startswith("query="):
            from urllib.parse import unquote_plus
            query = unquote_plus(query[6:])
    if not query.strip():
        raise HTTPException(400, "порожній запит")
    if WRITE_RE.search(re.sub(r'"[^"]*"', "", query)):
        raise HTTPException(403, "лише читання: оновлення SPARQL заборонені")
    if not re.search(r"\b(SELECT|ASK)\b", query, re.I):
        raise HTTPException(400, "дозволені лише SELECT/ASK")
    if re.search(r"\bSELECT\b", query, re.I) and not re.search(r"\bLIMIT\s+\d+", query, re.I):
        query += "\nLIMIT 500"
    t0 = time.time()
    try:
        res = store().query(query)
    except SyntaxError as e:
        raise HTTPException(400, f"синтаксис SPARQL: {e}")
    if isinstance(res, bool):
        return {"boolean": res}
    vars_ = [v.value for v in res.variables]
    rows = []
    for sol in res:
        rows.append({v: _term(sol[v]) for v in vars_})
        if len(rows) >= 500:
            break
    return {"vars": vars_, "rows": rows, "ms": round((time.time() - t0) * 1000, 1)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", 7878)))
