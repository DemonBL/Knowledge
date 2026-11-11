// Q08 · CQ8 · Правила верифікації, формалізовані з досвіду фактчекерів
// Які правила верифікації сформульовано на основі досвіду кожного фактчекера?
MATCH (f:FactChecker)
OPTIONAL MATCH (f)-[:FORMALIZED_IN]->(r:Rule)
RETURN f.name AS checker, collect(r.id) AS rules, count(r) AS n
ORDER BY n DESC, checker;
