# Tech Jobs Crawler - Startup Script

Write-Host "======================================" -ForegroundColor Cyan
Write-Host "  Tech Company Web Crawler & Job Tracker" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

# Change to project directory
Set-Location "D:\7"

# Check if venv exists
if (-not (Test-Path ".\venv")) {
    Write-Host "[1/5] Creating virtual environment..." -ForegroundColor Yellow
    python -m venv venv
    Write-Host "[OK] Virtual environment created" -ForegroundColor Green
} else {
    Write-Host "[OK] Virtual environment exists" -ForegroundColor Green
}

# Activate virtual environment and install dependencies
Write-Host ""
Write-Host "[2/5] Installing dependencies..." -ForegroundColor Yellow

$pipPath = ".\venv\Scripts\pip.exe"
& $pipPath install --quiet fastapi uvicorn sqlalchemy mysql-connector-python spacy requests aiohttp beautifulsoup4 lxml redis httpx python-multipart pydantic pyyaml 2>&1

if ($LASTEXITCODE -eq 0) {
    Write-Host "[OK] Dependencies installed" -ForegroundColor Green
} else {
    Write-Host "[WARNING] Some dependencies may have issues" -ForegroundColor Yellow
}

# Download NLP model
Write-Host ""
Write-Host "[3/5] Downloading NLP model..." -ForegroundColor Yellow
python -c "import spacy; spacy.cli.download('en_core_web_sm')" 2>&1 | Out-Null
Write-Host "[OK] NLP model ready" -ForegroundColor Green

# Start backend in background
Write-Host ""
Write-Host "[4/5] Starting backend API server..." -ForegroundColor Yellow
Write-Host "API will be available at: http://localhost:8000" -ForegroundColor Cyan
Write-Host "API Documentation: http://localhost:8000/docs" -ForegroundColor Cyan

$backendJob = Start-Process -FilePath "python" -ArgumentList "main.py" -WorkingDirectory "D:\7\backend" -PassThru -NoNewWindow

# Open frontend
Write-Host ""
Write-Host "[5/5] Opening frontend..." -ForegroundColor Yellow
Start-Process "D:\7\frontend\index.html"

Write-Host ""
Write-Host "======================================" -ForegroundColor Cyan
Write-Host "  Project is now running!" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "API Server: http://localhost:8000" -ForegroundColor Green
Write-Host "Frontend:   Opened in browser" -ForegroundColor Green
Write-Host ""
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
