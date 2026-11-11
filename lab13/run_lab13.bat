@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
if not exist ..\logs mkdir ..\logs
set LOG=..\logs\lab13_run.log
echo [1/2] Annotator B (gemma3:4b), 42 items, ~5 min ... > %LOG%
echo [1/2] Annotator B (gemma3:4b), 42 items, ~5 min ...
"F:\kms_tools\venv\Scripts\python.exe" -u annotation\annotate_b.py >> %LOG% 2>&1
echo [2/2] Method B: qwen2.5:7b on dev (2 prompts) + test, ~80 min ...
"F:\kms_tools\venv\Scripts\python.exe" -u src\extract_llm.py --stage all --model qwen2.5:7b >> %LOG% 2>&1
echo DONE (exit %ERRORLEVEL%) >> %LOG%
type %LOG%
echo Finished. You can close this window.
pause
