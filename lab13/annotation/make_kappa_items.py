"""ЛР13 · вибірка для перевірки узгодженості розмітників: 32 позитивні пари (за типами відношень) + 10 негативних
(сутності з одного абзацу без відношення в золотому наборі). Мітка розмітника A (Claude) — із gold.jsonl."""
import json, random, re
from collections import defaultdict
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
random.seed(13)
corpus = {d["doc_id"]: d for d in map(json.loads, open(ROOT / "data" / "corpus.jsonl", encoding="utf-8"))}
gold = [json.loads(l) for l in open(ROOT / "data" / "gold.jsonl", encoding="utf-8")]
by_rel = defaultdict(list)
for g in gold:
    for r in g["relations"]: by_rel[r["relation"]].append(r)
items = []
for rel, lst in sorted(by_rel.items()):                       # до 4 прикладів кожного типу
    for r in random.sample(lst, min(4, len(lst))):
        items.append(dict(doc_id=r["doc_id"], head=r["head"], tail=r["tail"], label_A=rel, evidence=r["evidence"]))
items = items[:32]
def para_of(text, pos):
    a = text.rfind("\n\n", 0, pos) + 2; b = text.find("\n\n", pos); return text[a: b if b > 0 else len(text)]
for r in items: r["context"] = para_of(corpus[r["doc_id"]]["text"], corpus[r["doc_id"]]["text"].find(r["evidence"]))
neg = []
for g in random.sample(gold, len(gold)):
    text = corpus[g["doc_id"]]["text"]
    related = {(r["head"], r["tail"]) for r in g["relations"]} | {(r["tail"], r["head"]) for r in g["relations"]}
    ents = [m for m in g["entities"] if m["type"] not in ("DATE",)]
    for a in ents:
        for b in ents:
            if a["norm"] != b["norm"] and (a["norm"], b["norm"]) not in related and para_of(text, a["start"]) == para_of(text, b["start"]) and len(neg) < 10 \
               and not any(n["doc_id"] == g["doc_id"] for n in neg):
                neg.append(dict(doc_id=g["doc_id"], head=a["norm"], tail=b["norm"], label_A="NONE", evidence="", context=para_of(text, a["start"])))
items += neg
random.shuffle(items)
for i, it in enumerate(items, 1): it["id"] = f"K{i:02d}"
with open(ROOT / "data" / "kappa_items.jsonl", "w", encoding="utf-8") as f:
    for it in items: f.write(json.dumps(it, ensure_ascii=False) + "\n")
print(len(items), sum(i["label_A"] != "NONE" for i in items))
