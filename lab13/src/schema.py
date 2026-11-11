"""ЛР13 · схема витягу (v2): типи сутностей, відношення з сигнатурами, JSON-схема виходу. Єдине джерело для обох методів і оцінювання."""

ENTITY_TYPES = {
    "ORG": "організація, проєкт, державний орган, фонд, компанія без власної платформи (StopFake, ЦПД, ВООЗ, МОЗ України, Microsoft)",
    "PERSON": "конкретна названа особа (Поліна Лисенко, Mark Miller); посади без імені не розмічаються",
    "PLATFORM": "соцмережа, месенджер, відеосервіс або їх загальна назва (Telegram, Facebook, YouTube, «соціальні мережі», «месенджери»)",
    "PHENOMENON": "вид дезінформації/маніпуляції чи шкідливої інформаційної активності (фейк, дипфейк, пропаганда, фішинг, тролінг, соціальний бот)",
    "METHOD": "метод, технологія, інструмент або стандарт перевірки/створення контенту (аналіз EXIF, геолокація, штучний інтелект, TensorFlow)",
    "LOCATION": "країна, місто, регіон, місце (Україна, Одеса, Майдан)",
    "DATE": "дата, місяць, рік, період або строк (2 березня 2014 року, 2017 року, 12 годин)",
    "CASE_ID": "ідентифікатор бази знань Hub: ACC-, CLM-, NAR-, VRD-, PUB-, OFF-, RULE-, Ф-xx, псевдонім акаунта «Анонімний Telegram-канал #N»",
}
# відношення: (дозволені типи голови, дозволені типи хвоста, опис)
RELATIONS = {
    "FOUNDED_ON": ({"ORG", "PLATFORM"}, {"DATE"}, "організацію/проєкт створено, запущено, утворено в дату"),
    "PART_OF": ({"ORG", "CASE_ID"}, {"ORG", "CASE_ID"}, "є підрозділом/органом/частиною (ЦПД → РНБО; CLM → NAR)"),
    "LEADS": ({"PERSON"}, {"ORG", "PLATFORM"}, "особа очолює, заснувала або є автором ідеї організації"),
    "COUNTERS": ({"ORG", "PLATFORM", "METHOD"}, {"PHENOMENON"}, "протидіє, виявляє, спростовує, забороняє явище"),
    "COOPERATES_WITH": ({"ORG", "PLATFORM"}, {"ORG", "PLATFORM"}, "співпрацює, є партнером, фінансує (симетричне)"),
    "SUBTYPE_OF": ({"PHENOMENON", "METHOD"}, {"PHENOMENON", "METHOD"}, "є видом / різновидом"),
    "SPREADS": ({"ORG", "PERSON", "CASE_ID"}, {"PHENOMENON", "CASE_ID"}, "суб'єкт поширює явище або твердження (акаунт-першоджерело → CLM)"),
    "SPREADS_VIA": ({"PHENOMENON", "CASE_ID"}, {"PLATFORM"}, "явище поширюється через платформу / з'являється на ній"),
    "REFUTES": ({"ORG"}, {"CASE_ID"}, "офіційне джерело спростовує твердження"),
    "USES": ({"ORG", "PLATFORM", "PHENOMENON", "METHOD"}, {"METHOD", "PHENOMENON"}, "використовує технологію, метод або прийом"),
}
SYMMETRIC = {"COOPERATES_WITH"}

JSON_SCHEMA = {
    "type": "object", "required": ["entities", "relations"], "additionalProperties": False,
    "properties": {
        "entities": {"type": "array", "items": {"type": "object", "required": ["text", "type"], "additionalProperties": False,
                     "properties": {"text": {"type": "string", "minLength": 1}, "type": {"enum": list(ENTITY_TYPES)}}}},
        "relations": {"type": "array", "items": {"type": "object", "required": ["head", "relation", "tail", "evidence"], "additionalProperties": False,
                      "properties": {"head": {"type": "string"}, "head_type": {"enum": list(ENTITY_TYPES)}, "relation": {"enum": list(RELATIONS)},
                                     "tail": {"type": "string"}, "tail_type": {"enum": list(ENTITY_TYPES)},
                                     "evidence": {"type": "string", "minLength": 5}, "confidence": {"type": "number", "minimum": 0, "maximum": 1}}}},
    },
}
