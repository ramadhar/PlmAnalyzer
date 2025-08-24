# PLM Log Analyzer - Offline PowerShell Launcher
# Right-click and select "Run with PowerShell" if you get execution policy errors

Write-Host "========================================" -ForegroundColor Green
Write-Host "   PLM Log Analyzer - Offline Version" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

# Check if Python is available
try {
    $pythonVersion = python --version 2>&1
    Write-Host "✓ Python found: $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "✗ ERROR: Python is not installed or not in PATH" -ForegroundColor Red
    Write-Host "Please install Python 3.7+ and try again" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

# Check if Flask is installed
try {
    python -c "import flask" 2>$null
    Write-Host "✓ Flask is already installed" -ForegroundColor Green
} catch {
    Write-Host "Dependencies not found. Installing from local files..." -ForegroundColor Yellow
    try {
        python install_dependencies.py
        Write-Host "✓ Dependencies installed successfully!" -ForegroundColor Green
    } catch {
        Write-Host "✗ ERROR: Failed to install dependencies" -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
}

Write-Host ""
Write-Host "Starting PLM Log Analyzer..." -ForegroundColor Cyan
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "   Application will open in browser" -ForegroundColor Green
Write-Host "   URL: http://localhost:5000" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Press Ctrl+C to stop the server when done" -ForegroundColor Yellow
Write-Host ""

# Open browser
Start-Process "http://localhost:5000"

# Start Flask application
python app.py

Write-Host ""
Write-Host "Application stopped." -ForegroundColor Yellow
Read-Host "Press Enter to exit"
