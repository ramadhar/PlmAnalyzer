@echo off
REM Launch PLM Log Analyzer (Flask) in a dedicated window.
REM Adjust PYTHON path or virtual environment activation below if needed.

SETLOCAL ENABLEDELAYEDEXPANSION
SET SCRIPT_DIR=%~dp0
PUSHD "%SCRIPT_DIR%.."

REM Optional: activate venv if exists (./venv)
IF EXIST venv\Scripts\activate.bat (
  CALL venv\Scripts\activate.bat
)

REM Install dependencies if flask not found (first run convenience)
python -c "import flask" 2>NUL 1>NUL
IF NOT %ERRORLEVEL%==0 (
  echo [INFO] Installing base dependencies...
  pip install -r requirements.txt >NUL
)

REM Launch the app
echo Starting PLM Log Analyzer on http://localhost:5000 ...
start "PLM Log Analyzer" python app.py

REM Optionally open browser automatically
START "" "http://localhost:5000/"
POPD
ENDLOCAL
