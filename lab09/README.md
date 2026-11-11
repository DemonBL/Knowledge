# ЛР 9 · Графова база знань у Neo4j

    run_lab09.bat      # дані (seed 42) → імпорт + обмеження/індекси → 11 запитів → перевірка → GDS → PROFILE → SPARQL vs Cypher
    run_t2c_both.bat   # text-to-Cypher, підказки v1 і v2 (qwen2.5:7b, read-only)

Артефакти: docs/graph_schema.(png|dot), docs/cq_mapping.md, import/*.cypher, data/*.csv, queries/*.cypher,
docs/cypher_results.md, docs/gds_report.md, docs/sparql_vs_cypher.md, tests/t2c*.jsonl, results/*.json,
llm_log/, claims/claims.csv.
