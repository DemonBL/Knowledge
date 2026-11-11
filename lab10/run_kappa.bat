@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set HF_HOME=F:\kms_tools\hf
set HF_HUB_OFFLINE=1
set OLLAMA_MODELS=F:\kms_tools\ollama-models
set PY=F:\kms_tools\venv\Scripts\python.exe
if not exist ..\logs mkdir ..\logs
echo LR10 kappa (gemma3 annotator) ... log: logs\lab10_kappa.log
"%PY%" -u eval\kappa.py > ..\logs\lab10_kappa.log 2>&1
echo DONE (exit %ERRORLEVEL%) >> ..\logs\lab10_kappa.log
