@echo off
title JonBranding Platform Server Mode
cd /d "C:\Users\baxti\playground\oisha-os"

echo ===============================================
echo   SETTING UP SERVER ENVIRONMENT...
echo ===============================================

:: Prevent Sleep
powercfg /requestsoverride process python.exe display system awaymode >nul 2>&1
powercfg /requestsoverride process node.exe display system awaymode >nul 2>&1
powercfg /x -standby-timeout-ac 0 >nul 2>&1

:: 1. Start Oisha-OS Bot
echo [1/2] Starting Oisha-OS Bot...
if exist .venv_oi\Scripts\activate.bat (
    call .venv_oi\Scripts\activate.bat
)
start "Oisha Bot" /b pythonw src/main.py
start "Oisha Watchdog" /b pythonw src/services/watchdog.py

:: 2. Start JonBranding Website
echo [2/2] Starting JonBranding Website (Port 9002)...
cd /d "c:\Users\baxti\.gemini\antigravity\playground\jonbranding-veb-sayti"
start "JonBranding Web" /b npm run dev

echo   PLATFORM IS NOW LIVE ON LOCAL SERVER
echo   Oisha Bot: Running in background
echo   Website:   http://localhost:9002
echo   Dashboard: http://localhost:8080/static/dashboard.html
echo.
echo   Press any key to keep this server window open.
echo ===============================================
pause
