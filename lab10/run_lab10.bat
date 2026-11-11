@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set HF_HOME=F:\kms_tools\hf
set HF_HUB_OFFLINE=1
set PY=F:\kms_tools\venv\Scripts\python.exe
if not exist ..\logs mkdir ..\logs
echo LR10: corpus -> gold -> indexes/eval ... log: logs\lab10_run.log
"%PY%" -u src\build_corpus.py > ..\logs\lab10_run.log 2>&1
"%PY%" -u eval\make_gold.py >> ..\logs\lab10_run.log 2>&1
"%PY%" -u src\run_lab10.py >> ..\logs\lab10_run.log 2>&1
echo DONE (exit %ERRORLEVEL%) >> ..\logs\lab10_run.log
