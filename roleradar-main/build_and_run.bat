@echo off
REM Tech Jobs Crawler - Build and Run Script
REM Run this script to build and start the application

echo ================================================
echo  Tech Company Web Crawler & Job Tracker
echo  Build Script for Windows
echo ================================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed. Please install Python 3.11+ first.
    echo Download from: https://python.org/downloads/
    pause
    exit /b 1
)

echo [OK] Python found

REM Get script directory
set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

REM Create virtual environment if it doesn't exist
if not exist "%SCRIPT_DIR%venv" (
    echo.
    echo [1/5] Creating virtual environment...
    python -m venv venv
    echo [OK] Virtual environment created
) else (
    echo [OK] Virtual environment already exists
)

REM Activate virtual environment
echo.
echo [2/5] Activating virtual environment...
call venv\Scripts\activate.bat
echo [OK] Virtual environment activated

REM Install dependencies
echo.
echo [3/5] Installing Python dependencies...
pip install -r requirements.txt >nul 2>&1
if errorlevel 1 (
    echo [WARNING] Some dependencies may have failed. Trying with verbose output...
    pip install -r requirements.txt
)
echo [OK] Dependencies installed

REM Download NLP models
echo.
echo [4/5] Downloading NLP models...
python -c "import spacy; spacy.cli.download('en_core_web_sm')" >nul 2>&1
echo [OK] NLP models ready

REM Check database connection
echo.
echo [5/5] Checking database connection...
python -c "from backend.database import db_manager; db_manager.connect(); db_manager.close(); print('[OK] Database connection successful')" 2>nul
if errorlevel 1 (
    echo [WARNING] Database connection failed. Please check config.yaml and ensure MySQL is running.
    echo.
    echo Database setup:
    echo  1. Install MySQL 8.0+
    echo  2. Create database: CREATE DATABASE tech_jobs_db;
    echo  3. Import schema: mysql -u root -p < database\schema.sql
)

echo.
echo ================================================
echo  Build Complete!
echo ================================================
echo.
echo Options:
echo  1) Start API Server (http://localhost:8000)
echo  2) Start Frontend Only
echo  3) Run Crawler Only
echo  4) Run Tests
echo  5) Exit
echo.

set /p choice="Enter your choice (1-5): "

if "%choice%"=="1" (
    echo.
    echo Starting API Server...
    echo Open http://localhost:8000/docs for API documentation
    cd backend
    python main.py
) else if "%choice%"=="2" (
    echo.
    echo Opening frontend...
    start "" "%SCRIPT_DIR%frontend\index.html"
) else if "%choice%"=="3" (
    echo.
    echo Starting crawler...
    python -m crawler.distributed_crawler
) else if "%choice%"=="4" (
    echo.
    echo Running tests...
    pytest tests/ -v
) else (
    echo.
    echo Exiting...
)

pause
