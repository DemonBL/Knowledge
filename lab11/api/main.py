"""ЛР11 · Результат 3: REST API чат-бота (FastAPI).

Ендпоінти:  POST /ask · GET /health · GET /sources/{id}
Автентифікація: заголовок X-API-Key. Ключі НЕ зберігаються в коді: при першому запуску
генеруються у файл api/keys.local.json (додано до .gitignore), у коді — лише SHA-256 хеші в пам'яті.
Ролі: guest → public; analyst → public+internal; admin → +restricted (той самий пре-фільтр, що в ЛР10).
Ліміт: 10 запитів / 60 с на ключ (sliding window) → 429. Валідація — Pydantic → 422.
Запуск: uvicorn api.main:app --port 8000   (з папки lab11)
"""
from __future__ import annotations

import hashlib
import json
import secrets
import sys
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

LAB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB / "src"))
sys.path.insert(0, str(LAB.parent / "lab10" / "src"))
sys.path.insert(0, str(LAB.parent / "common"))

KEYS_FILE = LAB / "api" / "keys.local.json"
RATE_LIMIT, RATE_WINDOW = 10, 60.0
ROLE_ACCESS = {"guest": {"public"}, "analyst": {"public", "internal"},
               "admin": {"public", "internal", "restricted"}}


def load_keys() -> dict[str, str]:
    if not KEYS_FILE.exists():
        keys = {secrets.token_urlsafe(24): role for role in ("guest", "analyst", "admin")}
        KEYS_FILE.write_text(json.dumps(keys, indent=1), encoding="utf-8")
    raw = json.loads(KEYS_FILE.read_text(encoding="utf-8"))
    return {hashlib.sha256(k.encode()).hexdigest(): role for k, role in raw.items()}


KEY_HASHES = load_keys()
_hits: dict[str, deque] = defaultdict(deque)
STATE: dict = {}


def get_rag():
    if "rag" not in STATE:
        from rag import RAG
        from graph_context import GraphContext
        from hub_common import neo4j_driver
        try:
            graph = GraphContext(neo4j_driver())
        except Exception:  # noqa
            graph = None
        STATE["rag"] = RAG(k=5, use_graph=graph is not None, graph=graph, log_name="api_log.jsonl")
    return STATE["rag"]


# ------------------------------------------------------------------ моделі
class AskRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=500, description="Питання українською")
    use_graph: bool = Field(True, description="Додавати підграф із Neo4j")
    k: int = Field(5, ge=1, le=10, description="Кількість фрагментів контексту")

    @field_validator("question")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("питання не може бути порожнім")
        return v.strip()


class Source(BaseModel):
    id: str
    title: str
    sensitivity: Literal["public", "internal", "restricted"]
    score: float


class AskResponse(BaseModel):
    answer: str
    abstained: bool
    sources: list[Source]
    citations_valid: list[str]
    citations_invalid: list[str]
    graph_entities: list[dict]
    role: str
    latency_s: float
    tokens: dict


app = FastAPI(title="Domain Knowledge Hub · RAG-бот «Аналіз достовірності інформації»",
              version="1.0", description="ЛР11: RAG + граф знань, цитування, політика «не знаю», ролі доступу.")


def auth(request: Request, x_api_key: str | None = Header(None, alias="X-API-Key")) -> str:
    if not x_api_key:
        raise HTTPException(401, "Потрібен заголовок X-API-Key")
    h = hashlib.sha256(x_api_key.encode()).hexdigest()
    role = KEY_HASHES.get(h)
    if role is None:
        raise HTTPException(401, "Невірний API-ключ")
    now = time.monotonic()
    q = _hits[h]
    while q and now - q[0] > RATE_WINDOW:
        q.popleft()
    if len(q) >= RATE_LIMIT:
        retry = int(RATE_WINDOW - (now - q[0])) + 1
        raise HTTPException(429, f"Перевищено ліміт {RATE_LIMIT} запитів за {int(RATE_WINDOW)} с",
                            headers={"Retry-After": str(retry)})
    q.append(now)
    return role


@app.get("/health", summary="Стан сервісу")
def health():
    from hub_common import port_open
    return {"status": "ok", "neo4j": port_open(7687), "ollama": port_open(11434),
            "rag_loaded": "rag" in STATE}


@app.post("/ask", response_model=AskResponse, summary="Питання → відповідь із джерелами")
def ask(req: AskRequest, role: str = Depends(auth)):
    rag = get_rag()
    rag.k, rag.use_graph = req.k, req.use_graph and rag.graph is not None
    r = rag.answer(req.question, role)
    return AskResponse(answer=r["answer"], abstained=r["abstained"], sources=r["sources"],
                       citations_valid=r["citations_valid"], citations_invalid=r["citations_invalid"],
                       graph_entities=r["graph_entities"], role=role, latency_s=r["latency_s"],
                       tokens={"prompt": r["prompt_tokens"], "completion": r["completion_tokens"]})


@app.get("/sources/{source_id}", summary="Повний текст джерела з перевіркою прав")
def source(source_id: str, role: str = Depends(auth)):
    if len(source_id) > 40:
        raise HTTPException(422, "Задовгий ідентифікатор")
    rag = get_rag()
    if source_id.startswith("G:"):
        g = rag.graph
        nid = source_id[2:]
        if g is None or nid not in g.nodes:
            raise HTTPException(404, "Вузол графа не знайдено")
        if role == "guest":
            raise HTTPException(403, "Роль guest не має доступу до графа розслідувань")
        return {"id": source_id, "type": "graph_node", **g.nodes[nid]}
    c = rag.by_id.get(source_id)
    if c is None:
        raise HTTPException(404, "Джерело не знайдено")
    if c["sensitivity"] not in ROLE_ACCESS[role]:
        raise HTTPException(403, f"Роль {role} не має доступу до документів «{c['sensitivity']}»")
    return {k: c[k] for k in ("chunk_id", "doc_id", "title", "section", "type", "date", "sensitivity",
                              "source_url", "text")}


@app.exception_handler(HTTPException)
def http_exc(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.detail, "status": exc.status_code},
                        headers=getattr(exc, "headers", None))
