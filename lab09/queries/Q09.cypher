// Q09 · CQ9 · Найкоротший шлях від першоджерела до звичайних користувачів
// Через скільки кроків контент анонімного каналу ACC-005 доходить до звичайних користувачів?
MATCH (src:Account {id: 'ACC-005'}), (u:Account {kind: 'користувач'})
MATCH path = shortestPath((src)-[:PUBLISHED|DERIVED_FROM*..10]-(u))
RETURN u.id AS user, u.name AS name, length(path) AS hops,
       [x IN nodes(path) | x.id] AS route
ORDER BY hops, user LIMIT 5;
