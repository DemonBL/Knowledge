"""ЛР16 · каталог об'єктів рекомендацій і граф знань для них.

Об'єкт рекомендації (item) — фрагмент корпусу Hub (очищений у ЛР14), 529 штук, з метаданими: документ, дата,
рівень доступу, статус чинності, «перевіреність». Граф: фрагмент —MENTIONS→ сутність (реєстр ЛР14 після ER + id
графа ЛР9), сутність —графові ребра ЛР9 (CLM→NAR, ACC→CLM…)→ сутність, фрагмент —IN_DOC→ документ.
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import date
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
HUB = LAB.parent
REF_DATE = date(2026, 11, 7)
ROLE_ACCESS = {"guest": {"public"}, "analyst": {"public", "internal"}, "admin": {"public", "internal", "restricted"}}
UNVERIFIED_DOCS = {"INT-SAMPLE-INJ"}          # зразок публікації для розбору (містить ін'єкцію) — не перевірене знання

# тематика документів — для генерації синтетичних взаємодій (data_gen.py) і холодного старту (вибір інтересів)
TOPICS = {
    "фактчекінг": ["W01", "W02", "W04", "W14", "W19"],
    "пропаганда": ["W03", "W05", "W15", "W16", "W25"],
    "боти й тролі": ["W17", "W18", "W22"],
    "фото й метадані": ["W06", "W12", "W13"],
    "кібербезпека": ["W09", "W10", "W11"],
    "свобода слова": ["W07", "W08", "W20", "W21", "W23", "W24"],
    "здоров'я": ["W26", "INT-NAR-03"],
    "наративи війни": ["INT-NAR-01", "INT-NAR-02", "INT-NAR-04", "INT-NAR-05", "INT-NAR-06"],
    "регламенти": ["INT-REG-2025", "INT-REG-2026", "INT-RULES", "INT-SAMPLE-INJ"],
}
DOC_TOPIC = {d: t for t, ds in TOPICS.items() for d in ds}


def load_items():
    ch = [json.loads(l) for l in open(HUB / "lab14" / "data" / "clean" / "corpus.jsonl", encoding="utf-8")]
    items = []
    for c in ch:
        items.append(dict(id=c["chunk_id"], doc=c["doc_id"], title=c["title"], section=c["section"], date=c["date"],
                          sensitivity=c["sensitivity"], status=c.get("status", "чинний"), text=c["text"], embed_text=c["embed_text"],
                          verified=c["doc_id"] not in UNVERIFIED_DOCS, topic=DOC_TOPIC.get(c["doc_id"], "інше")))
    return items


def entity_gazetteer():
    """Сутності з реєстру ЛР14 (після entity resolution): канонічний id → (мітка, тип, варіанти назв)."""
    reg = json.loads((HUB / "lab14" / "data" / "clean" / "entity_registry.json").read_text(encoding="utf-8"))
    out = {}
    for e in reg["entities"]:
        if e["type"] in ("CASE_ID",):
            continue
        names = {m["name"] for m in e["members"]} | {e["label"]}
        names = {n for n in names if len(n) >= 4 and not re.fullmatch(r"[\d\W]+", n)}
        if names:
            out[e["id"]] = dict(label=e["label"], type=e["type"], names=sorted(names, key=len, reverse=True))
    return out


ID_RE = re.compile(r"\b(CLM-\d{2}|NAR-\d{2}|ACC-\d{3}|RULE-\d|OFF-\d{2}|FCH-\d{2})\b")


def _stem_pattern(name):
    toks = [t for t in re.split(r"\s+", name.lower()) if t]
    parts = [re.escape(t[:max(4, len(t) - 2)]) + r"\w*" if len(t) > 5 and t.isalpha() else re.escape(t) for t in toks]
    return re.compile(r"(?<!\w)" + r"\W+".join(parts) + r"(?!\w)", re.I)


def build_graph(items, gaz=None):
    """Повертає adj: вузол → {сусід: тип ребра}. Вузли: 'I:<chunk>', 'E:<entity>', 'D:<doc>', 'G:<id графа ЛР9>'."""
    gaz = gaz or entity_gazetteer()
    pats = {eid: [_stem_pattern(n) for n in g["names"][:6]] for eid, g in gaz.items()}
    adj = defaultdict(dict)
    labels = {f"E:{k}": v["label"] for k, v in gaz.items()}

    def link(a, b, t):
        adj[a][b] = t
        adj[b][a] = t

    prev = None
    for it in items:
        i = "I:" + it["id"]
        link(i, "D:" + it["doc"], "IN_DOC")
        if prev and prev["doc"] == it["doc"]:                 # структура документа: сусідні розділи
            link(i, "I:" + prev["id"], "NEXT_SECTION")
        prev = it
        labels["D:" + it["doc"]] = it["title"]
        txt = it["text"]
        for eid, ps in pats.items():
            if any(p.search(txt) for p in ps):
                link(i, "E:" + eid, "MENTIONS")
        for gid in set(ID_RE.findall(txt)):
            link(i, "G:" + gid, "MENTIONS")
            labels.setdefault("G:" + gid, gid)
    # ребра графа знань ЛР9 (очищений у ЛР14) між згаданими id: твердження → наратив, акаунт → твердження тощо
    import csv
    gdir = HUB / "lab14" / "data" / "clean" / "graph"
    names = {}
    for f in gdir.glob("nodes_*.csv"):
        for r in csv.DictReader(open(f, encoding="utf-8")):
            names[r["id"]] = r.get("name") or r.get("text") or r["id"]
    for rel, (a_pre, b_pre) in {"PART_OF": ("CLM", "NAR"), "REFUTES": ("OFF", "CLM"), "ISSUED": ("FCH", "VRD")}.items():
        for r in csv.DictReader(open(gdir / f"rels_{rel}.csv", encoding="utf-8")):
            a, b = "G:" + r["start"], "G:" + r["end"]
            if a in adj or b in adj:
                link(a, b, rel)
                labels.setdefault(a, r["start"])
                labels.setdefault(b, r["end"])
    for k in list(labels):
        gid = k[2:]
        if k.startswith("G:") and gid in names:
            labels[k] = f"{gid} «{names[gid][:60]}»"
    return adj, labels


def allowed(it, role, fresh_days=None, require_verified=True, current_only=True):
    """Фільтри прав і якості: RBAC за роллю, лише перевірені, лише чинні, (опц.) свіжість."""
    if it["sensitivity"] not in ROLE_ACCESS.get(role, {"public"}):
        return False
    if require_verified and not it["verified"]:
        return False
    if current_only and it["status"] == "superseded":
        return False
    if fresh_days is not None and (REF_DATE - date.fromisoformat(it["date"])).days > fresh_days:
        return False
    return True


if __name__ == "__main__":
    import collections
    items = load_items()
    adj, labels = build_graph(items)
    deg = collections.Counter(n[:2] for n in adj)
    mentions = [sum(1 for v in adj["I:" + it["id"]] if v[:2] in ("E:", "G:")) for it in items]
    print(len(items), dict(deg), "фрагментів без сутностей:", sum(m == 0 for m in mentions), "сер. сутностей:", round(sum(mentions) / len(items), 2))
