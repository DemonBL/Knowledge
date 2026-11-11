"""ЛР13 · нормалізація та зв'язування сутностей (entity linking).

Ключ сутності:
  DATE     → ISO-подібна дата (2014-03-02, 2020-03, 2017, 1980s, PT12H); для відношень порівнюється рік;
  CASE_ID  → код у верхньому регістрі; псевдонім «Анонімний Telegram-канал #N» → ACC-код із контексту документа;
  інші     → лемми spaCy (uk_core_news_sm), кожна обрізана до 5 символів («стем»), після заміни синонімів зі словника KB.
Словник KB (data/kb_aliases.json) — канонічна назва → варіанти; укладено з таксономії/онтології (ЛР 4–8) і dev-документів."""
import json, re
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_nlp = None


def nlp():
    global _nlp
    if _nlp is None:
        import spacy
        _nlp = spacy.load("uk_core_news_sm", disable=["parser", "ner"])
    return _nlp


@lru_cache(maxsize=None)
def lemma_key(text, n=5):
    """Лемми через пробіл, кожна обрізана до n символів (n=5 — ключ зв'язування; n=99 — повні лемми для словників)."""
    t = re.sub(r"[«»\"'’()]", " ", text).replace("-", " ")
    toks = [x.lemma_.lower() for x in nlp()(t) if not (x.is_punct or x.is_space)]
    return " ".join(w[:n] for w in toks if w)


KB = json.loads((ROOT / "data" / "kb_aliases.json").read_text(encoding="utf-8"))
ALIAS = {}
for canon, info in KB.items():
    for v in [canon] + info["aliases"]:
        ALIAS[lemma_key(v)] = canon

MONTHS = {"січ": 1, "лют": 2, "берез": 3, "квіт": 4, "трав": 5, "черв": 6, "лип": 7, "серп": 8, "верес": 9, "жовт": 10, "листоп": 11, "груд": 12}


def norm_date(s):
    s0 = s.lower()
    if re.search(r"\d+\s*год", s0): return "PT" + re.search(r"\d+", s0).group() + "H"
    if "доб" in s0 or "діб" in s0: return "P3D" if "трьох" in s0 else "P?D"
    y = re.search(r"(1[5-9]\d\d|20\d\d)(-х)?", s0)
    if not y: return s0.strip()
    if y.group(2): return y.group(1) + "s"
    mon = next((v for k, v in MONTHS.items() if re.search(r"\b" + k, s0)), None)
    day = re.match(r"\s*(\d{1,2})\s", s0)
    if mon and day: return f"{y.group(1)}-{mon:02d}-{int(day.group(1)):02d}"
    if mon: return f"{y.group(1)}-{mon:02d}"
    return y.group(1)


def canon(text, etype, doc_text=""):
    """Канонічний ключ сутності для зв'язування й оцінювання."""
    if etype == "DATE":
        return norm_date(text)
    if etype == "CASE_ID":
        m = re.match(r"Анонімний Telegram-канал #(\d)", text)
        if m and doc_text:
            a = re.search(r"від (ACC-\d+) \(" + re.escape(text) + r"\)", doc_text)
            if a: return a.group(1)
        code = re.search(r"(ACC|CLM|NAR|VRD|PUB|OFF|RULE)-\d+|Ф-\d\d", text, re.I)
        return code.group().upper() if code else text.strip()
    k = lemma_key(text)
    return lemma_key(ALIAS.get(k, text)) if k in ALIAS else k


def rel_tail_key(key, etype):
    return key[:4] if etype == "DATE" and re.match(r"\d{4}", key) else key


def same_entity(a, b, etype):
    """Збіг ключів; для PERSON — допускається збіг за підмножиною токенів (прізвище без імені)."""
    if a == b: return True
    if etype == "PERSON":
        sa, sb = set(a.split()), set(b.split())
        return bool(sa) and bool(sb) and (sa <= sb or sb <= sa)
    return False
