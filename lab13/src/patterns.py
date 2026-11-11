"""ЛР13 · пошук патернів: асоціативні правила (Apriori) на транзакціях «абзац → множина нормалізованих сутностей».
Корпус — усі 36 документів ЛР 10 (не лише фрагменти). Сутності — методом А (словники + регулярні вирази), нормалізовані normalize.canon.
Для кожного правила: support, confidence, lift; перевірка випадковості (точний тест Фішера, перестановковий тест),
стабільності (бутстреп за документами, 1000 вибірок) і розбиття «Вікіпедія / внутрішні документи».
Вихід: results/patterns.json"""
import json, random, re, sys
from collections import Counter
from pathlib import Path
import pandas as pd
from mlxtend.frequent_patterns import apriori, association_rules
from mlxtend.preprocessing import TransactionEncoder
from scipy.stats import fisher_exact

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from extract_rules import find_entities, nlp  # noqa: E402
from normalize import canon, KB  # noqa: E402

random.seed(13)
docs = [json.loads(l) for l in open(ROOT / "data" / "lab10_docs.jsonl", encoding="utf-8")]
DISPLAY = {}
tx, tx_doc = [], []
for d in docs:
    for sec, paras in d["sections"]:
        for p in paras:
            if len(p) < 60: continue
            ents = find_entities(nlp()(p), p)
            items = set()
            for e in ents:
                if e["type"] in ("PHENOMENON", "PLATFORM", "METHOD") or (e["type"] == "ORG" and e["src"] == "lexicon"):
                    k = canon(e["text"], e["type"])
                    DISPLAY.setdefault(k, Counter())[e["text"]] += 1
                    items.add(k)
            if items: tx.append(sorted(items)); tx_doc.append(d["doc_id"])
name = {k: next((c for c in KB if canon(c, KB[c]["type"]) == k), v.most_common(1)[0][0]) for k, v in DISPLAY.items()}
tx_named = [[name[i] for i in t] for t in tx]
N = len(tx_named)
te = TransactionEncoder(); X = pd.DataFrame(te.fit_transform(tx_named), columns=te.columns_)
fi = apriori(X, min_support=0.012, use_colnames=True)
rules = association_rules(fi, metric="lift", min_threshold=1.2)
rules = rules[(rules.confidence >= 0.25) & (rules.antecedents.apply(len) == 1) & (rules.consequents.apply(len) == 1)]
rules = rules.sort_values(["lift", "support"], ascending=False)


def contingency(a, c, idx=None):
    rows = range(N) if idx is None else idx
    n11 = sum(1 for i in rows if X.at[i, a] and X.at[i, c]); n10 = sum(1 for i in rows if X.at[i, a] and not X.at[i, c])
    n01 = sum(1 for i in rows if not X.at[i, a] and X.at[i, c]); n00 = len(list(rows)) - n11 - n10 - n01
    return n11, n10, n01, n00


def metrics(a, c, idx):
    n11, n10, n01, n00 = contingency(a, c, idx); n = n11 + n10 + n01 + n00
    sa, sc = (n11 + n10) / n, (n11 + n01) / n
    return dict(support=n11 / n, confidence=n11 / (n11 + n10) if n11 + n10 else 0, lift=(n11 / n) / (sa * sc) if sa * sc else 0, n=n)


doc_ids = sorted(set(tx_doc)); by_doc = {d: [i for i, x in enumerate(tx_doc) if x == d] for d in doc_ids}
wiki_idx = [i for i, d in enumerate(tx_doc) if d.startswith("W")]; int_idx = [i for i, d in enumerate(tx_doc) if not d.startswith("W")]
out = []
for _, r in rules.head(12).iterrows():
    a, c = next(iter(r.antecedents)), next(iter(r.consequents))
    n11, n10, n01, n00 = contingency(a, c)
    _, p_fisher = fisher_exact([[n11, n10], [n01, n00]], alternative="greater")
    col_c = X[c].values.copy(); perm_ge = 0
    for _ in range(1000):                                         # перестановковий тест: перемішуємо наслідок між абзацами
        random.shuffle(col_c)
        perm_ge += int(((X[a].values & col_c).sum()) >= n11)
    boot = []
    for _ in range(1000):                                         # бутстреп за документами (абзаци одного документа залежні)
        idx = [i for d in random.choices(doc_ids, k=len(doc_ids)) for i in by_doc[d]]
        boot.append(metrics(a, c, idx)["lift"])
    boot.sort()
    # частка документів, у яких зустрічаються обидва елементи (чи не «один документ-генератор»)
    docs_both = sorted({tx_doc[i] for i in range(N) if X.at[i, a] and X.at[i, c]})
    out.append(dict(antecedent=a, consequent=c, support=round(r.support, 4), confidence=round(r.confidence, 3), lift=round(r.lift, 2),
                    count=n11, p_fisher=float(f"{p_fisher:.2e}"), p_perm=round((perm_ge + 1) / 1001, 4),
                    lift_ci95=[round(boot[25], 2), round(boot[974], 2)], share_boot_lift_gt1=round(sum(b > 1 for b in boot) / 1000, 3),
                    wiki=metrics(a, c, wiki_idx), internal=metrics(a, c, int_idx) if int_idx else None, docs_with_both=docs_both))
res = dict(transactions=N, docs=len(doc_ids), items=len(te.columns_), min_support=0.012, min_confidence=0.25, min_lift=1.2,
           top_items=Counter(i for t in tx_named for i in t).most_common(15), rules=out)
(ROOT / "results" / "patterns.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
print("transactions", N, "items", len(te.columns_), "rules", len(rules))
for o in out:
    print(f"{o['antecedent']:28} → {o['consequent']:24} s={o['support']:.3f} c={o['confidence']:.2f} lift={o['lift']:.2f} n={o['count']} "
          f"pF={o['p_fisher']:.1e} CI={o['lift_ci95']} docs={len(o['docs_with_both'])}")

# ---------------- набір 2: твердження з усіх звітів INT-NAR (витяг методом А за шаблоном звіту)
CITY = {"Києв": "Київ", "Одес": "Одеса", "Львов": "Львів", "Львів": "Львів", "Запоріж": "Запоріжжя", "Миколає": "Миколаїв", "Дніпр": "Дніпро", "Харков": "Харків", "Харків": "Харків"}
ctx, cdoc = [], []
for d in docs:
    if not d["doc_id"].startswith("INT-NAR"): continue
    nar = d["doc_id"].replace("INT-", "")
    for sec, paras in d["sections"]:
        for p in paras:
            m = re.match(r"(CLM-\d\d): «(.+?)»\. Пріоритет — (\w+); (.+)", p)
            if not m: continue
            it = {f"наратив={nar}", f"пріоритет={m.group(3)}"}
            v = re.search(r"вердикт VRD-\d+: «([^»]+)»", p); it.add(f"вердикт={v.group(1)}" if v else "вердикт=не завершено")
            o = re.search(r"Спростовано офіційним джерелом (.+?) \(", p)
            if o: it.add(f"спростовує={o.group(1)}")
            a = re.search(r"від (ACC-\d+)", p)
            if a: it.add(f"першоджерело={a.group(1)}")
            c = next((v_ for k, v_ in CITY.items() if k in m.group(2)), None)
            if c: it.add(f"місто={c}")
            ctx.append(sorted(it)); cdoc.append(nar)
te2 = TransactionEncoder(); X2 = pd.DataFrame(te2.fit_transform(ctx), columns=te2.columns_)
r2 = association_rules(apriori(X2, min_support=0.1, use_colnames=True), metric="lift", min_threshold=1.2)
r2 = r2[(r2.confidence >= 0.6) & (r2.antecedents.apply(len) == 1) & (r2.consequents.apply(len) == 1)].sort_values(["lift", "support"], ascending=False)
N2 = len(ctx); out2 = []
for _, r in r2.iterrows():
    a, c = next(iter(r.antecedents)), next(iter(r.consequents))
    n11 = int((X2[a] & X2[c]).sum()); n10 = int((X2[a] & ~X2[c]).sum()); n01 = int((~X2[a] & X2[c]).sum()); n00 = N2 - n11 - n10 - n01
    _, pf = fisher_exact([[n11, n10], [n01, n00]], alternative="greater")
    cc = X2[c].values.copy(); ge = 0
    for _ in range(1000):
        random.shuffle(cc); ge += int((X2[a].values & cc).sum() >= n11)
    out2.append(dict(antecedent=a, consequent=c, support=round(r.support, 3), confidence=round(r.confidence, 3), lift=round(r.lift, 2), count=n11,
                     p_fisher=float(f"{pf:.2e}"), p_perm=round((ge + 1) / 1001, 4), narratives=sorted({cdoc[i] for i in range(N2) if X2.at[i, a] and X2.at[i, c]})))
res["claims_set"] = dict(transactions=N2, items=len(te2.columns_), min_support=0.1, min_confidence=0.6, rules=out2[:15])
(ROOT / "results" / "patterns.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
print("claims transactions", N2, "rules", len(out2))
for o in out2[:15]:
    print(f"{o['antecedent']:38} → {o['consequent']:34} s={o['support']:.2f} c={o['confidence']:.2f} lift={o['lift']:.2f} n={o['count']} pF={o['p_fisher']:.1e} pP={o['p_perm']}")
