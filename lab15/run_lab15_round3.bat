@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set HF_HOME=F:\kms_tools\hf
set HF_HUB_OFFLINE=1
set OLLAMA_MODELS=F:\kms_tools\ollama-models
set PY=F:\kms_tools\venv\Scripts\python.exe
echo LR15 round 3 (about 15 min). Log: logs\lab15_round3.log
echo [1/3] diagnostics: why e5 (sentence-transformers) does not load > ..\logs\lab15_round3.log
"%PY%" -c "import transformers, torch; print('transformers', transformers.__version__, 'torch', torch.__version__); from transformers import PreTrainedModel; print('PreTrainedModel OK')" >> ..\logs\lab15_round3.log 2>&1
"%PY%" -m pip check >> ..\logs\lab15_round3.log 2>&1
"%PY%" -m pip list >> ..\logs\lab15_round3.log 2>&1
echo [2/3] scenarios v3 >> ..\logs\lab15_round3.log
"%PY%" -u agent\run_eval.py scenarios --version v3 --tag r3 >> ..\logs\lab15_round3.log 2>&1
echo [3/3] finish attacks BEFORE defenses (A08..R04) >> ..\logs\lab15_round3.log
"%PY%" -u agent\run_eval.py attacks --profile permissive --version v2 --tag before_v2 >> ..\logs\lab15_round3.log 2>&1
echo DONE >> ..\logs\lab15_round3.log
echo Finished. You can close this window.
