-- ЛР12 · зіркова схема «Перевірка публікацій» (DuckDB ≥ 1.1)
-- Зерно факту: один рядок = одна завершена перевірка однієї публікації одним фактчекером
--              (датується днем винесення вердикту).

CREATE TABLE dim_date (
    date_key      INTEGER PRIMARY KEY,          -- yyyymmdd
    full_date     DATE    NOT NULL UNIQUE,
    day_of_month  TINYINT NOT NULL,
    day_name      VARCHAR NOT NULL,
    iso_week      TINYINT NOT NULL,
    week_start    DATE    NOT NULL,             -- понеділок тижня
    month         TINYINT NOT NULL,
    month_name    VARCHAR NOT NULL,
    quarter       TINYINT NOT NULL,
    year          SMALLINT NOT NULL,
    is_weekend    BOOLEAN NOT NULL
);

-- Таксономія як вимір: кожне поняття SKOS — рядок з IRI; ієрархія гілка → клас → поняття.
-- Використовується у двох ролях: «ознака дезінформації» і «метод перевірки» (role-playing dimension).
CREATE TABLE dim_taxonomy (
    taxonomy_key  INTEGER PRIMARY KEY,
    concept_iri   VARCHAR NOT NULL UNIQUE,      -- IRI поняття в онтології disinfo-analysis
    notation      VARCHAR NOT NULL,             -- S2.3, M1.1 …
    label         VARCHAR NOT NULL,
    level         TINYINT NOT NULL CHECK (level BETWEEN 1 AND 3),
    parent_iri    VARCHAR,
    branch_iri    VARCHAR NOT NULL,             -- рівень 1: «Ознаки дезінформації» / «Методи перевірки»
    branch_label  VARCHAR NOT NULL,
    class_iri     VARCHAR,                      -- рівень 2: «За змістом», «Технічна верифікація» …
    class_label   VARCHAR,
    scheme_iri    VARCHAR NOT NULL
);

-- Акаунт-автор: SCD тип 2 за рівнем довіри (правило R2 знижує довіру — історію зберігаємо).
CREATE TABLE dim_account (
    account_key   INTEGER PRIMARY KEY,          -- сурогатний ключ версії
    account_id    VARCHAR NOT NULL,             -- природний ключ
    name          VARCHAR NOT NULL,
    kind          VARCHAR NOT NULL,             -- бот / анонімний канал / користувач / медіа
    trust_level   TINYINT NOT NULL CHECK (trust_level BETWEEN 1 AND 4),
    trust_label   VARCHAR NOT NULL,
    valid_from    DATE    NOT NULL,
    valid_to      DATE    NOT NULL,             -- 9999-12-31 для поточної версії
    is_current    BOOLEAN NOT NULL,
    UNIQUE (account_id, valid_from)
);

CREATE TABLE dim_platform (
    platform_key  INTEGER PRIMARY KEY,
    platform      VARCHAR NOT NULL UNIQUE,
    platform_type VARCHAR NOT NULL              -- месенджер / соцмережа / відеоплатформа
);

-- Фактчекер → організація (SCD тип 1: виправлення перезаписуються).
CREATE TABLE dim_analyst (
    analyst_key    INTEGER PRIMARY KEY,
    analyst_id     VARCHAR NOT NULL UNIQUE,
    name           VARCHAR NOT NULL,
    specialization VARCHAR NOT NULL,
    org_id         VARCHAR NOT NULL,
    org_name       VARCHAR NOT NULL
);

CREATE TABLE dim_narrative (
    narrative_key  INTEGER PRIMARY KEY,         -- 0 = «без наративу» (unknown member)
    narrative_id   VARCHAR NOT NULL UNIQUE,
    name           VARCHAR NOT NULL,
    theme          VARCHAR NOT NULL
);

CREATE TABLE dim_verdict (
    verdict_key    INTEGER PRIMARY KEY,
    category       VARCHAR NOT NULL UNIQUE,     -- фейк / маніпуляція / правда / неможливо перевірити
    is_false       BOOLEAN NOT NULL,            -- фейк або маніпуляція
    severity       TINYINT NOT NULL
);

CREATE TABLE fact_check (
    check_id          VARCHAR PRIMARY KEY,                       -- вироджений вимір (ID справи)
    publication_id    VARCHAR NOT NULL,                          -- вироджений вимір
    date_key          INTEGER NOT NULL REFERENCES dim_date(date_key),        -- дата вердикту
    detected_date_key INTEGER NOT NULL REFERENCES dim_date(date_key),        -- дата виявлення
    account_key       INTEGER NOT NULL REFERENCES dim_account(account_key),  -- версія акаунта на дату вердикту
    platform_key      INTEGER NOT NULL REFERENCES dim_platform(platform_key),
    analyst_key       INTEGER NOT NULL REFERENCES dim_analyst(analyst_key),
    narrative_key     INTEGER NOT NULL REFERENCES dim_narrative(narrative_key),
    signal_key        INTEGER NOT NULL REFERENCES dim_taxonomy(taxonomy_key), -- роль: ознака
    method_key        INTEGER NOT NULL REFERENCES dim_taxonomy(taxonomy_key), -- роль: метод
    verdict_key       INTEGER NOT NULL REFERENCES dim_verdict(verdict_key),
    priority          VARCHAR NOT NULL CHECK (priority IN ('високий', 'середній', 'низький')),
    -- міри
    check_count       INTEGER NOT NULL DEFAULT 1,     -- адитивна
    shares_at_check   INTEGER NOT NULL CHECK (shares_at_check >= 0),   -- адитивна (охоплення)
    evidence_count    INTEGER NOT NULL CHECK (evidence_count BETWEEN 0 AND 10), -- адитивна
    effort_minutes    INTEGER NOT NULL CHECK (effort_minutes > 0),     -- адитивна (трудовитрати)
    backlog_open      INTEGER NOT NULL CHECK (backlog_open >= 0),      -- напівадитивна (знімок черги)
    hours_to_verdict  DECIMAL(8,2) NOT NULL CHECK (hours_to_verdict > 0), -- неадитивна (лише AVG/медіана)
    confidence        DECIMAL(3,2) NOT NULL CHECK (confidence BETWEEN 0 AND 1), -- неадитивна
    sla_met           BOOLEAN NOT NULL                                 -- неадитивна (частка)
);
