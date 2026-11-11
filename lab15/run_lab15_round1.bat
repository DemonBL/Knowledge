@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set HF_HOME=F:\kms_tools\hf
set HF_HUB_OFFLINE=1
set OLLAMA_MODELS=F:\kms_tools\ollama-models
set PY=F:\kms_tools\venv\Scripts\python.exe
if not exist ..\logs mkdir ..\logs
if not exist results mkdir results
echo LR15 round 1 (about 25-30 min). Log: logs\lab15_round1.log
echo [1/5] install langgraph, mcp ... > ..\logs\lab15_round1.log
"%PY%" -m pip install -q langgraph mcp pyshacl rdflib pyyaml sqlglot duckdb >> ..\logs\lab15_round1.log 2>&1
echo [2/5] smoke test tools >> ..\logs\lab15_round1.log
"%PY%" -u agent\tools.py >> ..\logs\lab15_round1.log 2>&1
echo [3/5] red team (gemma3:4b) >> ..\logs\lab15_round1.log
"%PY%" -u agent\run_eval.py redteam >> ..\logs\lab15_round1.log 2>&1
echo [4/5] scenarios v1 >> ..\logs\lab15_round1.log
"%PY%" -u agent\run_eval.py scenarios --version v1 --tag r1 >> ..\logs\lab15_round1.log 2>&1
echo [5/5] attacks BEFORE defenses >> ..\logs\lab15_round1.log
"%PY%" -u agent\run_eval.py attacks --profile permissive --tag before >> ..\logs\lab15_round1.log 2>&1
"%PY%" -u mcp_server\demo_client.py >> ..\logs\lab15_round1.log 2>&1
echo DONE >> ..\logs\lab15_round1.log
echo Finished. You can close this window.
