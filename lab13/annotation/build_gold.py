"""ЛР13 · збирання корпусу (data/docs/*.txt, data/corpus.jsonl) і золотого набору (data/gold.jsonl) зі специфікації gold_spec.py.
Перевіряє: кожна поверхнева форма є в тексті, кожна цитата-доказ — дослівний фрагмент, голова/хвіст відношення — розмічені сутності."""
import json, re, sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "annotation"))
from gold_spec import DOCS, NAR_DOCS, nar_gold  # noqa: E402

SRC = {d["doc_id"]: d for d in map(json.loads, open(ROOT / "data" / "lab10_docs.jsonl", encoding="utf-8"))}
SOURCE_TYPE = {"encyclopedia": "Вікіпедія (uk), CC BY-SA 4.0", "incident_report": "аналітичний звіт групи моніторингу (синтетичний, ЛР 10)",
               "regulation": "регламент перевірки (синтетичний, ЛР 10)", "rulebook": "каталог правил R1–R4 (ЛР 7, ЛР 10)", "sample": "зразок публікації (синтетичний, ЛР 10)"}


def excerpt(doc_id, prefixes=None, n_claims=None):
    d = SRC[doc_id]
    out, last_sec = [f"# {d['title']}"], None
    for sec, paras in d["sections"]:
        for p in paras:
            take = any(p.startswith(x) for x in prefixes) if prefixes else (
                sec == "Загальна характеристика" and p is paras[0]) or (sec == "Твердження та стан перевірки" and paras.index(p) < n_claims)
            if take:
                if sec != last_sec: out.append(f"## {sec}"); last_sec = sec
                out.append(p)
    return "\n\n".join(out)


def spans(text, surface):
    return [(m.start(), m.end()) for m in re.finditer(re.escape(surface), text)]


docs_out, gold_out, claims = [], [], []
problems = []
specs = {**{k: v for k, v in DOCS.items()}, **{k: dict(split=s, n=n) for k, (s, n) in NAR_DOCS.items()}}
for doc_id in sorted(specs, key=lambda x: (not x.startswith("W"), x)):
    sp = specs[doc_id]
    if doc_id in NAR_DOCS:
        text = excerpt(doc_id, n_claims=sp["n"])
        ents, rels = nar_gold(text)
        pseud = dict((m.group(2), m.group(1)) for m in re.finditer(r"від (ACC-\d+) \((Анонімний Telegram-канал #\d)\)", text))
        ents = [(s, t, n if n else pseud[s]) for s, t, n in ents]
    else:
        text = excerpt(doc_id, prefixes=sp["paras"])
        ents, rels = sp["ents"], sp["rels"]
        for p in sp["paras"]:
            if p not in text: problems.append(f"{doc_id}: абзац '{p}' не знайдено")
    (ROOT / "data" / "docs" / f"{doc_id}.txt").write_text(text, encoding="utf-8")
    src = SRC[doc_id]
    stype = src["type"] if src["type"] in SOURCE_TYPE else ("sample" if "SAMPLE" in doc_id else src["type"])
    docs_out.append(dict(doc_id=doc_id, title=src["title"], source_type=stype, source=SOURCE_TYPE.get(stype, stype), url=src["source_url"],
                         license=src["license"], sensitivity=src["sensitivity"], split=sp["split"], chars=len(text), text=text))
    # сутності: усі появи поверхневих форм; перекриття — довша форма
    ment = []
    for s, t, n in ents:
        sp_ = spans(text, s)
        if not sp_: problems.append(f"{doc_id}: сутність '{s}' не знайдено")
        ment += [dict(start=a, end=b, text=s, type=t, norm=n) for a, b in sp_]
    ment.sort(key=lambda m: (m["start"], -(m["end"] - m["start"])))
    kept, last_end = [], -1
    for m in ment:
        if m["start"] >= last_end: kept.append(m); last_end = m["end"]
    norms = {(m["norm"], m["type"]) for m in kept}
    nset = {m["norm"] for m in kept}
    rel_out = []
    for i, (h, r, t, ev) in enumerate(rels, 1):
        ev_sp = spans(text, ev)
        if not ev_sp: problems.append(f"{doc_id}: цитата не знайдена: '{ev[:50]}'")
        for x in (h, t):
            if x not in nset: problems.append(f"{doc_id}: '{x}' відношення {r} не серед сутностей")
        cid = f"{doc_id}:R{i:02d}"
        a, b = ev_sp[0] if ev_sp else (-1, -1)
        rec = dict(id=cid, doc_id=doc_id, head=h, relation=r, tail=t, evidence=ev, ev_start=a, ev_end=b, split=sp["split"])
        rel_out.append(rec); claims.append(rec)
    gold_out.append(dict(doc_id=doc_id, split=sp["split"], source_type=stype, entities=kept, relations=rel_out))

with open(ROOT / "data" / "corpus.jsonl", "w", encoding="utf-8") as f:
    for d in docs_out: f.write(json.dumps(d, ensure_ascii=False) + "\n")
with open(ROOT / "data" / "gold.jsonl", "w", encoding="utf-8") as f:
    for g in gold_out: f.write(json.dumps(g, ensure_ascii=False) + "\n")
st = dict(docs=len(gold_out), by_split=Counter(g["split"] for g in gold_out), by_source=Counter(g["source_type"] for g in gold_out),
          entity_mentions=sum(len(g["entities"]) for g in gold_out), unique_entities=sum(len({(m["norm"], m["type"]) for m in g["entities"]}) for g in gold_out),
          relations=len(claims), rel_by_split=Counter(c["split"] for c in claims), rel_types=Counter(c["relation"] for c in claims),
          ent_types=Counter(m["type"] for g in gold_out for m in g["entities"]), chars=sum(d["chars"] for d in docs_out))
(ROOT / "results" / "gold_stats.json").write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")
print(json.dumps(st, ensure_ascii=False, indent=1))
print("ПРОБЛЕМИ:", *problems, sep="\n  ") if problems else print("перевірки пройдено")
