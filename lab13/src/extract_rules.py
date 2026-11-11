"""ЛР13 · Метод А: правила + spaCy (uk_core_news_sm).
Сутності: spaCy NER (PER/ORG/LOC) + словники типів (лемми) + регулярні вирази для кодів і дат.
Відношення: тригерні шаблони в межах речення + структурні правила (заголовок «Види X», шаблон звіту NAR).
Запуск: python src/extract_rules.py --split dev|test|all   → results/rules_<split>.jsonl"""
import argparse, json, re, sys, time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from normalize import lemma_key  # noqa: E402
from schema import RELATIONS  # noqa: E402

VERSION = "rules-v5.1"
# Словники укладено ДО запуску на test: (1) назви тем корпусу ЛР 10 і таксономії ЛР 4/12, (2) сутності попередніх ЛР (ЛР 9: організації,
# офіційні джерела, платформи), (3) терміни dev-документів. Терміни, що трапляються лише в test, свідомо не додавалися.
LEX = {
 "PHENOMENON": ["дезінформація", "дезінформування", "фейк", "фейки", "фейкові новини", "фейк-ньюз", "дипфейк", "діпфейк", "пропаганда", "клікбейт",
                "фішинг", "тролінг", "бот", "чат-бот", "соціальний бот", "ботоферма", "теорія змови", "маніпуляція", "соціальна інженерія", "чутки",
                "інформаційна війна", "гібридна війна", "психологічна війна", "цензура", "постправда", "неправдива інформація",
                # dev
                "технічні боти", "бойові боти", "зливні боти", "гіперболізовані боти", "упереджене викладення фактів", "дезінформування від зворотного",
                "термінологічне «мінування»"],
 "METHOD": ["аналіз EXIF", "Exif", "EXIF", "реверсивний пошук", "геолокація", "штучний інтелект", "фактчекінг", "WebService API"],
 "PLATFORM": ["Telegram", "Facebook", "Фейсбук", "Twitter", "Твіттер", "X", "YouTube", "Instagram", "TikTok", "Viber", "WhatsApp", "Whatsapp",
              "ВКонтакті", "Messenger", "eBay", "соціальні мережі", "соцмережі", "соціальні медіа", "месенджери"],
 "ORG": ["StopFake", "СтопФейк", "stopfake.org", "VoxCheck", "EUvsDisinfo", "Детектор медіа", "Центр протидії дезінформації", "РНБО", "МОЗ України",
         "ДСНС України", "Національна поліція України", "Офіційні канали міських рад", "Betfair"],
}
DATE_RE = re.compile(r"\b(?:\d{1,2}\s+)?(?:січ|лют|берез|квіт|трав|черв|лип|серп|верес|жовт|листоп|груд)\w*(?:\s*[-–]\s*\w+)?\s+\d{4}(?:\s+р(?:оку|оці|\.))?"
                     r"|\b(?:у|в|з)?\s?(?:кінці|початку)\s+\d{4}-х|\b\d{4}\s+(?:року|році|рр?\.)|\b\d+\s+годин\b|\bтрьох\s+діб\b", re.I)
CODE_RE = re.compile(r"\b(?:NAR|CLM|VRD|PUB|ACC|OFF|RULE)-\d+\b|Ф-\d\d|Анонімний Telegram-канал #\d")
TRIG = {  # тригери (початки лем), що вмикають відношення в реченні
 "FOUNDED_ON": ["створ", "запуст", "утвор", "засн", "з'яв"],
 "LEADS": ["керівни", "призначен", "засновн", "автор", "очол"],
 "COUNTERS": ["протиді", "спростув", "виявле", "бороть", "заборон", "захист", "припин", "контрол"],
 "COOPERATES_WITH": ["співпрац", "партнер", "підтримк"],
 "SPREADS": ["поширюва", "розповсюдж", "поширю"],
 "SPREADS_VIA": ["поширен", "працю", "з'яв", "знайти", "використовуєт"],
 "USES": ["використ", "базуєт", "застосов", "впровад"],
}
GENERIC = {lemma_key(x) for x in ["соціальні мережі", "соцмережі", "месенджери", "соціальні медіа"]}
NLP = None


def nlp():
    global NLP
    if NLP is None:
        import spacy
        NLP = spacy.load("uk_core_news_sm")
    return NLP


LEXKEY = {}
for t, words in LEX.items():
    for w in words: LEXKEY.setdefault(lemma_key(w, 99), t)
MAXN = max(len(k.split()) for k in LEXKEY)


BLOCK = []


def blocked(pos):
    return any(a <= pos < b for a, b in BLOCK)


def find_entities(doc, text):
    """Сутності; не розмічаються мітки вердиктів («фейк» після «вердикт VRD-xx:») і спеціалізації в дужках після «Аналітик Ф-xx»."""
    BLOCK[:] = [(m.start(), m.end()) for m in re.finditer(r"вердикт VRD-\d+: «[^»]+»|Аналітик Ф-\d\d \([^)]*\)", text)]
    ents = []
    for m in CODE_RE.finditer(text): ents.append((m.start(), m.end(), "CASE_ID", "regex"))
    for m in DATE_RE.finditer(text): ents.append((m.start(), m.end(), "DATE", "regex"))
    toks = [t for t in doc if not t.is_space]
    for i in range(len(toks)):
        for n in range(MAXN, 0, -1):
            span = toks[i:i + n]
            if len(span) < n: continue
            k = lemma_key(text[span[0].idx: span[-1].idx + len(span[-1].text)], 99)
            if k in LEXKEY and not blocked(span[0].idx):
                ents.append((span[0].idx, span[-1].idx + len(span[-1].text), LEXKEY[k], "lexicon")); break
    for e in doc.ents:
        lab = {"PER": "PERSON", "ORG": "ORG", "LOC": "LOCATION"}.get(e.label_)
        if not lab: continue
        k = lemma_key(e.text, 99)
        if k in LEXKEY: lab = LEXKEY[k]
        if any(not (e.end_char <= a or e.start_char >= b) for a, b in [(m.start(), m.end()) for m in CODE_RE.finditer(text)]): continue
        if blocked(e.start_char): continue
        ents.append((e.start_char, e.end_char, lab, "spacy-ner"))
    pr = {"regex": 0, "lexicon": 1, "spacy-ner": 2}
    ents.sort(key=lambda x: (x[0], -(x[1] - x[0]), pr[x[3]]))
    out, last = [], -1
    for s, e, t, src in ents:
        if s >= last:
            surf = text[s:e].strip(" .,;:(")
            if t == "PERSON" and len(surf.split()) == 1 and surf[0].islower(): continue
            out.append(dict(text=surf, type=t, start=s, end=s + len(surf), src=src)); last = e
    return out


def has(sent_lemmas, rel):
    return any(l.startswith(tr) for l in sent_lemmas for tr in TRIG[rel])


def ok_sig(rel, h, t):
    H, T, _ = RELATIONS[rel]
    return h["type"] in H and t["type"] in T and h["text"] != t["text"]


def extract(doc_id, text, title):
    doc = nlp()(text)
    ents = find_entities(doc, text)
    rels = []

    def add(h, rel, t, ev_s, ev_e, rule, conf):
        seg = text[ev_s:ev_e]                                       # цитата без рядків-заголовків (v5.1: лише формат provenance)
        if "\n" in seg and not seg.startswith("## Види") and not seg.startswith("## Методи"):
            pieces, pos = [], 0
            for part in seg.split("\n"):
                if part.strip() and not part.startswith("#"): pieces.append((ev_s + pos, ev_s + pos + len(part)))
                pos += len(part) + 1
            if pieces: ev_s, ev_e = max(pieces, key=lambda p: p[1] - p[0])
        ev_e = ev_s + len(text[ev_s:ev_e].rstrip())
        if ok_sig(rel, h, t):
            rels.append(dict(head=h["text"], head_type=h["type"], relation=rel, tail=t["text"], tail_type=t["type"],
                             evidence=text[ev_s:ev_e], ev_start=ev_s, ev_end=ev_e, rule=rule, confidence=conf))
    title_ent = next((e for e in ents if e["start"] < len(title) + 3 and e["type"] in ("ORG", "PLATFORM", "PHENOMENON", "METHOD")), None)
    # --- структурні правила
    nar = re.search(r"NAR-\d\d", text)
    if nar and "Звіт складено групою моніторингу" in text:
        N = dict(text=nar.group(), type="CASE_ID")
        for p in re.finditer(r"(CLM-\d\d): .+", text):
            para, ps = p.group(), p.start()
            C = dict(text=p.group(1), type="CASE_ID")
            add(C, "PART_OF", N, ps, ps + (para.find(". Пріоритет") if ". Пріоритет" in para else len(p.group(1))), "nar-template", 0.95)
            o = re.search(r"Спростовано офіційним джерелом (.+?) \(OFF-\d\d\)", para)
            if o: add(dict(text=o.group(1), type="ORG"), "REFUTES", C, ps + o.start(), ps + o.end(), "nar-template", 0.95)
            a = re.search(r"першоджерело: PUB-\d+ від (ACC-\d+)", para)
            if a: add(dict(text=a.group(1), type="CASE_ID"), "SPREADS", C, ps + a.start(), ps + a.end(), "nar-template", 0.9)
    for h in re.finditer(r"^## (?:Види|Методи|Типи|Різновиди) (.+)$", text, re.M):                    # заголовок «Види X» → абзаци-підтипи
        sec_end = text.find("\n## ", h.end()); sec_end = len(text) if sec_end < 0 else sec_end
        parent = next((e for e in ents if h.start() <= e["start"] < h.end() and e["type"] == "PHENOMENON"), None)
        if parent is None:
            parent = dict(text=re.sub(r"\s+", " ", h.group(1)).strip(), type="PHENOMENON")
        for e in ents:
            if h.end() < e["start"] < sec_end and e["type"] == "PHENOMENON" and text[e["start"] - 2:e["start"]] == "\n\n":
                add(e, "SUBTYPE_OF", parent, h.start(), h.end(), "section-header", 0.7)
    # --- речення
    for sent in doc.sents:
        s, e = sent.start_char, sent.end_char
        se = [x for x in ents if s <= x["start"] < e]
        lem = [t.lemma_.lower() for t in sent]
        st = text[s:e]
        def typ(*ts): return [x for x in se if x["type"] in ts]
        m = re.search(r"(?:— |є )(?:вид|один з різновидів|різновид)\w*", st)
        if m:
            left = [x for x in se if x["start"] < s + m.start() and x["type"] in ("PHENOMENON", "METHOD")]
            right = [x for x in se if x["start"] >= s + m.end() and x["type"] in ("PHENOMENON", "METHOD")]
            if left and right: add(left[0], "SUBTYPE_OF", right[0], s, e, "is-a", 0.8)
        if has(lem, "FOUNDED_ON"):
            coref = title_ent and title_ent["type"] == "ORG" and re.match(r"\s*(Сайт|Проєкт|Центр|Утворений)", st)
            heads = [title_ent] if coref else [x for x in typ("ORG", "PLATFORM") if lemma_key(x["text"]) not in GENERIC]
            for d in typ("DATE")[:1]:
                for h in heads[:1]: add(h, "FOUNDED_ON", d, s, e, "trigger", 0.6)
        m = re.search(r"робочий орган|є органом|підпорядковується", st)
        if m:
            right = [x for x in typ("ORG") if x["start"] > s + m.start()]
            left = [x for x in typ("ORG") if x["start"] < s + m.start()] or ([title_ent] if title_ent and title_ent["type"] == "ORG" else [])
            if left and right: add(left[0], "PART_OF", right[0], s, e, "trigger", 0.7)
        for m in re.finditer(r"(\S[^()]*?) \(в тому числі ([^)]+)\)", st):
            inner = [x for x in typ("ORG") if s + m.start(2) <= x["start"] < s + m.end(2)]
            outer = [x for x in typ("ORG") if s + m.start(1) <= x["start"] < s + m.end(1)]
            for i_ in inner:
                if outer: add(i_, "PART_OF", outer[-1], s, e, "в-тому-числі", 0.6)
        if has(lem, "LEADS"):
            orgs = typ("ORG", "PLATFORM") or ([title_ent] if title_ent and title_ent["type"] == "ORG" else [])
            trig = [m.start() for m in re.finditer(r"керівни|призначен|засновн|[Аа]втор|очол", st)]
            for p in typ("PERSON"):
                if orgs and any(abs((p["start"] - s) - t) < 45 for t in trig): add(p, "LEADS", min(orgs, key=lambda o: abs(o["start"] - p["start"])), s, e, "trigger", 0.6)
        if has(lem, "COUNTERS"):
            heads = typ("ORG", "PLATFORM", "METHOD") or ([title_ent] if title_ent and title_ent["type"] in ("ORG", "METHOD") else [])
            for t in typ("PHENOMENON"):
                for h in heads: add(h, "COUNTERS", t, s, e, "trigger", 0.5)
        if has(lem, "COOPERATES_WITH"):
            ents2 = typ("ORG", "PLATFORM")
            pivot = re.search(r"співпрац\w*|партнер\w*|підтримк\w*", st)
            left = [x for x in ents2 if x["start"] < s + pivot.start()] if pivot else []
            right = [x for x in ents2 if pivot and x["start"] >= s + pivot.start()]
            if not left and title_ent and title_ent["type"] == "ORG": left = [title_ent]
            for a_ in left:
                for b_ in right:
                    if lemma_key(a_["text"]) != lemma_key(b_["text"]): add(a_, "COOPERATES_WITH", b_, s, e, "trigger", 0.5)
            for m in re.finditer(r"\(разом з ([^)]+)\)", st):              # «співпрацювати з Y (разом з X)» → X–Y
                xs = [x for x in ents2 if s + m.start(1) <= x["start"] < s + m.end(1)]
                ys = [x for x in ents2 if x["start"] < s + m.start() and x not in left]
                for x_ in xs:
                    for y_ in ys[-1:]: add(x_, "COOPERATES_WITH", y_, s, e, "разом-з", 0.5)
        if has(lem, "SPREADS"):
            for t in typ("PHENOMENON"):
                for h in typ("ORG", "PERSON"): add(h, "SPREADS", t, s, e, "trigger", 0.5)
        if has(lem, "SPREADS_VIA") or re.search(r"\bна [A-Z]|у групах|у соц", st):
            hs = typ("PHENOMENON")
            if re.match(r"\s*Це ", st):                                         # «Це …» → підмет абзацу
                para_start = text.rfind("\n\n", 0, s) + 2
                first = next((x for x in ents if x["start"] >= para_start and x["type"] == "PHENOMENON"), None)
                hs = [first] if first else hs
            if title_ent and title_ent["type"] == "PHENOMENON":               # загальне «боти» → тема документа
                hs = [title_ent if lemma_key(x["text"], 99) in ("бот", "бот бот") and lemma_key("бот") in lemma_key(title_ent["text"]) else x for x in hs]
            for h in hs:
                for t in typ("PLATFORM"):
                    if t["start"] > h["start"]: add(h, "SPREADS_VIA", t, s, e, "trigger", 0.5)
        if has(lem, "USES"):
            m = re.search(r"[Вв]икорист\w*|базується на|застосов\w*|впровад\w*", st)
            if not m: continue
            left = [x for x in se if x["start"] < s + m.start() and x["type"] in ("ORG", "PLATFORM", "PHENOMENON", "METHOD")]
            left = [x for x in left if x["type"] in ("ORG", "PLATFORM")] or left
            right = [x for x in se if x["start"] > s + m.start() and x["type"] in ("METHOD",)]
            if left and right: add(left[-1], "USES", right[0], s, e, "trigger", 0.5)
    seen, uniq = set(), []
    for r in rels:
        k = (r["head"], r["relation"], r["tail"])
        if k not in seen: seen.add(k); uniq.append(r)
    return [{k: v for k, v in x.items() if k != "src"} | {"source": x["src"]} for x in ents], uniq


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--split", default="dev"); a = ap.parse_args()
    corpus = [d for d in map(json.loads, open(ROOT / "data" / "corpus.jsonl", encoding="utf-8")) if a.split == "all" or d["split"] == a.split]
    out = ROOT / "results" / f"rules_{a.split}.jsonl"
    with open(out, "w", encoding="utf-8") as f:
        for d in corpus:
            t0 = time.perf_counter()
            ents, rels = extract(d["doc_id"], d["text"], d["text"].split("\n")[0])
            ms = (time.perf_counter() - t0) * 1000
            f.write(json.dumps(dict(doc_id=d["doc_id"], method="A:rules+spaCy", model="uk_core_news_sm-3.8.0", version=VERSION,
                                    ts=datetime.now().isoformat(timespec="seconds"), entities=ents, relations=rels,
                                    cost=dict(latency_s=round(ms / 1000, 3), calls=0, prompt_tokens=0, completion_tokens=0)), ensure_ascii=False) + "\n")
    print("written", out, len(corpus), "docs")
