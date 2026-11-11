@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set LOG=..\logs\lab13_kappa.log
echo Annotator B (gemma3:4b), 42 items, ~5 min ...
"F:\kms_tools\venv\Scripts\python.exe" -u annotation\annotate_b.py > %LOG% 2>&1
echo DONE (exit %ERRORLEVEL%) >> %LOG%
type %LOG%
echo Finished. You can close this window.
pause
