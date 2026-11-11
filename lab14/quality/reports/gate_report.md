# Quality gate · запуск 3 · data/defects · **BLOCKED**

3 навмисні дефекти (D-1, D-2, D-3)

Час: 2026-11-06T20:38:17+00:00; перевірок: 19; пройдено: 10; critical-порушень: 6; попереджень: 1; пропущено: 2; 1.93 с.

| Перевірка | Інструмент | Критичність | Результат | Порушення |
|---|---|---|---|---|
| test_T08_chunk_ids_unique | pytest / GE-очікування | critical | ✅ |  |
| test_T09_no_exact_duplicate_chunks | pytest / GE-очікування | critical | ❌ | AssertionError: точні дублікати фрагментів: [('W14:s099', 'W14:s001')] (усього 1) |
| test_T10_chunk_provenance | pytest / GE-очікування | critical | ❌ | AssertionError: фрагменти без source_url/license: 1 (напр. ['W14:s099']) |
| test_T11_superseded_flagged | pytest / GE-очікування | critical | ✅ |  |
| test_T12_claim_status_complete | pytest / GE-очікування | critical | ✅ |  |
| test_T13_referential_integrity | pytest / GE-очікування | critical | ❌ | AssertionError: ребра до неіснуючих вузлів: [('MAKES_CLAIM', 'PUB-012', 'CLM-99')] |
| test_T14_confidence_range | pytest / GE-очікування | critical | ❌ | AssertionError: confidence поза [0, 1]: [('MAKES_CLAIM', 'PUB-012', 'CLM-99', '1.7')] |
| test_T15_rag_evidence_preserved | pytest / GE-очікування | critical | ✅ |  |
| test_T16_freshness | pytest / GE-очікування | warning | ⚠️ | AssertionError: застарілі документи (> 24 міс.): ['W07', 'W22', 'W23', 'W24'] |
| test_T17_chunk_schema | JSON Schema | critical | ❌ | AssertionError: фрагменти не відповідають схемі: 1; [(529, "None is not of type 'string'")] |
| test_T18_registry_schema | JSON Schema | critical | — |  |
| test_T19_alternatives_schema | JSON Schema | critical | — |  |
| test_T01_shacl_no_violations | SHACL (pySHACL) | critical | ❌ | AssertionError: SHACL Violation: 4; приклади: [('st_MAKES_CLAIM_137', 'S6: confidence — число 0…1'), ('PUB-010', 'S2: публікація має рівно одного автора'), ('PUB-012', 'S2: публікація висуває рівно одне твердження'), ('PUB-012', 'S2: публікація висуває рівно одне твердження')] |
| test_T02_shacl_warnings | SHACL (pySHACL) | warning | ✅ |  |
| test_T03_true_verdict_two_sources | SPARQL-інваріант (rdflib) | critical | ✅ |  |
| test_T04_fake_two_evidence | SPARQL-інваріант (rdflib) | critical | ✅ |  |
| test_T05_no_refuted_and_confirmed | SPARQL-інваріант (rdflib) | critical | ✅ |  |
| test_T06_temporal_flagged | SPARQL-інваріант (rdflib) | critical | ✅ |  |
| test_T07_derived_not_before_parent | SPARQL-інваріант (rdflib) | critical | ✅ |  |

## Тренд

| Запуск | Версія | Мітка | Статус | Пройдено | Critical | Warning |
|---|---|---|---|---|---|---|
| 1 | baseline | baseline kb-2026.11-v0 (до очищення) | BLOCKED | 8/19 | 7 | 2 |
| 2 | clean | clean kb-2026.11-v1 (після очищення) | PASSED | 18/19 | 0 | 1 |
| 3 | data/defects | 3 навмисні дефекти (D-1, D-2, D-3) | BLOCKED | 10/19 | 6 | 1 |
