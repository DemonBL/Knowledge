// Q03 · CQ3 · Вердикт щодо кожного твердження; незавершені перевірки
// Який вердикт винесено щодо кожного твердження з високим пріоритетом і які ще не перевірені?
MATCH (c:Claim {priority: 'високий'})
OPTIONAL MATCH (c)<-[:ABOUT]-(v:Verdict)<-[:ISSUED]-(f:FactChecker)
WITH c, v, f
RETURN CASE WHEN v IS NULL THEN 'очікує перевірки' ELSE v.category END AS status,
       count(c) AS claims, collect(c.id)[..8] AS examples
ORDER BY claims DESC;
