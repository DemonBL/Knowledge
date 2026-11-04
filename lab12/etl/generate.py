"""ЛР12 · документований генератор синтетичних подій «перевірка публікації» (seed = 12).

Що моделюється (див. docs/star_design.md, розділ «Дані»):
  * період 01.07.2026–31.10.2026, ≈ 16 перевірок на день, у вихідні ×0,6;
  * сплески наративів: NAR-03 «Отруєна питна вода» (10–25.08), NAR-05 «Фейкові збори коштів» (15.09–05.10),
    NAR-02 «Колапс критичної інфраструктури» (10–31.10);
  * акаунти: 45 з графа ЛР 9 + 75 синтетичних; у 25 акаунтів рівень довіри знижується за правилом R2 (історія для SCD2);
  * фактчекери: 6 з ЛР 9 + 6 синтетичних, 4 організації з ЛР 9;
  * ймовірність «фейку» залежить від ознаки, типу акаунта і довіри; час до вердикту — від методу і пріоритету;
  * у сирі дані навмисно додано 6 дефектів (4 дублікати, 2 посилання на неіснуючий акаунт) — їх має відсіяти ELT.
Вихід: data/raw/*.csv (імітація операційних систем: журнал перевірок, реєстр акаунтів, кадровий список)."""
import csv, math, random
from datetime import date, datetime, timedelta
from pathlib import Path

SEED = 12
random.seed(SEED)
ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"; RAW.mkdir(parents=True, exist_ok=True)
LR9 = ROOT / "etl" / "lr9"          # копія nodes_Account/FactChecker/FactCheckOrg/Narrative з ЛР 9
NS = "http://www.lnu.edu.ua/ontologies/disinfo-analysis.owl#"
D0, D1 = date(2026, 7, 1), date(2026, 10, 31)


def rd(name):
    with open(LR9 / f"{name}.csv", encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ---------------- акаунти та історія довіри (SCD2-джерело) ----------------
PLATFORMS = ["Telegram", "Facebook", "X", "TikTok", "Instagram", "YouTube"]
TRUST = {1: "низький", 2: "знижений", 3: "середній", 4: "високий"}
accounts, history = [], []
for a in rd("nodes_Account"):
    accounts.append(dict(account_id=a["id"], name=a["name"], kind=a["kind"], platform="Telegram" if "Telegram" in a["name"] or a["kind"] in ("анонімний канал", "бот") else random.choice(PLATFORMS[:3]),
                         trust_level=int(a["trustLevel"]), created=a["createdAt"]))
KIND_W = [("бот", 1, 30), ("анонімний канал", 1, 12), ("анонімний канал", 2, 10), ("користувач", 2, 13), ("користувач", 3, 25), ("медіа", 4, 10)]
for i in range(46, 121):
    kind, lvl, _ = random.choices(KIND_W, [w for *_, w in KIND_W])[0]
    created = D0 + timedelta(days=random.randint(-700, 100)) if kind != "бот" else D0 + timedelta(days=random.randint(-60, 110))
    accounts.append(dict(account_id=f"ACC-{i:03d}", name=f"{kind.capitalize()} #{i}", kind=kind,
                         platform=random.choices(PLATFORMS, [50, 18, 12, 10, 6, 4])[0], trust_level=lvl, created=created.isoformat()))
for a in accounts:
    history.append(dict(account_id=a["account_id"], trust_level=a["trust_level"], valid_from=a["created"], reason="початковий рівень"))
for a in random.sample([a for a in accounts if a["trust_level"] >= 2], 25):  # правило R2: знизити на 1 рівень
    when = D0 + timedelta(days=random.randint(20, 110))
    if when.isoformat() <= history[[h["account_id"] for h in history].index(a["account_id"])]["valid_from"]:
        continue
    a["trust_new"] = a["trust_level"] - 1
    history.append(dict(account_id=a["account_id"], trust_level=a["trust_level"] - 1, valid_from=when.isoformat(),
                        reason="R2: спростоване твердження з ≥ 1000 поширень"))
created_of = {a["account_id"]: a["created"] for a in accounts}

# ---------------- фактчекери, організації, наративи ----------------
orgs = {o["id"]: o["name"] for o in rd("nodes_FactCheckOrg")}
analysts = [dict(analyst_id=f["id"], name=f["name"], specialization=f["specialization"]) for f in rd("nodes_FactChecker")]
org_of = {"FCH-01": "ORG-01", "FCH-02": "ORG-02", "FCH-03": "ORG-03", "FCH-04": "ORG-04", "FCH-05": "ORG-01", "FCH-06": "ORG-02"}
for i, spec in enumerate(["військова тематика", "регіональні новини", "медіа та фото", "соцмережі й боти", "здоров'я та медицина", "загальна тематика"], 7):
    analysts.append(dict(analyst_id=f"FCH-{i:02d}", name=f"Аналітик Ф-{i:02d} ({spec})", specialization=spec))
    org_of[f"FCH-{i:02d}"] = f"ORG-0{(i % 4) + 1}"
for a in analysts:
    a["org_id"] = org_of[a["analyst_id"]]; a["org_name"] = orgs[a["org_id"]]
narratives = rd("nodes_Narrative")
THEME = {"NAR-01": "безпека", "NAR-02": "інфраструктура", "NAR-03": "здоров'я", "NAR-04": "влада", "NAR-05": "фінанси", "NAR-06": "безпека"}
SPIKE = {"NAR-03": (date(2026, 8, 10), date(2026, 8, 25), 3.0), "NAR-05": (date(2026, 9, 15), date(2026, 10, 5), 2.5), "NAR-02": (date(2026, 10, 10), date(2026, 10, 31), 2.2)}

# ---------------- ознаки й методи (листки таксономії) ----------------
SIG = {"content": ["Oznaka_EmotsiinaLeksyka", "Oznaka_NemaPershodzherela", "Oznaka_VyrvanyiKontekst", "Oznaka_ZbirKoshtiv"],
       "author": ["Oznaka_NovyiAkaunt", "Oznaka_BotMerezha", "Oznaka_ZminaTematyky", "Oznaka_SprostovaniDopysy"],
       "media": ["Oznaka_ZastarileFoto", "Oznaka_HeolokatsiiaNeZbihaietsia", "Oznaka_Dypfeik"]}
P_FAKE = {"Oznaka_EmotsiinaLeksyka": .30, "Oznaka_NemaPershodzherela": .45, "Oznaka_VyrvanyiKontekst": .25, "Oznaka_ZbirKoshtiv": .70,
          "Oznaka_NovyiAkaunt": .45, "Oznaka_BotMerezha": .60, "Oznaka_ZminaTematyky": .35, "Oznaka_SprostovaniDopysy": .55,
          "Oznaka_ZastarileFoto": .40, "Oznaka_HeolokatsiiaNeZbihaietsia": .30, "Oznaka_Dypfeik": .65}
METHOD_BY = {"content": [("Metod_BazyFaktcheckeriv", 4), ("Metod_OfitsiineDzherelo", 5), ("Metod_PerekhresnaPerevirka", 2), ("Metod_ZapytEksperta", 1)],
             "author": [("Metod_MerezhaPoshyrennia", 5), ("Metod_PershodzhereloLantsiuzhok", 4), ("Metod_BazyFaktcheckeriv", 1)],
             "media": [("Metod_ReversyvnyiPoshuk", 5), ("Metod_AnalizEXIF", 3), ("Metod_Heolokatsiia", 3), ("Metod_ZapytEksperta", 1)]}
HOURS = {"Metod_ReversyvnyiPoshuk": 3, "Metod_AnalizEXIF": 2.5, "Metod_Heolokatsiia": 7, "Metod_MerezhaPoshyrennia": 9, "Metod_BazyFaktcheckeriv": 2,
         "Metod_OfitsiineDzherelo": 6, "Metod_PershodzhereloLantsiuzhok": 10, "Metod_PerekhresnaPerevirka": 8, "Metod_ZapytEksperta": 20}
SPEC_FOR = {"media": "медіа та фото", "author": "соцмережі й боти", "NAR-05": "фінансові шахрайства", "NAR-03": "здоров'я та медицина",
            "NAR-02": "регіональні новини", "NAR-01": "військова тематика", "NAR-06": "військова тематика", "NAR-04": "регіональні новини"}
ACC_W = {"бот": 3.0, "анонімний канал": 4.0, "користувач": 1.0, "медіа": 0.6}


checks = []
cid = 0
d = D0
while d <= D1:
    n = 16 * (0.6 if d.weekday() >= 5 else 1.0) * (1 + 0.15 * math.sin(d.toordinal() / 9))
    active = [nid for nid, (a, b, k) in SPIKE.items() if a <= d <= b]
    n *= 1 + 0.5 * len(active)
    for _ in range(max(1, round(random.gauss(n, 3)))):
        cid += 1
        # наратив
        if active and random.random() < 0.55:
            nar = random.choice(active)
        elif random.random() < 0.45:
            nar = random.choice(narratives)["id"]
        else:
            nar = None
        # акаунт, що існує на цю дату
        pool = [a for a in accounts if a["created"] <= d.isoformat()]
        acc = random.choices(pool, [ACC_W[a["kind"]] for a in pool])[0]
        hist = sorted([h for h in history if h["account_id"] == acc["account_id"] and h["valid_from"] <= d.isoformat()], key=lambda h: h["valid_from"])
        trust = hist[-1]["trust_level"]
        # ознака
        if nar == "NAR-05" and random.random() < .6: sig = "Oznaka_ZbirKoshtiv"
        elif acc["kind"] == "бот" and random.random() < .6: sig = random.choice(["Oznaka_BotMerezha", "Oznaka_NovyiAkaunt"])
        else:
            branch = random.choices(["content", "author", "media"], [5, 3, 3])[0]; sig = random.choice(SIG[branch])
        branch = next(k for k, v in SIG.items() if sig in v)
        meth = random.choices(*zip(*METHOD_BY[branch]))[0]
        # вердикт
        p = 0.72 * P_FAKE[sig] * {1: 1.35, 2: 1.15, 3: 0.8, 4: 0.45}[trust] * (1.2 if nar else 0.9)
        r = random.random()
        verdict = "фейк" if r < min(p, .9) else "маніпуляція" if r < min(p, .9) + .22 else "неможливо перевірити" if r < min(p, .9) + .32 else "правда"
        ev = {"фейк": random.randint(2, 5), "маніпуляція": random.randint(2, 4), "правда": random.randint(2, 3), "неможливо перевірити": random.randint(0, 1)}[verdict]
        if verdict in ("фейк", "маніпуляція") and random.random() < .025: ev = 1          # порушення регламенту (≥ 2 доказів)
        conf = round(min(.99, max(.3, .45 + .1 * ev + random.gauss(0, .06))), 2)
        shares = int(random.lognormvariate(5.2 + (.8 if acc["kind"] in ("медіа", "анонімний канал") else 0) + (.6 if nar else 0), 1.1))
        prio = "високий" if shares >= 1500 or (trust <= 1 and shares >= 700) else "середній" if shares >= 200 else "низький"
        hrs = HOURS[meth] * {"високий": .55, "середній": 1.0, "низький": 1.6}[prio] * random.lognormvariate(0, .45)
        detected = datetime(d.year, d.month, d.day, random.randint(6, 22), random.randint(0, 59))
        verdict_at = detected + timedelta(hours=hrs)
        cand = [a for a in analysts if a["specialization"] in (SPEC_FOR.get(nar), SPEC_FOR.get(branch))]
        an = random.choice(cand) if cand and random.random() < .7 else random.choice(analysts)
        checks.append(dict(check_id=f"CHK-{cid:05d}", publication_id=f"PUB-{100000 + cid}", account_id=acc["account_id"], platform=acc["platform"],
                           analyst_id=an["analyst_id"], narrative_id=nar or "", signal_iri=NS + sig, method_iri=NS + meth, priority=prio,
                           detected_at=detected.isoformat(timespec="minutes"), verdict_at=verdict_at.isoformat(timespec="minutes"),
                           verdict=verdict, confidence=conf, evidence_count=ev, shares_at_check=shares,
                           effort_minutes=int(20 + hrs * random.uniform(4, 9))))
    d += timedelta(days=1)

# відкриті справи аналітика на момент вердикту (напівадитивна міра)
by_an = {}
for c in checks: by_an.setdefault(c["analyst_id"], []).append(c)
for lst in by_an.values():
    for c in lst:
        c["backlog_open"] = sum(1 for o in lst if o["detected_at"] <= c["verdict_at"] < o["verdict_at"])
# навмисні дефекти сирих даних
defects = [dict(random.choice(checks)) for _ in range(4)]
for k in range(2):
    bad = dict(random.choice(checks)); bad["check_id"] = f"CHK-9{k:04d}"; bad["account_id"] = f"ACC-9{k:02d}"; defects.append(bad)
rows = checks + defects
random.shuffle(rows)


def wr(name, data):
    with open(RAW / name, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(data[0])); w.writeheader(); w.writerows(data)


wr("checks.csv", rows)
wr("accounts.csv", [{k: a[k] for k in ("account_id", "name", "kind", "platform", "created")} for a in accounts])
wr("account_trust_history.csv", history)
wr("analysts.csv", analysts)
wr("narratives.csv", [dict(narrative_id=n["id"], name=n["name"], theme=THEME[n["id"]]) for n in narratives])
print(f"checks: {len(checks)} (+{len(defects)} дефектних), accounts: {len(accounts)}, trust history: {len(history)}, analysts: {len(analysts)}")
