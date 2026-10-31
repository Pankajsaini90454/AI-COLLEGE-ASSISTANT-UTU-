@echo off
title AI College Assistant
cd /d "%~dp0"

echo ==============================================
echo        Starting AI College Assistant
echo ==============================================

:: Check if Docker container is running (optional, won't crash if docker is already active)
where docker >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    echo [1/3] Ensuring PostgreSQL database container is active...
    docker-compose up -d >nul 2>nul
)

:: Wait 1 second then open browser
echo [2/3] Launching web assistant in your default browser...
start "" http://127.0.0.1:8000/chat

:: Launch FastAPI server using project virtual environment
echo [3/3] Starting backend server (main.py)...
echo ----------------------------------------------
echo Press CTRL+C at any time to stop the server.
echo ----------------------------------------------
.\myenv\Scripts\python.exe main.py

pause
