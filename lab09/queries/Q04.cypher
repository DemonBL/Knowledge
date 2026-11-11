// Q04 · CQ4 · Повторно використані медіафайли (правило RULE-4)
// Які публікації містять медіафайли, зняті більш ніж на 7 днів раніше за публікацію, і чим це виявлено?
MATCH (p:Publication)-[:CONTAINS]->(m:Media)
WHERE m.exifDate < p.publishedAt - duration({days: 7})
OPTIONAL MATCH (m)-[:VERIFIED_WITH]->(t:Tool)
RETURN p.id AS publication, m.id AS media, m.exifDate AS shot, p.publishedAt AS published,
       duration.inDays(m.exifDate, p.publishedAt).days AS ageDays, collect(t.name) AS tools
ORDER BY ageDays DESC;
