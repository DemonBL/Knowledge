@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set PY=F:\kms_tools\venv\Scripts\python.exe
if not exist logs mkdir logs
echo LR16: Docker Compose from scratch + demo only (about 8-10 min). Docker Desktop must be running.
echo Log: lab16\logs\lab16_docker.log
"%PY%" -u src\pc_run.py docker > logs\lab16_docker.log 2>&1
echo DONE (exit %ERRORLEVEL%) >> logs\lab16_docker.log
echo Finished. UI: http://127.0.0.1:8501  API: http://127.0.0.1:8000/docs
pause
