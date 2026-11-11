"""ЛР16 · API фінального демонстратора Domain Knowledge Hub.

Ендпоінти:
  GET  /health                     — стан сервісу, графа, LLM, обраних ембедингів
  POST /recommend                  — рекомендації (гібрид RRF; фільтри RBAC/перевіреність/чинність/свіжість) + пояснення зі шляху графа
  GET  /explain?user_id=&item_id=  — пояснення для конкретної пари
  POST /search                     — пошук документів (BM25 [+ e5 на ПК]) з RBAC — інструмент ЛР15
  POST /ask                        — агент ЛР15 (v3, профіль strict, LLM qwen2.5:7b через Ollama на хості)
  POST /sparql                     — проксі до сервісу графа, лише SELECT/ASK
Роль: для відомого user_id роль береться з реєстру користувачів (не з запиту) — спроба підвищити роль ігнорується і журналюється.
Журнал усіх запитів: $LOG_DIR/api_requests.jsonl.
Змінні середовища: OLLAMA_URL, OLLAMA_MODEL, GRAPH_URL, LOG_DIR, RECO_EMB (auto|e5|lsa), HUB_DENSE (0|1), PORT.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

LAB = Path(__file__).resolve().parents[1]
HUB = LAB.parent
sys.path.insert(0, str(LAB / "reco"))
sys.path.insert(0, str(HUB / "lab15" / "agent"))

import csv  # noqa: E402

import explain as X  # noqa: E402
import items as IT  # noqa: E402
import models as M  # noqa: E402

LOG_DIR = Path(os.environ.get("LOG_DIR", LAB / "logs"))
LOG_DIR.mkdir(parents=True, exist_ok=True)
GRAPH_URL = os.environ.get("GRAPH_URL", "http://127.0.0.1:7878")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:7b")
NOW = datetime(2026, 11, 8)

app = FastAPI(title="Domain Knowledge Hub · ЛР16 demo")
S: dict = {}


def log(rec):
    rec["ts"] = datetime.now().isoformat(timespec="seconds")
    with open(LOG_DIR / "api_requests.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")


def state():
    if not S:
        t0 = time.time()
        rows = list(csv.DictReader(open(LAB / "data" / "interactions.csv", encoding="utf-8")))
        users = {u["user_id"]: u for u in csv.DictReader(open(LAB / "data" / "users.csv", encoding="utf-8"))}
        want = os.environ.get("RECO_EMB", "auto")
        emb = "e5" if want == "e5" or (want == "auto" and (LAB / "data" / "item_vecs_e5.npy").exists()) else "lsa"
        ctx = M.Context(IT.load_items(), rows, NOW, emb=emb)
        S.update(ctx=ctx, users=users, emb=emb, load_s=round(time.time() - t0, 2))
        if os.environ.get("HUB_DENSE", "0") != "1":          # пошук ЛР15 лише BM25 (швидкий старт; e5 — HUB_DENSE=1 на ПК)
            import tools as T              # додає lab10/src у sys.path
            import search_core as SC  # noqa
            ch = SC.load_jsonl(HUB / "lab14" / "data" / "clean" / "corpus.jsonl")
            T._STORE["c"] = dict(chunks=ch, bm=SC.BM25Index(ch), enc=None, vecs=None, S=SC)
    return S


@app.on_event("startup")
def _startup():
    state()


def _get(url, timeout=3):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.load(r)


@app.get("/health")
def health():
    st = state()
    out = {"status": "ok", "items": len(st["ctx"].items), "users": len(st["users"]), "interactions": sum(st["ctx"].raw_pop.values()),
           "embeddings": st["emb"], "load_s": st["load_s"]}
    try:
        out["graph"] = _get(GRAPH_URL + "/health")
    except Exception as e:  # noqa
        out["graph"] = {"status": "unavailable", "error": type(e).__name__}
    try:
        tags = _get(OLLAMA_URL + "/api/tags")
        out["llm"] = {"status": "ok", "model": OLLAMA_MODEL, "available": OLLAMA_MODEL in [m["name"] for m in tags.get("models", [])]}
    except Exception as e:  # noqa
        out["llm"] = {"status": "unavailable", "error": type(e).__name__}
    return out


class RecoReq(BaseModel):
    user_id: str | None = None
    interests: list[str] = Field(default_factory=list, description="теми для холодного старту (див. /topics)")
    role: str = "guest"
    k: int = 5
    fresh_days: int | None = None
    require_verified: bool = True
    current_only: bool = True
    mode: str = "rrf"


def _role(user_id, claimed, rid):
    users = state()["users"]
    if user_id and user_id in users:
        real = users[user_id]["role"]
        if claimed and claimed != real:
            log({"rid": rid, "event": "role_escalation_ignored", "user_id": user_id, "claimed": claimed, "role": real})
        return real, claimed != real
    return ("guest" if claimed not in IT.ROLE_ACCESS else claimed), False


@app.get("/topics")
def topics():
    return {t: ds for t, ds in IT.TOPICS.items()}


@app.post("/recommend")
def recommend(req: RecoReq):
    rid = uuid.uuid4().hex[:8]
    t0 = time.time()
    st = state()
    ctx = st["ctx"]
    role, overridden = _role(req.user_id, req.role, rid)
    flt = dict(fresh_days=req.fresh_days, require_verified=req.require_verified, current_only=req.current_only)
    seeds = None
    scenario = "known_user"
    if not req.user_id or req.user_id not in ctx.hist:
        bad = [t for t in req.interests if t not in IT.TOPICS]
        if bad:
            raise HTTPException(400, f"невідомі теми: {bad}; див. /topics")
        from cold_start import topic_seeds
        seeds = topic_seeds(ctx.items, req.interests) if req.interests else {}
        scenario = "cold_start_interests" if seeds else "cold_start_popularity"
    uid = req.user_id or "ANON-" + rid
    k = max(1, min(req.k, 20))
    if seeds == {}:
        ranked, paths = M.popularity(ctx, uid, role, k, **flt), {}
    else:
        ranked, paths = M.hybrid_rec(ctx, uid, role, k, req.mode, w=(0.3, 0.3, 0.4), seeds=seeds, new_slots=1, **flt)
    out = []
    for i, sc in ranked:
        it = ctx.by_id[i]
        e = None
        if i in paths:
            tpl = X.template(paths[i], ctx)
            ok, bad = X.check(tpl, paths[i], ctx)
            if scenario == "cold_start_interests":            # сід — не перегляд, а обрана тема
                tpl = tpl.replace("бо ви переглядали", f"бо обрана вами тема «{ctx.by_id[paths[i][0][2:]]['topic']}» містить", 1)
            e = {"text": tpl, "path": [X.node_label(n, ctx) for n in paths[i]], "check_ok": ok}
        elif i in ctx.new_items:
            e = {"text": "Новий фрагмент, схожий за змістом на ваші інтереси (ще без переглядів).", "path": [], "check_ok": True}
        else:
            e = {"text": "Популярне серед користувачів з вашим рівнем доступу.", "path": [], "check_ok": True}
        out.append({"item_id": i, "title": it["title"], "section": it["section"], "doc": it["doc"], "date": it["date"],
                    "sensitivity": it["sensitivity"], "score": round(float(sc), 5), "explanation": e})
    res = {"request_id": rid, "user_id": req.user_id, "role": role, "role_claim_ignored": overridden, "scenario": scenario,
           "filters": flt, "embeddings": st["emb"], "items": out, "latency_ms": round((time.time() - t0) * 1000, 1)}
    log({"rid": rid, "endpoint": "/recommend", "req": req.model_dump(), "role": role, "scenario": scenario,
         "items": [o["item_id"] for o in out], "latency_ms": res["latency_ms"]})
    return res


@app.get("/explain")
def explain(user_id: str, item_id: str):
    ctx = state()["ctx"]
    seeds = ctx.hist.get(user_id)
    if not seeds or item_id not in ctx.by_id:
        raise HTTPException(404, "немає історії користувача або фрагмента")
    sc, best = M.graph_scores(ctx, seeds, {item_id})
    if item_id not in best:
        return {"item_id": item_id, "explanation": None, "note": "у графі немає шляху від історії користувача до фрагмента"}
    p = best[item_id][1]
    tpl = X.template(p, ctx)
    ok, bad = X.check(tpl, p, ctx)
    return {"item_id": item_id, "path": [X.node_label(n, ctx) for n in p], "explanation": tpl, "check_ok": ok, "problems": bad}


class SearchReq(BaseModel):
    query: str
    role: str = "guest"
    user_id: str | None = None
    k: int = 4


@app.post("/search")
def search(req: SearchReq):
    import tools as T
    rid = uuid.uuid4().hex[:8]
    role, _ = _role(req.user_id, req.role, rid)
    sess = T.Session(role=role, profile="strict", request_id=rid)
    r = T.search_docs(sess, req.query, k=req.k)
    log({"rid": rid, "endpoint": "/search", "query": req.query, "role": role})
    return {"request_id": rid, "role": role, "result": r}


class AskReq(BaseModel):
    question: str
    role: str = "analyst"
    user_id: str | None = None


@app.post("/ask")
def ask(req: AskReq):
    rid = uuid.uuid4().hex[:8]
    role, overridden = _role(req.user_id, req.role, rid)
    try:
        _get(OLLAMA_URL + "/api/tags")
    except Exception as e:  # noqa
        raise HTTPException(503, f"LLM недоступна за {OLLAMA_URL}: {type(e).__name__}. Запустіть Ollama на хості.")
    import agent as A
    from llm import OllamaLLM
    llm = OllamaLLM(model=OLLAMA_MODEL, log_name="demo_llm.jsonl", prompt_version="agent_v3")
    r = A.run(req.question, role=role, profile="strict", version="v3", llm=llm, run_name="demo16")
    keep = ("request_id", "answer", "status", "tools_used", "evidence_ids", "blocked", "latency_s", "llm_calls", "tool_calls")
    res = {k: r.get(k) for k in keep}
    res.update(role=role, role_claim_ignored=overridden)
    log({"rid": rid, "endpoint": "/ask", "question": req.question, "role": role, "status": r.get("status"),
         "blocked": r.get("blocked"), "latency_s": r.get("latency_s")})
    return res


@app.post("/sparql")
async def sparql(request: Request):
    q = (await request.body()).decode("utf-8")
    try:
        req = urllib.request.Request(GRAPH_URL + "/sparql", data=q.encode("utf-8"), method="POST",
                                     headers={"Content-Type": "application/sparql-query"})
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise HTTPException(e.code, json.loads(e.read() or b"{}").get("detail", "помилка графа"))
    except Exception as e:  # noqa
        raise HTTPException(503, f"сервіс графа недоступний: {type(e).__name__}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", 8000)))
