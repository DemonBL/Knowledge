"""ЛР9 · генератор навчального набору даних для графової бази знань.

Набір СИНТЕТИЧНИЙ (seed=42) і побудований за онтологією ЛР7–8 «Аналіз достовірності
інформації». Реальні лише назви організацій та інструментів; акаунти, публікації,
твердження й вердикти змодельовано, щоб відтворити типову картину поширення
дезінформації: кілька анонімних «першоджерел», бот-мережі, що підсилюють їх,
медіа з високою довірою та фактчекери, які спростовують твердження.

Вихід: data/nodes_<Label>.csv і data/rels_<TYPE>.csv (UTF-8).
"""
import csv
import random
from datetime import date, timedelta
from pathlib import Path

SEED = 42
rnd = random.Random(SEED)
OUT = Path(__file__).resolve().parents[1] / "data"
OUT.mkdir(exist_ok=True)

nodes: dict[str, list[dict]] = {}
rels: dict[str, list[dict]] = {}
D0 = date(2026, 9, 1)


def d(offset: int) -> str:
    return (D0 + timedelta(days=offset)).isoformat()


def node(label, **p):
    nodes.setdefault(label, []).append(p)
    return p["id"]


def rel(t, a, b, source, confidence, valid_from, **p):
    rels.setdefault(t, []).append(dict(start=a, end=b, source=source,
                                        confidence=round(confidence, 2), validFrom=valid_from, **p))


# ---------------------------------------------------------------- довідники
TRUST = {1: "низький", 2: "знижений", 3: "середній", 4: "високий"}
OFFICIAL = [("OFF-01", "ДСНС України"), ("OFF-02", "Повітряні сили ЗСУ"),
            ("OFF-03", "Офіційні канали міських рад"), ("OFF-04", "МОЗ України"),
            ("OFF-05", "Національна поліція України")]
ORGS = [("ORG-01", "VoxCheck"), ("ORG-02", "StopFake"), ("ORG-03", "EUvsDisinfo"),
        ("ORG-04", "Детектор медіа")]
TOOLS = [("TOOL-01", "Реверсивний пошук зображень", "медіа"),
         ("TOOL-02", "Аналіз EXIF-метаданих", "медіа"),
         ("TOOL-03", "Геолокація за супутниковими знімками", "медіа"),
         ("TOOL-04", "Аналіз мережі поширення", "мережа"),
         ("TOOL-05", "Архів вебсторінок (Wayback Machine)", "текст")]
RULES = [("RULE-1", "вік акаунта < 30 днів AND акаунт не верифікований", "індекс довіри = знижений"),
         ("RULE-2", "автор має спростоване твердження у публікації з ≥ 1000 поширень",
          "знизити індекс довіри на один рівень"),
         ("RULE-3", "публікацію без першоджерела репостять ≥ 3 акаунти з низькою довірою за 1 годину",
          "пріоритет перевірки = високий"),
         ("RULE-4", "дата EXIF медіафайлу раніша за дату події більш ніж на 7 днів",
          "медіафайл позначити як повторно використаний")]
NARRATIVES = [
    ("NAR-01", "Повна втрата контролю над містом", [
        "Місцева влада втратила контроль над ситуацією {u} {l}",
        "{U} {l} зруйновано всю енергетичну інфраструктуру",
        "Рятувальники {u} {l} відмовляються виїжджати на виклики",
        "{U} {l} оголошено примусову евакуацію всього населення"]),
    ("NAR-02", "Колапс критичної інфраструктури", [
        "{n} залишиться без води на два тижні",
        "Усі лікарні {g} переведено на аварійне живлення без запасу пального",
        "Мобільний зв'язок {u} {l} вимкнуть на невизначений строк",
        "Опалювальний сезон {u} {l} скасовано"]),
    ("NAR-03", "Отруєна питна вода", [
        "У водогоні {g} виявлено отруйні речовини",
        "МОЗ приховує масові отруєння водою {u} {l}"]),
    ("NAR-04", "Втеча місцевої влади", [
        "Мер {g} таємно виїхав за кордон",
        "Депутати міської ради {g} вивезли сім'ї з міста"]),
    ("NAR-05", "Фейкові збори коштів", [
        "Збір на «дрони для {g}» від імені волонтерського фонду",
        "Терміновий збір на лікування поранених рятувальників {g}"]),
    ("NAR-06", "Небезпека укриттів і пунктів незламності", [
        "Укриття {u} {l} затоплені й непридатні",
        "Пункти незламності {u} {l} не працюють"]),
]
TRUE_CLAIMS = ["{U} {l} оголошено повітряну тривогу",
               "{U} {l} частково знеструмлено два райони після атаки",
               "{U} {l} відкрито додаткові пункти незламності",
               "Графік відключень світла {u} {l} змінено"]
CITIES = [("Львів", "Львові", "Львова"), ("Київ", "Києві", "Києва"), ("Харків", "Харкові", "Харкова"),
          ("Дніпро", "Дніпрі", "Дніпра"), ("Одеса", "Одесі", "Одеси"),
          ("Запоріжжя", "Запоріжжі", "Запоріжжя"), ("Миколаїв", "Миколаєві", "Миколаєва")]

def fmt(tpl, city):
    v = city[1][0] in "АЕЄИІЇОУЮЯ"
    return tpl.format(n=city[0], l=city[1], g=city[2], u="в" if v else "у", U="В" if v else "У")


for i, n in OFFICIAL:
    node("OfficialSource", id=i, name=n, trust="високий", trustLevel=4)
for i, n in ORGS:
    node("FactCheckOrg", id=i, name=n, trust="високий", trustLevel=4)
for i, n, k in TOOLS:
    node("Tool", id=i, name=n, kind=k)
for i, c, a in RULES:
    node("Rule", id=i, condition=c, action=a)

checkers = []
for k in range(6):
    fid = f"FCH-0{k+1}"
    org = ORGS[k % 4][0]
    spec = ["військова тематика", "регіональні новини", "медіа та фото", "соцмережі й боти",
            "здоров'я та медицина", "фінансові шахрайства"][k]
    node("FactChecker", id=fid, name=f"Аналітик Ф-0{k+1} ({spec})", specialization=spec)
    rel("WORKS_FOR", fid, org, "org_staff_list", 1.0, d(-200))
    checkers.append(fid)
    for t in rnd.sample([t[0] for t in TOOLS], 2 + (k % 2)):
        rel("USES", fid, t, "analyst_profile", 0.9, d(-100))
rel("FORMALIZED_IN", "FCH-01", "RULE-1", "lab07_rules", 1.0, d(-60))
rel("FORMALIZED_IN", "FCH-01", "RULE-2", "lab07_rules", 1.0, d(-60))
rel("FORMALIZED_IN", "FCH-04", "RULE-3", "analyst_interview", 0.8, d(-30))
rel("FORMALIZED_IN", "FCH-03", "RULE-4", "analyst_interview", 0.8, d(-30))

# ---------------------------------------------------------------- наративи й твердження
claims = []  # (id, narrative or None, is_true, city)
cid = 0
for nid, name, templates in NARRATIVES:
    node("Narrative", id=nid, name=name)
    for tpl, city in [(t, c) for t in templates for c in rnd.sample(CITIES, 2)]:
        cid += 1
        c = f"CLM-{cid:02d}"
        txt = fmt(tpl, city)
        node("Claim", id=c, text=txt, priority=rnd.choice(["високий", "високий", "середній"]),
             city=city[0])
        rel("PART_OF", c, nid, "analyst_clustering", rnd.uniform(0.7, 0.95), d(rnd.randint(0, 20)))
        claims.append((c, nid, False, city))
for tpl in TRUE_CLAIMS * 2:
    city = rnd.choice(CITIES)
    cid += 1
    c = f"CLM-{cid:02d}"
    node("Claim", id=c, text=fmt(tpl, city), priority="середній", city=city[0])
    claims.append((c, None, True, city))

# ---------------------------------------------------------------- акаунти
accounts = []  # (id, kind, trustLevel)
acc = 0


def account(kind, name, trust, followers, created_offset, verified):
    global acc
    acc += 1
    a = f"ACC-{acc:03d}"
    node("Account", id=a, name=name, kind=kind, trust=TRUST[trust], trustLevel=trust,
         followers=followers, createdAt=d(created_offset), verified=verified)
    accounts.append((a, kind, trust))
    return a


anon = [account("анонімний канал", f"Анонімний Telegram-канал #{k+1}", rnd.choice([1, 2]),
                rnd.randint(800, 25000), rnd.randint(-40, 5), False) for k in range(8)]
botsA = [account("бот", f"Бот-акаунт A{k+1}", 1, rnd.randint(20, 300), rnd.randint(-25, 10), False)
         for k in range(10)]
botsB = [account("бот", f"Бот-акаунт B{k+1}", 1, rnd.randint(20, 300), rnd.randint(-25, 10), False)
         for k in range(8)]
media = [account("медіа", n, 4, rnd.randint(40000, 400000), rnd.randint(-2500, -900), True)
         for n in ["Суспільне Новини", "Укрінформ", "Твоє Місто (Львів)", "Громадське",
                   "Zaxid.net", "Українська правда"]]
users = [account("користувач", f"Користувач #{k+1}", rnd.choice([2, 3, 3, 3]), rnd.randint(50, 3000),
                 rnd.randint(-1500, -100), False) for k in range(13)]

# ---------------------------------------------------------------- публікації, медіа, поширення
pub = 0
med = 0
pubs = []


def publication(author, claim, offset, shares, parent=None, has_media=False, platform=None):
    global pub, med
    pub += 1
    p = f"PUB-{pub:03d}"
    text = next(n["text"] for n in nodes["Claim"] if n["id"] == claim)
    plat = platform or ("Telegram" if author in anon or author in botsA else
                        rnd.choice(["Facebook", "Telegram", "X"]))
    node("Publication", id=p, text=text if parent is None else f"Репост із коментарем: {text}",
         shares=shares, platform=plat, publishedAt=d(offset))
    rel("PUBLISHED", author, p, f"{plat.lower()}_export", 1.0, d(offset))
    rel("MAKES_CLAIM", p, claim, "nlp_claim_extraction", rnd.uniform(0.75, 0.98), d(offset))
    if parent:
        rel("DERIVED_FROM", p, parent, "propagation_analysis", rnd.uniform(0.7, 0.99), d(offset))
    if has_media:
        med += 1
        m = f"MED-{med:02d}"
        reused = rnd.random() < 0.75
        exif = d(offset - rnd.randint(400, 1500)) if reused else d(offset)
        node("Media", id=m, kind=rnd.choice(["фото", "фото", "відео"]), exifDate=exif,
             reverseSearch="збіг із матеріалом іншої події" if reused else "збігів не знайдено")
        rel("CONTAINS", p, m, f"{plat.lower()}_export", 1.0, d(offset))
        for t in rnd.sample(["TOOL-01", "TOOL-02", "TOOL-03"], rnd.choice([1, 2])):
            rel("VERIFIED_WITH", m, t, "analyst_case_file", rnd.uniform(0.8, 1.0), d(offset + 1))
    pubs.append(p)
    return p


fake_claims = [c for c in claims if not c[2]]
true_claims = [c for c in claims if c[2]]
cluster_of_bots = {"NAR-01": botsA, "NAR-02": botsA, "NAR-03": botsB, "NAR-04": botsB,
                   "NAR-05": botsB, "NAR-06": botsA}
for k, (c, nid, _, _) in enumerate(fake_claims):
    off = rnd.randint(0, 40)
    origin = publication(anon[k % len(anon)], c, off, rnd.randint(300, 6000), has_media=rnd.random() < 0.55)
    # ланцюжок похідних публікацій (глибина до 4): боти → користувачі
    parent = origin
    depth = rnd.choice([1, 2, 2, 3, 4])
    for lvl in range(depth):
        pool = cluster_of_bots[nid] if lvl < 2 else users
        child = publication(rnd.choice(pool), c, off + lvl, rnd.randint(10, 1500), parent=parent)
        if rnd.random() < 0.5 and lvl == 0:  # відгалуження
            publication(rnd.choice(pool), c, off + 1, rnd.randint(10, 400), parent=origin)
        parent = child
    # масові репости ботами з кластера
    for b in rnd.sample(cluster_of_bots[nid], rnd.randint(3, 6)):
        rel("REPOSTED", b, origin, "platform_api", 1.0, d(off), minutesAfter=rnd.randint(1, 55))
    if rnd.random() < 0.3:
        rel("REPOSTED", rnd.choice(users), origin, "platform_api", 1.0, d(off + 1),
            minutesAfter=rnd.randint(60, 900))
for k, (c, _, _, _) in enumerate(true_claims):
    off = rnd.randint(0, 40)
    p = publication(media[k % len(media)], c, off, rnd.randint(2000, 15000))
    for u in rnd.sample(users, rnd.randint(1, 3)):
        rel("REPOSTED", u, p, "platform_api", 1.0, d(off), minutesAfter=rnd.randint(5, 300))

# ---------------------------------------------------------------- вердикти, офіційні джерела
ver = 0
pending = set(rnd.sample([c[0] for c in fake_claims], 6)) | {true_claims[-1][0], true_claims[-2][0]}
official_for = {"NAR-01": "OFF-01", "NAR-02": "OFF-03", "NAR-03": "OFF-04", "NAR-04": "OFF-03",
                "NAR-05": "OFF-05", "NAR-06": "OFF-01"}
for c, nid, is_true, _ in claims:
    if c in pending:
        continue
    ver += 1
    v = f"VRD-{ver:02d}"
    cat = "правда" if is_true else rnd.choice(["фейк", "фейк", "фейк", "маніпуляція"])
    off = rnd.randint(2, 45)
    node("Verdict", id=v, category=cat, confidence=rnd.choice(["високий", "високий", "середній"]),
         decidedAt=d(off))
    rel("ABOUT", v, c, "factcheck_registry", 1.0, d(off))
    fc = rnd.choice(checkers)
    rel("ISSUED", fc, v, "factcheck_registry", 1.0, d(off))
    src = "OFF-02" if is_true and rnd.random() < 0.5 else (official_for.get(nid) or "OFF-01")
    rel("BASED_ON", v, src, "official_statement", rnd.uniform(0.85, 1.0), d(off))
    rel("CONFIRMS" if is_true else "REFUTES", src, c, "official_statement", rnd.uniform(0.85, 1.0), d(off))
    if not is_true:
        rel("BASED_ON", v, rnd.choice([t[0] for t in TOOLS]), "analyst_case_file", rnd.uniform(0.7, 0.95), d(off))
        if rnd.random() < 0.6:
            rel("BASED_ON", v, rnd.choice([o[0] for o in ORGS]), "factcheck_registry", 0.9, d(off))

# ---------------------------------------------------------------- запис CSV
for label, rows in nodes.items():
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with open(OUT / f"nodes_{label}.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, keys); w.writeheader(); w.writerows(rows)
for t, rows in rels.items():
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with open(OUT / f"rels_{t}.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, keys); w.writeheader(); w.writerows(rows)

n_nodes = sum(len(v) for v in nodes.values())
n_rels = sum(len(v) for v in rels.values())
print(f"seed={SEED}: {n_nodes} вузлів ({len(nodes)} міток), {n_rels} зв'язків ({len(rels)} типів)")
for k, v in nodes.items():
    print(f"  {k:15s} {len(v)}")
for k, v in rels.items():
    print(f"  {k:15s} {len(v)}")
