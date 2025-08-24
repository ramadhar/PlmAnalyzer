@echo off
REM Launch PLM Log Analyzer in AI (semantic) mode.
REM Ensures extended AI dependencies are installed and sets PLM_AI=1 for optional feature flags.

SETLOCAL ENABLEDELAYEDEXPANSION
SET SCRIPT_DIR=%~dp0
PUSHD "%SCRIPT_DIR%.."

IF EXIST venv\Scripts\activate.bat (
  CALL venv\Scripts\activate.bat
)

REM Ensure base + AI requirements installed (quiet-ish)
python -c "import flask" 1>NUL 2>NUL || pip install -r requirements.txt
python -c "import sentence_transformers" 1>NUL 2>NUL || pip install -r requirements-ai.txt

SET PLM_AI=1
echo Starting PLM Log Analyzer (AI Mode) on http://localhost:5000 ...
start "PLM Log Analyzer (AI)" python app.py
START "" "http://localhost:5000/"
POPD
ENDLOCAL
