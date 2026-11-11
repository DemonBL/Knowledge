"""ЛР10 · Результат 2: три стратегії розбиття на фрагменти.

1) fixed       — фіксоване вікно 800 символів з overlap 150 (межі вирівнюються по словах);
                 ігнорує структуру документа.
2) structural  — за заголовками: абзаци в межах одного розділу зливаються до ~1000 символів,
                 фрагмент ніколи не перетинає межу розділу; до тексту для embeddings додається
                 «Назва документа. Розділ.».
3) semantic    — за змістом: речення розділу групуються, поки косинусна схожість сусідніх речень
                 не впаде нижче 25-го перцентиля для документа (або розмір > 1200 символів).
Усі фрагменти мають однакові метадані: doc_id, title, section, type, date, sensitivity, source_url.
"""
import re

META = ("doc_id", "title", "type", "date", "sensitivity", "source_url")


def _base(doc, section, text, n, strategy):
    c = {k: doc[k] for k in META}
    c.update({"chunk_id": f"{doc['doc_id']}:{strategy[0]}{n:03d}", "section": section,
              "strategy": strategy, "text": text,
              "embed_text": text if strategy == "fixed" else f"{doc['title']}. {section}. {text}"})
    return c


def chunk_fixed(doc, size=800, overlap=150):
    spans, full = [], ""
    for name, paras in doc["sections"]:
        for p in paras:
            spans.append((len(full), name))
            full += p + "\n"
    out, start, n = [], 0, 0
    while start < len(full):
        end = min(len(full), start + size)
        if end < len(full):
            sp = full.rfind(" ", start + size - 120, end)
            end = sp if sp > start else end
        text = full[start:end].strip()
        sec = [name for pos, name in spans if pos <= start][-1]
        if text:
            out.append(_base(doc, sec, text, n, "fixed"))
            n += 1
        if end >= len(full):
            break
        nxt = end - overlap
        sp = full.find(" ", nxt)
        start = sp + 1 if 0 < sp < end else nxt
    return out


def chunk_structural(doc, max_chars=1000):
    out, n = [], 0
    for name, paras in doc["sections"]:
        buf = ""
        for p in paras:
            if buf and len(buf) + len(p) + 1 > max_chars:
                out.append(_base(doc, name, buf, n, "structural")); n += 1
                buf = ""
            if len(p) > max_chars * 1.6:  # дуже довгий абзац — ріжемо по реченнях
                for piece in _split_long(p, max_chars):
                    out.append(_base(doc, name, piece, n, "structural")); n += 1
                continue
            buf = (buf + "\n" + p).strip()
        if buf:
            out.append(_base(doc, name, buf, n, "structural")); n += 1
    return out


SENT = re.compile(r"(?<=[.!?…])\s+(?=[А-ЯІЇЄҐA-Z«\"(0-9])")


def sentences(text):
    return [s.strip() for s in SENT.split(text) if s.strip()]


def _split_long(p, max_chars):
    pieces, buf = [], ""
    for s in sentences(p):
        if buf and len(buf) + len(s) > max_chars:
            pieces.append(buf); buf = ""
        buf = (buf + " " + s).strip()
    if buf:
        pieces.append(buf)
    return pieces


def chunk_semantic(doc, embed, max_chars=1200, min_chars=250, pct=25):
    """embed(list[str]) -> np.ndarray нормалізованих векторів."""
    import numpy as np
    out, n = [], 0
    per_sec = [(name, sentences(" ".join(paras))) for name, paras in doc["sections"]]
    allsent = [s for _, ss in per_sec for s in ss]
    if not allsent:
        return out
    vec = embed(allsent)
    sims = [float(vec[i] @ vec[i + 1]) for i in range(len(allsent) - 1)]
    thr = float(np.percentile(sims, pct)) if sims else 0.0
    i = 0
    for name, ss in per_sec:
        buf = ""
        for j, s in enumerate(ss):
            gi = i + j
            if buf:
                breakpoint_ = gi > 0 and sims[gi - 1] < thr and len(buf) >= min_chars
                if breakpoint_ or len(buf) + len(s) > max_chars:
                    out.append(_base(doc, name, buf, n, "semantic")); n += 1
                    buf = ""
            buf = (buf + " " + s).strip()
        if buf:
            out.append(_base(doc, name, buf, n, "semantic")); n += 1
        i += len(ss)
    return out
