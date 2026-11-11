@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set HF_HOME=F:\kms_tools\hf
set OLLAMA_MODELS=F:\kms_tools\ollama-models
if not exist ..\logs mkdir ..\logs
echo Running t2c.py v2 ... log: logs\lab09_t2c_v2.log
"F:\kms_tools\venv\Scripts\python.exe" -u src\t2c.py v2 > ..\logs\lab09_t2c_v2.log 2>&1
echo DONE (exit %ERRORLEVEL%) >> ..\logs\lab09_t2c_v2.log
echo Finished. You can close this window.
