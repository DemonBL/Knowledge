@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set HF_HOME=F:\kms_tools\hf
set HF_HUB_OFFLINE=1
set OLLAMA_MODELS=F:\kms_tools\ollama-models
set PY=F:\kms_tools\venv\Scripts\python.exe
if not exist ..\logs mkdir ..\logs
echo LR11 API demo ... log: logs\lab11_api.log
"%PY%" -u api\api_demo.py > ..\logs\lab11_api.log 2>&1
echo DONE (exit %ERRORLEVEL%) >> ..\logs\lab11_api.log
