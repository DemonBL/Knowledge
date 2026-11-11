"""ЛР16 · пояснення рекомендацій зі шляху графа + автоматична перевірка.

1) template(path) — детерміноване пояснення, побудоване лише з вузлів шляху;
2) paraphrase(path) — LLM (qwen2.5:7b, локально) ЛИШЕ перефразовує шаблон; у підказці — дозволені сутності шляху;
3) check(text, path) — пояснення коректне, якщо всі згадані в ньому сутності (назви з реєстру сутностей, id графа,
   id фрагментів, назви документів, цитати «…») належать шляху, і згадано хоча б один проміжний вузол.
  python reco/explain.py --llm   (на ПК: Ollama)  → results/explanations.json
  python reco/explain.py         (без LLM: лише шаблони і перевірка)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

import data_gen as DG
import items as IT
import models as M

LAB = IT.LAB


def node_label(n, ctx):
    if n.startswith("I:"):
        it = ctx.by_id[n[2:]]
        return f"«{it['title']}» (розділ «{it['section']}»)"
    return ctx.labels.get(n, n[2:])


def path_entities(path, ctx):
    """Множина «дозволених» згадок: мітки вузлів, назви документів, розділи, id."""
    ok = set()
    for n in path:
        if n.startswith("I:"):
            it = ctx.by_id[n[2:]]
            ok |= {it["title"].lower(), it["section"].lower(), it["id"].lower(), it["doc"].lower()}
        else:
            lab = ctx.labels.get(n, n[2:])
            ok |= {lab.lower(), n[2:].lower()}
            m = re.match(r"(\S+) «(.+)»", lab)
            if m:
                ok |= {m.group(1).lower(), m.group(2).lower()}
    return ok


def template(path, ctx):
    rec, seen = ctx.by_id[path[-1][2:]], ctx.by_id[path[0][2:]]
    head = f"Рекомендуємо {node_label(path[-1], ctx)}, бо ви переглядали {node_label(path[0], ctx)}"
    if len(path) == 2:
        return head + ", а це сусідній розділ того самого документа."
    mid = path[1]
    if mid.startswith("D:"):
        return head + f", а обидва фрагменти — з документа «{ctx.labels[mid]}»."
    if len(path) == 3:
        return head + f", і обидва фрагменти згадують {node_label(mid, ctx)}."
    return head + f": він згадує {node_label(path[1], ctx)}, що в графі розслідувань пов'язане з {node_label(path[2], ctx)}, яке згадано в рекомендованому фрагменті."


GAZ = None


def mentions(text, ctx):
    """Сутності, згадані в тексті пояснення: назви з реєстру, id графа/фрагментів, цитати «…»."""
    global GAZ
    if GAZ is None:
        GAZ = IT.entity_gazetteer()
        GAZ = {eid: [IT._stem_pattern(n) for n in g["names"][:4]] for eid, g in GAZ.items()}
    found = set()
    for eid, ps in GAZ.items():
        if any(p.search(text) for p in ps):
            found.add(("E", eid))
    for x in re.findall(r"\b(?:CLM|NAR|ACC|RULE|OFF|FCH|VRD|PUB)-\d+\b", text):
        found.add(("G", x))
    for x in re.findall(r"\b(?:W\d\d|INT-[A-Z0-9-]+):s\d{3}\b", text):
        found.add(("I", x))
    for x in re.findall(r"«([^«»]{3,120})»", text):
        found.add(("Q", x))
    return found


def _norm(t):
    """Основи слів (перші 5 літер): «Дезінформацією щодо пандемії» ≈ «Дезінформація щодо пандемії»."""
    return " ".join(w[:5] for w in re.findall(r"\w+", t.lower()))


def check(text, path, ctx, stem=True):
    """stem=True (v2): цитати «…» порівнюються за основами слів, бо LLM відмінює назви документів;
    stem=False (v1, строга): точний збіг підрядка — давала хибні відмови на відмінкових формах."""
    allowed_nodes = set(path)
    ok_strings = path_entities(path, ctx)
    ok_norm = {_norm(x) for x in ok_strings}
    bad = []
    for kind, val in mentions(text, ctx):
        if kind == "E" and f"E:{val}" not in allowed_nodes:
            # сутність, яка є частиною назви документа/розділу шляху, допустима
            if not any(p.search(s) for p in GAZ[val] for s in ok_strings):
                bad.append(f"сутність поза шляхом: {ctx.labels.get('E:' + val, val)}")
        elif kind == "G" and f"G:{val}" not in allowed_nodes and val.lower() not in " ".join(ok_strings):
            bad.append(f"id поза шляхом: {val}")
        elif kind == "I" and f"I:{val}" not in allowed_nodes:
            bad.append(f"фрагмент поза шляхом: {val}")
        elif kind == "Q" and not (any(val.lower() in s or s in val.lower() for s in ok_strings)
                                  or (stem and any(_norm(val) and (_norm(val) in s2 or s2 in _norm(val)) for s2 in ok_norm if s2))):
            bad.append(f"цитата поза шляхом: «{val}»")
    mids = path[1:-1] or path[:1]
    tl, tn = text.lower(), _norm(text)
    has_link = any(any(s and (s in tl or (stem and _norm(s) and _norm(s) in tn)) for s in path_entities([m], ctx)) for m in mids)
    if not has_link:
        bad.append("не згадано жодного проміжного вузла шляху")
    return not bad, bad


PROMPT = """Перефразуй пояснення рекомендації природною українською мовою, 1–2 речення, звертаючись до аналітика на «ви».
Використовуй ЛИШЕ ці сутності й назви (без нових фактів, чисел, організацій, дат): {ents}.
Пояснення: {tpl}
Відповідь — лише перефразоване пояснення."""


def paraphrase(llm, tpl, path, ctx):
    ents = "; ".join(node_label(n, ctx) for n in path)
    r = llm.chat([{"role": "user", "content": PROMPT.format(ents=ents, tpl=tpl)}], max_tokens=160, task="explain_paraphrase")
    return r["text"].strip(), r


def sample_recs(n_users=10, k=3, seed=16, emb="lsa"):
    users, rows = DG.generate(seed)
    tr = [r for r in rows if r["ts"] < DG.T_TEST.isoformat()]
    ctx = M.Context(IT.load_items(), tr, DG.T_TEST, emb=emb)
    out = []
    role = {u["user_id"]: u["role"] for u in users}
    for u in sorted(ctx.hist)[:: max(1, len(ctx.hist) // n_users)][:n_users]:
        ranked, paths = M.hybrid_rec(ctx, u, role[u], k=k, mode="rrf")
        for i, _ in ranked:
            if i in paths:
                out.append(dict(user=u, role=role[u], item=i, path=paths[i]))
    return out, ctx


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm", action="store_true")
    ap.add_argument("--emb", default="lsa")
    ap.add_argument("--recheck", action="store_true", help="перевірити збережені тексти LLM строгою (v1) і основовою (v2) перевіркою без нових викликів")
    a = ap.parse_args()
    if a.recheck:
        return recheck(a.emb)
    recs, ctx = sample_recs(emb=a.emb)
    llm = None
    if a.llm:
        sys.path.insert(0, str(IT.HUB / "lab15" / "agent"))
        from llm import OllamaLLM
        llm = OllamaLLM(model="qwen2.5:7b", log_name="../../lab16/llm_log/explain_llm.jsonl", temperature=0.0, seed=42,
                        prompt_version="explain_v1")
    rows = []
    for r in recs:
        tpl = template(r["path"], ctx)
        ok_t, bad_t = check(tpl, r["path"], ctx)
        row = dict(r, path_labels=[node_label(n, ctx) for n in r["path"]], template=tpl, template_ok=ok_t, template_problems=bad_t)
        if llm:
            txt, raw = paraphrase(llm, tpl, r["path"], ctx)
            ok, bad = check(txt, r["path"], ctx)
            row.update(llm_text=txt, llm_ok=ok, llm_problems=bad, llm_latency_s=raw["latency_s"])
        rows.append(row)
        print(r["user"], r["item"], "tpl", ok_t, "llm", row.get("llm_ok"), "|", (row.get("llm_text") or tpl)[:120])
    summ = {"n": len(rows), "template_correct": sum(r["template_ok"] for r in rows) / len(rows)}
    if llm:
        summ["llm_correct"] = sum(r["llm_ok"] for r in rows) / len(rows)
        summ["llm_model"] = llm.model
    (LAB / "results").mkdir(exist_ok=True)
    (LAB / "results" / "explanations.json").write_text(json.dumps({"summary": summ, "rows": rows}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(summ)


def recheck(emb):
    p = LAB / "results" / "explanations.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    _, ctx = sample_recs(emb=emb)
    for r in d["rows"]:
        for key, txt in (("template", r["template"]), ("llm", r.get("llm_text"))):
            if txt is None:
                continue
            ok1, bad1 = check(txt, r["path"], ctx, stem=False)
            ok2, bad2 = check(txt, r["path"], ctx, stem=True)
            r[f"{key}_ok_strict"], r[f"{key}_ok"], r[f"{key}_problems"] = ok1, ok2, bad2
    rows = d["rows"]
    d["summary"].update(template_correct=sum(r["template_ok"] for r in rows) / len(rows),
                        template_correct_strict=sum(r["template_ok_strict"] for r in rows) / len(rows))
    if any("llm_text" in r for r in rows):
        d["summary"].update(llm_correct=sum(r["llm_ok"] for r in rows) / len(rows),
                            llm_correct_strict=sum(r["llm_ok_strict"] for r in rows) / len(rows))
    d["summary"]["checker"] = "v2: цитати за основами слів (v1 strict — точний підрядок)"
    # негативний контроль: у кожне пояснення LLM вставляємо одну сторонню сутність або назву документа поза шляхом
    import random
    rnd = random.Random(16)
    ents = [(k, v) for k, v in ctx.labels.items() if k.startswith("E:") and len(v) >= 5]
    titles = sorted({it["title"] for it in ctx.items})
    caught, total = 0, 0
    for r in rows:
        base = r.get("llm_text") or r["template"]
        on_path = set(r["path"])
        for kind in ("entity", "title"):
            if kind == "entity":
                k, lab = rnd.choice([e for e in ents if e[0] not in on_path])
                bad_txt = base + f" Також обидва фрагменти згадують {lab}."
            else:
                t = rnd.choice([t for t in titles if all(t.lower() not in x for x in path_entities(r["path"], ctx))])
                bad_txt = base + f" Див. також «{t}»."
            ok, _ = check(bad_txt, r["path"], ctx, stem=True)
            caught += (not ok)
            total += 1
    d["summary"]["negative_control"] = {"injected": total, "caught": caught, "detection_rate": caught / total}
    p.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    print(d["summary"])
    for r in rows:
        if r.get("llm_text") and not r["llm_ok"]:
            print("FAIL", r["llm_problems"], "|", r["llm_text"][:150])


if __name__ == "__main__":
    main()
