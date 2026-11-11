@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set HF_HOME=F:\kms_tools\hf
set HF_HUB_OFFLINE=1
set OLLAMA_MODELS=F:\kms_tools\ollama-models
set PY=F:\kms_tools\venv\Scripts\python.exe
if not exist logs mkdir logs
echo LR16: e5 vectors + eval + LLM explanations + Docker Compose from scratch + demo (about 15-20 min)
echo Docker Desktop must be running. Log: lab16\logs\lab16_run.log
"%PY%" -u src\pc_run.py all > logs\lab16_run.log 2>&1
echo DONE (exit %ERRORLEVEL%) >> logs\lab16_run.log
echo Finished. UI: http://127.0.0.1:8501  API: http://127.0.0.1:8000/docs
pause
