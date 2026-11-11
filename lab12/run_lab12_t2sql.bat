@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
if not exist ..\logs mkdir ..\logs
set LOG=..\logs\lab12_t2sql.log
echo [1/2] Installing duckdb, sqlglot, pyyaml, pyarrow into F:\kms_tools\venv ...
"F:\kms_tools\venv\Scripts\python.exe" -m pip install -q duckdb==2.0.0 sqlglot==30.29.0 pyyaml pyarrow > %LOG% 2>&1 || "F:\kms_tools\venv\Scripts\python.exe" -m pip install -q duckdb sqlglot pyyaml pyarrow >> %LOG% 2>&1
echo [2/2] Text-to-SQL evaluation with qwen2.5:7b (Ollama), ~5-10 min ...
"F:\kms_tools\venv\Scripts\python.exe" -u t2sql\t2sql.py --model qwen2.5:7b >> %LOG% 2>&1
echo DONE (exit %ERRORLEVEL%) >> %LOG%
type %LOG%
echo Finished. You can close this window.
pause
