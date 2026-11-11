"""ЛР10 · Результат 5, крок 2: двоє розмітників на 12 запитах → Cohen's κ.

Розмітник A — Claude (LLM-експерт, розмітка в eval/annot_A_claude.jsonl, зроблена за текстами кандидатів).
Розмітник B — gemma3:4b (локальна модель через Ollama, незалежно, temperature=0) → eval/annot_B_gemma.jsonl.
Бінарна релевантність: 1 — фрагмент містить відповідь або її суттєву частину; 0 — ні.
Додатково: узгодженість кожного розмітника з автоматичною розміткою за цитатами-доказами (gold).
"""
import json
import sys
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB.parent / "common"))
sys.path.insert(0, str(LAB / "src"))
from hub_common import LLM, write_json  # noqa: E402
import search_core as S  # noqa: E402
from sklearn.metrics import cohen_kappa_score  # noqa: E402

PROMPT = """Запит користувача: «{q}»

Фрагмент документа «{title}» (розділ «{section}»):
\"\"\"{text}\"\"\"

Чи містить цей фрагмент відповідь на запит або її суттєву частину? Відповідай JSON: {{"relevant": 1}} або {{"relevant": 0}}."""


def main():
    cands = S.load_jsonl(LAB / "eval" / "kappa_candidates.jsonl")
    A = {(x["qid"], x["chunk_id"]): x["relevant"] for x in S.load_jsonl(LAB / "eval" / "annot_A_claude.jsonl")}
    outB = LAB / "eval" / "annot_B_gemma.jsonl"
    B = {}
    if outB.exists():
        B = {(x["qid"], x["chunk_id"]): x["relevant"] for x in S.load_jsonl(outB)}
    llm = LLM("gemma3:4b", LAB / "llm_log" / "annotator_B.jsonl", temperature=0.0, seed=42, prompt_version="relevance_v1")
    with open(outB, "a", encoding="utf-8") as f:
        for q in cands:
            for c in q["candidates"]:
                key = (q["qid"], c["chunk_id"])
                if key in B:
                    continue
                r = llm.chat([{"role": "user", "content": PROMPT.format(q=q["query"], title=c["title"],
                                                                         section=c["section"], text=c["text"][:1500])}],
                             task="relevance", fmt="json", max_tokens=20)
                try:
                    lab = int(json.loads(r["text"]).get("relevant", 0))
                except Exception:  # noqa
                    lab = 1 if "1" in r["text"] else 0
                B[key] = lab
                f.write(json.dumps({"qid": q["qid"], "chunk_id": c["chunk_id"], "relevant": lab}, ensure_ascii=False) + "\n")
    gold = {g["qid"]: g for g in S.load_jsonl(LAB / "eval" / "gold.jsonl")}
    keys = [k for k in A if k in B]
    chunks = {c["chunk_id"]: c for c in S.load_jsonl(LAB / "data" / "corpus.jsonl")}
    G = {k: int(any(S.evidence_hit(chunks[k[1]], e) for e in gold[k[0]]["evidence"])) for k in keys}
    a, b, g = [A[k] for k in keys], [B[k] for k in keys], [G[k] for k in keys]
    res = {"n_queries": len({k[0] for k in keys}), "n_pairs": len(keys),
           "kappa_A_B": round(cohen_kappa_score(a, b), 3),
           "agreement_A_B": round(sum(x == y for x, y in zip(a, b)) / len(keys), 3),
           "kappa_A_gold": round(cohen_kappa_score(a, g), 3), "kappa_B_gold": round(cohen_kappa_score(b, g), 3),
           "positives": {"A": sum(a), "B": sum(b), "gold": sum(g)},
           "disagreements": [{"qid": k[0], "chunk_id": k[1], "A": A[k], "B": B[k], "gold": G[k]} for k in keys if A[k] != B[k]]}
    write_json(LAB / "results" / "kappa.json", res)
    print(json.dumps({k: v for k, v in res.items() if k != "disagreements"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
