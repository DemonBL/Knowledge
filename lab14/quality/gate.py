"""ЛР14 · локальний quality gate (те саме запускає CI: .github/workflows/quality.yml).

Запускає 19 перевірок (SHACL, SPARQL, pytest/GE-стиль, JSON Schema) для версії сховища,
пише звіт за правилами, додає рядок у тренд і повертає код 1, якщо впала хоч одна critical-перевірка.
  python quality/gate.py --version clean [--label "опис запуску"]
  python quality/gate.py --kb-dir data/defects --label "3 навмисні дефекти"
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import pytest

Q = Path(__file__).resolve().parent
LAB = Q.parent
REP = Q / "reports"


class Collector:
    def __init__(self):
        self.rows = []

    def pytest_runtest_logreport(self, report):
        if report.when == "call" or (report.when == "setup" and report.outcome != "passed"):
            marks = set(report.keywords)
            sev = "critical" if "critical" in marks else ("warning" if "warning" in marks else "critical")
            msg = ""
            if report.failed:
                msg = str(report.longrepr.reprcrash.message if hasattr(report.longrepr, "reprcrash") else report.longrepr)
                msg = msg.split("\n")[0][:300]
            name = report.nodeid.split("::")[-1]
            self.rows.append(dict(check=name.split("_")[1], test=name, file=report.nodeid.split("::")[0].split("/")[-1],
                                  severity=sev, outcome=report.outcome, message=msg))


def tool_of(f):
    return {"test_shacl.py": "SHACL (pySHACL)", "test_sparql.py": "SPARQL-інваріант (rdflib)",
            "test_data.py": "pytest / GE-очікування", "test_schema.py": "JSON Schema"}.get(f, f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default="clean")
    ap.add_argument("--kb-dir")
    ap.add_argument("--label", default="")
    a = ap.parse_args()
    os.environ["KB_VERSION"] = a.version
    if a.kb_dir:
        os.environ["KB_DIR"] = str((LAB / a.kb_dir).resolve() if not Path(a.kb_dir).is_absolute() else a.kb_dir)
    for m in [m for m in sys.modules if m in ("kb", "conflicts")]:
        del sys.modules[m]
    col = Collector()
    t0 = time.perf_counter()
    pytest.main(["-q", "-p", "no:cacheprovider", str(Q / "tests")], plugins=[col])
    dt = round(time.perf_counter() - t0, 2)
    rows = col.rows
    for r in rows:
        r["tool"] = tool_of(r["file"])
    crit_fail = [r for r in rows if r["outcome"] == "failed" and r["severity"] == "critical"]
    warn_fail = [r for r in rows if r["outcome"] == "failed" and r["severity"] == "warning"]
    status = "BLOCKED" if crit_fail else "PASSED"
    REP.mkdir(exist_ok=True)
    trend = REP / "trend.csv"
    n = sum(1 for _ in open(trend, encoding="utf-8")) if trend.exists() else 1
    ts = datetime.now().astimezone().isoformat(timespec="seconds")
    run = dict(run=n, ts=ts, version=a.kb_dir or a.version, label=a.label, status=status, checks=len(rows),
               passed=sum(r["outcome"] == "passed" for r in rows), failed_critical=len(crit_fail),
               failed_warning=len(warn_fail), skipped=sum(r["outcome"] == "skipped" for r in rows), seconds=dt)
    new = not trend.exists()
    with open(trend, "a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(run))
        if new:
            w.writeheader()
        w.writerow(run)
    out = dict(run=run, results=rows)
    (REP / f"gate_run{n:02d}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    # markdown-звіт: останній запуск + тренд
    L = [f"# Quality gate · запуск {n} · {run['version']} · **{status}**", "", f"{a.label}", "",
         f"Час: {ts}; перевірок: {run['checks']}; пройдено: {run['passed']}; critical-порушень: {run['failed_critical']}; "
         f"попереджень: {run['failed_warning']}; пропущено: {run['skipped']}; {dt} с.", "",
         "| Перевірка | Інструмент | Критичність | Результат | Порушення |", "|---|---|---|---|---|"]
    for r in rows:
        icon = {"passed": "✅", "failed": "❌" if r["severity"] == "critical" else "⚠️", "skipped": "—"}[r["outcome"]]
        L.append(f"| {r['test']} | {r['tool']} | {r['severity']} | {icon} | {r['message'].replace('|', '/')} |")
    L += ["", "## Тренд", "", "| Запуск | Версія | Мітка | Статус | Пройдено | Critical | Warning |", "|---|---|---|---|---|---|---|"]
    for t in csv.DictReader(open(trend, encoding="utf-8")):
        L.append(f"| {t['run']} | {t['version']} | {t['label']} | {t['status']} | {t['passed']}/{t['checks']} | {t['failed_critical']} | {t['failed_warning']} |")
    (REP / "gate_report.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"GATE {status}: {run['passed']}/{run['checks']} passed, critical={run['failed_critical']}, warning={run['failed_warning']}")
    for r in crit_fail:
        print("  ✗", r["test"], "—", r["message"][:160])
    sys.exit(1 if crit_fail else 0)


if __name__ == "__main__":
    main()
