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
echo LR14: Neo4j migration + LLM judge + RAG eval (about 20-25 min) ... log: logs\lab14_run.log
"%PY%" -u src\pc_run.py all > ..\logs\lab14_run.log 2>&1
echo DONE (exit %ERRORLEVEL%) >> ..\logs\lab14_run.log
echo Finished. You can close this window.
