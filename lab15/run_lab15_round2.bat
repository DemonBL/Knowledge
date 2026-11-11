@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set HF_HOME=F:\kms_tools\hf
set HF_HUB_OFFLINE=1
set OLLAMA_MODELS=F:\kms_tools\ollama-models
set PY=F:\kms_tools\venv\Scripts\python.exe
echo LR15 round 2 (about 20-25 min). Log: logs\lab15_round2.log
echo [1/5] re-pin approved tool manifests > ..\logs\lab15_round2.log
"%PY%" -u agent\tools.py >> ..\logs\lab15_round2.log 2>&1
echo [2/5] scenarios v2 (after fixes) >> ..\logs\lab15_round2.log
"%PY%" -u agent\run_eval.py scenarios --version v2 --tag r2 >> ..\logs\lab15_round2.log 2>&1
echo [3/5] attacks BEFORE defenses, agent v2 >> ..\logs\lab15_round2.log
"%PY%" -u agent\run_eval.py attacks --profile permissive --version v2 --tag before_v2 >> ..\logs\lab15_round2.log 2>&1
echo [4/5] attacks AFTER defenses, agent v2 >> ..\logs\lab15_round2.log
"%PY%" -u agent\run_eval.py attacks --profile strict --version v2 --tag after >> ..\logs\lab15_round2.log 2>&1
echo [5/5] human-in-the-loop demo >> ..\logs\lab15_round2.log
"%PY%" -u agent\propose_fact.py demo >> ..\logs\lab15_round2.log 2>&1
echo.
echo =====================================================================
echo  HUMAN-IN-THE-LOOP: you will see 2 proposals.
echo  Proposal 1 (MEDIUM risk, StopFake - Facebook partnership): answer y
echo  Proposal 2 (HIGH risk, change of verdict VRD-28): answer n
echo =====================================================================
"%PY%" -u agent\hitl_review.py
"%PY%" -u agent\propose_fact.py metrics >> ..\logs\lab15_round2.log 2>&1
echo DONE >> ..\logs\lab15_round2.log
echo Finished. You can close this window.
pause
