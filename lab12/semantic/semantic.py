"""ЛР12 · семантичний шар: генерація SQL за назвою метрики з semantic/metrics.yml.

    from semantic.semantic import SemanticLayer
    sl = SemanticLayer()
    print(sl.metric_sql(["false_verdict_rate"], ["signal_class"], {"month": [8, 9]}))
Метрики, виміри й фільтри беруться лише з каталогу (білий список) — довільний SQL у запит не потрапляє."""
from pathlib import Path
import duckdb
import yaml

ROOT = Path(__file__).resolve().parents[1]


class SemanticLayer:
    def __init__(self, path=ROOT / "semantic" / "metrics.yml", db=ROOT / "data" / "lab12.duckdb"):
        self.spec = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
        self.metrics = {m["name"]: m for m in self.spec["metrics"]}
        self.dims = self.spec["dimensions"]
        self.db = db
        for m in self.metrics.values():   # обов'язкові поля метрики
            missing = {"name", "definition", "formula", "unit", "owner", "sources", "constraints", "review_date", "status"} - set(m)
            assert not missing, f"{m['name']}: немає полів {missing}"

    @staticmethod
    def _lit(v):
        return str(v) if isinstance(v, (int, float)) else "'" + str(v).replace("'", "''") + "'"

    def metric_sql(self, metrics, dimensions=(), filters=None, order_by=None, limit=None):
        for x in metrics:
            if x not in self.metrics: raise KeyError(f"невідома метрика: {x}")
        for x in list(dimensions) + list((filters or {}).keys()):
            if x not in self.dims: raise KeyError(f"невідомий вимір: {x}")
        joins = []
        need = [j for x in metrics for j in self.metrics[x].get("joins", [])] + \
               [self.dims[x]["join"] for x in list(dimensions) + list((filters or {}).keys())]
        for j in need:
            if j and j not in joins: joins.append(j)
        sel = [f"{self.dims[x]['column']} AS {x}" for x in dimensions] + [f"{self.metrics[x]['formula']} AS {x}" for x in metrics]
        where = []
        for x, v in (filters or {}).items():
            col = self.dims[x]["column"]
            where.append(f"{col} IN ({', '.join(self._lit(i) for i in v)})" if isinstance(v, (list, tuple)) else f"{col} = {self._lit(v)}")
        sql = f"SELECT {', '.join(sel)}\nFROM {self.spec['base_table']}"
        sql += "".join(f"\n{self.spec['joins'][j]}" for j in joins)
        if where: sql += "\nWHERE " + " AND ".join(where)
        if dimensions: sql += "\nGROUP BY " + ", ".join(str(i + 1) for i in range(len(dimensions)))
        if order_by: sql += f"\nORDER BY {order_by}"
        elif dimensions: sql += "\nORDER BY " + ", ".join(str(i + 1) for i in range(len(dimensions)))
        if limit: sql += f"\nLIMIT {int(limit)}"
        return sql

    def query(self, *a, **kw):
        con = duckdb.connect(str(self.db), read_only=True)
        try:
            return con.execute(self.metric_sql(*a, **kw)).df()
        finally:
            con.close()

    def catalog_text(self):
        """Компактний опис для підказки LLM (text-to-SQL)."""
        lines = ["Метрики (використовуй формули дослівно):"]
        for m in self.metrics.values():
            lines.append(f"- {m['name']} ({m['unit']}): {m['definition']} Формула: {m['formula']}; потрібні join: {m.get('joins') or 'немає'}")
        lines.append("Виміри (колонка ← join):")
        for k, d in self.dims.items():
            lines.append(f"- {k}: {d['column']} — {d['description']}")
        lines.append("З'єднання:")
        lines += [f"- {k}: {v}" for k, v in self.spec["joins"].items()]
        return "\n".join(lines)


if __name__ == "__main__":
    sl = SemanticLayer()
    print(sl.metric_sql(["false_verdict_rate", "checks_count"], ["signal_class"], {"month": [8, 9]}))
    print(sl.query(["false_verdict_rate", "checks_count"], ["signal_class"]))
