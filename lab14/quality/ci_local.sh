#!/usr/bin/env bash
# ЛР14 · локальний прогін gate (еквівалент CI): baseline → clean → 3 дефекти. Лог: quality/reports/gate_log.txt
cd "$(dirname "$0")/.."
rm -rf quality/reports && mkdir -p quality/reports
{
  echo "\$ python quality/gate.py --version baseline"; python3 quality/gate.py --version baseline --label "baseline kb-2026.11-v0 (до очищення)" 2>&1 | grep -E "^GATE|✗"; echo "exit=${PIPESTATUS[0]}"
  echo "\$ python quality/gate.py --version clean";    python3 quality/gate.py --version clean --label "clean kb-2026.11-v1 (після очищення)" 2>&1 | grep -E "^GATE|✗"; echo "exit=${PIPESTATUS[0]}"
  python3 quality/defects.py >/dev/null
  echo "\$ python quality/gate.py --kb-dir data/defects"; python3 quality/gate.py --kb-dir data/defects --label "3 навмисні дефекти (D-1, D-2, D-3)" 2>&1 | grep -E "^GATE|✗"; echo "exit=${PIPESTATUS[0]}"
} | sed -E 's/(.{0,170}).*/\1/' > quality/reports/gate_log.txt
cat quality/reports/gate_log.txt
