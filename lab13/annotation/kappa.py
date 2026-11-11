"""ЛР13 · κ Коена між розмітником A (Claude, gold) і розмітником B (gemma3:4b) на 42 парах сутностей (32 відношення + 10 NONE).
Вихід: results/kappa.json (κ, узгодженість, матриця розбіжностей, розбір незбігів)."""
import json
from collections import Counter
from pathlib import Path
from sklearn.metrics import cohen_kappa_score
ROOT = Path(__file__).resolve().parents[1]
A = {i["id"]: i for i in map(json.loads, open(ROOT / "data" / "kappa_items.jsonl", encoding="utf-8"))}
B = {b["id"]: b["label_B"] for b in map(json.loads, open(ROOT / "results" / "kappa_B.jsonl", encoding="utf-8"))}
ids = sorted(A)
a = [A[i]["label_A"] for i in ids]; b = [B.get(i, "NONE") for i in ids]
k = cohen_kappa_score(a, b)
agree = sum(x == y for x, y in zip(a, b)) / len(ids)
ab = [("REL" if x != "NONE" else "NONE") for x in a]; bb = [("REL" if y != "NONE" else "NONE") for y in b]
k_bin = cohen_kappa_score(ab, bb)
P = [i for i in ids if A[i]["label_A"] != "NONE"]
k_pos = cohen_kappa_score([A[i]["label_A"] for i in P], [B.get(i, "NONE") for i in P])
agree_pos = sum(A[i]["label_A"] == B.get(i) for i in P) / len(P)
dis = [dict(id=i, doc=A[i]["doc_id"], head=A[i]["head"], tail=A[i]["tail"], A=x, B=y, context=A[i]["context"][:300]) for i, x, y in zip(ids, a, b) if x != y]
res = dict(n=len(ids), n_positive=sum(x != "NONE" for x in a), agreement=round(agree, 3), kappa=round(k, 3),
           kappa_binary_rel_vs_none=round(k_bin, 3), kappa_positive_only=round(k_pos, 3), agreement_positive_only=round(agree_pos, 3), confusion=Counter(f"{x}→{y}" for x, y in zip(a, b) if x != y).most_common(),
           labels_A=Counter(a), labels_B=Counter(b), disagreements=dis)
(ROOT / "results" / "kappa.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
print({k_: v for k_, v in res.items() if k_ not in ("disagreements",)})
