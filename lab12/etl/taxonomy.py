"""ЛР12 · таксономія (гілки «Ознаки дезінформації» і «Методи перевірки» з ЛР 4–5) у SKOS з IRI.
Вихід: taxonomy/taxonomy.ttl — джерело для виміру dim_taxonomy."""
from pathlib import Path
from rdflib import Graph, Literal, Namespace, RDF, URIRef
from rdflib.namespace import SKOS, DCTERMS

ROOT = Path(__file__).resolve().parents[1]
NS = Namespace("http://www.lnu.edu.ua/ontologies/disinfo-analysis.owl#")

# (код, назва) → підкласи → листові поняття. Рівні 1–2 — з таксономії ЛР 4 / концептуальної карти ЛР 5,
# рівень 3 — конкретні ознаки та методи з тієї самої таксономії (колонка «приклади»).
TAXONOMY = {
    ("Oznaky", "Ознаки дезінформації", "S"): {
        ("Oznaky_ZaZmistom", "За змістом"): [
            ("Oznaka_EmotsiinaLeksyka", "Емоційна лексика"),
            ("Oznaka_NemaPershodzherela", "Немає першоджерела"),
            ("Oznaka_VyrvanyiKontekst", "Вирваний або змінений контекст"),
            ("Oznaka_ZbirKoshtiv", "Терміновий збір коштів на приватну картку"),
        ],
        ("Oznaky_ZaAvtorom", "За автором"): [
            ("Oznaka_NovyiAkaunt", "Новий неверифікований акаунт"),
            ("Oznaka_BotMerezha", "Масові репости бот-мережі"),
            ("Oznaka_ZminaTematyky", "Різка зміна тематики акаунта"),
            ("Oznaka_SprostovaniDopysy", "Автор має спростовані дописи"),
        ],
        ("Oznaky_ZaMedia", "За медіа"): [
            ("Oznaka_ZastarileFoto", "Застаріле фото (EXIF)"),
            ("Oznaka_HeolokatsiiaNeZbihaietsia", "Невідповідність геолокації"),
            ("Oznaka_Dypfeik", "Дипфейк або монтаж"),
        ],
    },
    ("Metody", "Методи перевірки", "M"): {
        ("Metody_TekhnichnaVeryfikatsiia", "Технічна верифікація"): [
            ("Metod_ReversyvnyiPoshuk", "Реверсивний пошук зображень"),
            ("Metod_AnalizEXIF", "Аналіз EXIF"),
            ("Metod_Heolokatsiia", "Геолокація"),
            ("Metod_MerezhaPoshyrennia", "Аналіз мережі поширення"),
        ],
        ("Metody_ZvirkaZBazamy", "Звірка з базами"): [
            ("Metod_BazyFaktcheckeriv", "Пошук у базах фактчекерів"),
            ("Metod_OfitsiineDzherelo", "Звірка з офіційним джерелом"),
        ],
        ("Metody_EkspertnaPerevirka", "Експертна перевірка"): [
            ("Metod_PershodzhereloLantsiuzhok", "Пошук першоджерела (ланцюжок репостів)"),
            ("Metod_PerekhresnaPerevirka", "Перехресна перевірка"),
            ("Metod_ZapytEksperta", "Запит до галузевого експерта"),
        ],
    },
}


def build():
    g = Graph()
    g.bind("", NS); g.bind("skos", SKOS); g.bind("dcterms", DCTERMS)
    for (code, label, prefix), subs in TAXONOMY.items():
        scheme = NS[f"{code}Scheme"]
        g.add((scheme, RDF.type, SKOS.ConceptScheme))
        g.add((scheme, SKOS.prefLabel, Literal(f"Таксономія: {label.lower()}", lang="uk")))
        g.add((scheme, DCTERMS.modified, Literal("2026-11-04")))
        top = NS[code]
        g.add((top, RDF.type, SKOS.Concept)); g.add((top, SKOS.prefLabel, Literal(label, lang="uk")))
        g.add((top, SKOS.notation, Literal(prefix))); g.add((top, SKOS.inScheme, scheme)); g.add((top, SKOS.topConceptOf, scheme))
        for i, ((scode, slabel), leaves) in enumerate(subs.items(), 1):
            s = NS[scode]
            g.add((s, RDF.type, SKOS.Concept)); g.add((s, SKOS.prefLabel, Literal(slabel, lang="uk")))
            g.add((s, SKOS.notation, Literal(f"{prefix}{i}"))); g.add((s, SKOS.broader, top)); g.add((s, SKOS.inScheme, scheme))
            for j, (lcode, llabel) in enumerate(leaves, 1):
                c = NS[lcode]
                g.add((c, RDF.type, SKOS.Concept)); g.add((c, SKOS.prefLabel, Literal(llabel, lang="uk")))
                g.add((c, SKOS.notation, Literal(f"{prefix}{i}.{j}"))); g.add((c, SKOS.broader, s)); g.add((c, SKOS.inScheme, scheme))
    out = ROOT / "taxonomy" / "taxonomy.ttl"
    out.parent.mkdir(exist_ok=True)
    g.serialize(out, format="turtle")
    return out, len(g)


if __name__ == "__main__":
    print(*build())
