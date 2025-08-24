@echo off
echo Starting PLM Log Analyzer...
echo.
echo Installing dependencies...
pip install -r requirements.txt
echo.
echo Starting the web application...
echo.
echo The application will be available at: http://localhost:5000
echo Press Ctrl+C to stop the server
echo.
python app.py
pause
