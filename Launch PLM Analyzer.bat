@echo off
title PLM Log Analyzer - Launching...
color 0A

echo.
echo ========================================
echo    PLM Log Analyzer - Launch Tool
echo ========================================
echo.

echo Checking if Python is available...
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.7+ and try again
    pause
    exit /b 1
)

echo Python found! Checking Flask installation...
python -c "import flask" >nul 2>&1
if errorlevel 1 (
    echo Installing Flask and dependencies...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo ERROR: Failed to install dependencies
        pause
        exit /b 1
    )
    echo Dependencies installed successfully!
)

echo.
echo Starting PLM Log Analyzer...
echo.
echo ========================================
echo    Application will open in browser
echo    URL: http://localhost:5000
echo ========================================
echo.
echo Press Ctrl+C to stop the server when done
echo.

start http://localhost:5000
python app.py

echo.
echo Application stopped.
pause
