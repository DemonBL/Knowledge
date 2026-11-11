@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set OLLAMA_MODELS=F:\kms_tools\ollama-models
if not exist ..\logs mkdir ..\logs
echo Text-to-Cypher v1 and v2 ... logs: logs\lab09_t2c.log, logs\lab09_t2c_v2.log
"F:\kms_tools\venv\Scripts\python.exe" -u src\t2c.py v1 > ..\logs\lab09_t2c.log 2>&1
"F:\kms_tools\venv\Scripts\python.exe" -u src\t2c.py v2 > ..\logs\lab09_t2c_v2.log 2>&1
echo DONE >> ..\logs\lab09_t2c_v2.log
