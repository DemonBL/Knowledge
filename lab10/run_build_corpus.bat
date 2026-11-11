@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
if not exist ..\logs mkdir ..\logs
set PY=python
if exist "F:\kms_tools\venv\Scripts\python.exe" set PY=F:\kms_tools\venv\Scripts\python.exe
echo Building corpus (Wikipedia uk + internal docs) ... log: logs\lab10_build_corpus.log
"%PY%" -u src\build_corpus.py > ..\logs\lab10_build_corpus.log 2>&1
echo DONE (exit %ERRORLEVEL%) >> ..\logs\lab10_build_corpus.log
