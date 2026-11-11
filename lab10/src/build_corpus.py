"""ЛР10 · Результат 1: збирання та очищення корпусу, метадані, sensitivity.

Джерела:
  1) Українська Вікіпедія (CC BY-SA 4.0) — статті про дезінформацію, фактчекінг, медіаграмотність
     тощо; завантажуються через MediaWiki API (prop=extracts, explaintext) — без HTML-навігації.
  2) Внутрішні документи kb_internal/*.md (складено на основі ЛР7–ЛР9; internal/restricted).
Очищення: вилучаються службові розділи (Примітки, Джерела, Посилання, Див. також, Література),
порожні рядки, дужки з транскрипціями, повтори пробілів; відкидаються абзаци < 60 символів.
Вихід: data/docs.jsonl (документи з розділами) і data/corpus.jsonl (фрагменти, стратегія «структурна»).
"""
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB / "src"))
DATA = LAB / "data"
DATA.mkdir(exist_ok=True)
API = "https://uk.wikipedia.org/w/api.php"
UA = {"User-Agent": "KMS-Lab10-StudentProject/1.0 (https://lnu.edu.ua; educational corpus, ~40 requests) python-urllib"}

TITLES = [
    "Дезінформація", "Фейкові новини", "Фактчекінг", "Пропаганда", "Медіаграмотність",
    "Інформаційна війна", "Діпфейк", "Постправда", "Теорія змови", "Клікбейт", "Фішинг",
    "Соціальна інженерія", "Маніпуляція свідомістю", "Інформаційна безпека", "Exif", "Метадані",
    "StopFake", "Гібридна війна", "Російська пропаганда", "Психологічна війна",
    "Інтернет-троль", "Бот (програма)", "Ехо-камера (медіа)", "Фільтрова бульбашка",
    "Центр протидії дезінформації", "Детектор медіа", "Свобода слова", "Цензура",
    "Ботоферма", "Пошук за зображенням", "Журналістика даних", "Чутки",
]
SEARCH_FALLBACK = ["дезінформація фейки", "фактчекінг перевірка фактів", "пропаганда інформаційна операція",
                   "медіаграмотність критичне мислення"]
SKIP_SECTIONS = re.compile(r"^(примітки|джерела|посилання|див\. також|література|виноски|"
                           r"зовнішні посилання|бібліографія|галерея)$", re.I)


def api(params):
    url = API + "?" + urllib.parse.urlencode({**params, "format": "json", "formatversion": 2,
                                              "maxlag": 5})
    for attempt in range(6):
        time.sleep(1.5)
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (429, 503) and attempt < 5:
                wait = int(e.headers.get("Retry-After") or 0) or 10 * (attempt + 1)
                print(f"  HTTP {e.code}, чекаю {wait} с", flush=True)
                time.sleep(wait)
                continue
            raise
        except (TimeoutError, urllib.error.URLError, ConnectionError, OSError) as e:
            if attempt < 5:
                print(f"  мережа: {e!r}, повтор", flush=True)
                time.sleep(5 * (attempt + 1))
                continue
            raise


CACHE = DATA / "wiki_cache"


def fetch(title):
    CACHE.mkdir(exist_ok=True)
    cf = CACHE / (re.sub(r"[^\w]+", "_", title) + ".json")
    if cf.exists():
        return json.loads(cf.read_text(encoding="utf-8")) or None
    d = _fetch(title)
    cf.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    return d


def _fetch(title):
    j = api({"action": "query", "prop": "extracts|info|revisions", "explaintext": 1,
             "exsectionformat": "wiki", "redirects": 1, "inprop": "url", "rvprop": "timestamp",
             "titles": title})
    p = j["query"]["pages"][0]
    if p.get("missing") or not p.get("extract"):
        return None
    return {"title": p["title"], "url": p["fullurl"], "date": p["revisions"][0]["timestamp"][:10],
            "text": p["extract"], "pageid": p["pageid"]}


def clean_sections(text):
    """Розбиває explaintext на (розділ, [абзаци]) і чистить шум."""
    secs, cur, buf = [], "Вступ", []
    for line in text.split("\n"):
        m = re.match(r"^(=+)\s*(.*?)\s*\1$", line.strip())
        if m:
            secs.append((cur, buf))
            cur, buf = m.group(2), []
            continue
        buf.append(line)
    secs.append((cur, buf))
    out = []
    skip_level = False
    for name, lines in secs:
        if SKIP_SECTIONS.match(name.strip()):
            continue
        paras = []
        for para in "\n".join(lines).split("\n"):
            p = re.sub(r"\s+", " ", para.replace("\u0301", "")).strip()
            p = re.sub(r"\s*\((?:англ|рос|лат|нім|фр)\.[^)]{0,80}\)", "", p)  # транскрипції
            if len(p) >= 60:
                paras.append(p)
        if paras:
            out.append((name, paras))
    return out


def parse_internal(path):
    raw = path.read_text(encoding="utf-8")
    m = re.match(r"---\n(.*?)\n---\n", raw, re.S)
    meta = dict(line.split(": ", 1) for line in m.group(1).splitlines())
    body = raw[m.end():]
    secs, cur, buf = [], meta["title"], []
    for line in body.split("\n"):
        h = re.match(r"^#{1,3}\s+(.*)", line)
        if h:
            if buf:
                secs.append((cur, buf))
            cur, buf = h.group(1).strip(), []
        elif line.strip():
            buf.append(re.sub(r"^- ", "", line.strip()))
    if buf:
        secs.append((cur, buf))
    return meta, [(n, [p for p in ps if len(p) >= 40]) for n, ps in secs if ps]


def main():
    import make_internal_docs  # noqa: F401  (генерує kb_internal/*.md із графа ЛР9)
    docs = []
    seen = set()
    log = []
    titles = list(TITLES)
    for t in titles:
        try:
            d = fetch(t)
        except Exception as e:  # noqa
            log.append(f"ERR {t}: {e}")
            continue
        time.sleep(0.3)
        if not d or d["pageid"] in seen:
            log.append(f"skip {t}")
            continue
        secs = clean_sections(d["text"])
        if sum(len(p) for _, p in secs) < 8:
            log.append(f"short {t}")
            continue
        seen.add(d["pageid"])
        docs.append({"doc_id": f"W{len(docs)+1:02d}", "title": d["title"], "type": "encyclopedia",
                     "date": d["date"], "sensitivity": "public", "source_url": d["url"],
                     "license": "CC BY-SA 4.0", "lang": "uk", "sections": secs})
        log.append(f"ok  {t} -> {d['title']} ({sum(len(p) for _, p in secs)} абзаців)")
        print(log[-1], flush=True)
    # добір через пошук, якщо статей менше 24
    for q in SEARCH_FALLBACK:
        if len(docs) >= 26:
            break
        try:
            res = api({"action": "query", "list": "search", "srsearch": q, "srlimit": 10})
        except Exception as e:  # noqa
            log.append(f"ERR search {q}: {e}")
            continue
        for hit in res["query"]["search"]:
            if len(docs) >= 26:
                break
            try:
                d = fetch(hit["title"])
            except Exception as e:  # noqa
                log.append(f"ERR {hit['title']}: {e}")
                continue
            if not d or d["pageid"] in seen:
                continue
            secs = clean_sections(d["text"])
            if sum(len(p) for _, p in secs) < 8:
                continue
            seen.add(d["pageid"])
            docs.append({"doc_id": f"W{len(docs)+1:02d}", "title": d["title"], "type": "encyclopedia",
                         "date": d["date"], "sensitivity": "public", "source_url": d["url"],
                         "license": "CC BY-SA 4.0", "lang": "uk", "sections": secs})
            log.append(f"ok  [search:{q}] {d['title']}")
    for p in sorted((LAB / "kb_internal").glob("*.md")):
        meta, secs = parse_internal(p)
        docs.append({"doc_id": meta["doc_id"], "title": meta["title"], "type": meta["type"],
                     "date": meta["date"], "sensitivity": meta["sensitivity"],
                     "source_url": f"kb_internal/{p.name}", "license": "внутрішній документ (навчальний)",
                     "lang": "uk", "sections": secs})
    with open(DATA / "docs.jsonl", "w", encoding="utf-8") as f:
        for d in docs:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    (LAB / "results").mkdir(exist_ok=True)
    (LAB / "results" / "corpus_log.txt").write_text("\n".join(log), encoding="utf-8")
    from chunking import chunk_structural
    chunks = [c for d in docs for c in chunk_structural(d)]
    with open(DATA / "corpus.jsonl", "w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    print(f"docs={len(docs)} (wiki={sum(d['type']=='encyclopedia' for d in docs)}), chunks={len(chunks)}")


if __name__ == "__main__":
    main()
