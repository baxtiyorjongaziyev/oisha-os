@echo off
title Oisha-OS Server Mode
cd /d "C:\Users\baxti\playground\oisha-os"

echo Setting Power Scheme to High Performance (Server Mode)...
powercfg /requestsoverride process python.exe display system awaymode
powercfg /x -standby-timeout-ac 0

if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
)

set PYTHONPATH=.
set PYTHONIOENCODING=utf-8

echo Starting Oisha-OS Main Service...
start "" /b python -u src/main.py > bot_startup.log 2>&1

echo Starting Self-Healing Watchdog (Self-Healing)...
start "" /b python -u src/services/watchdog.py > watchdog_startup.log 2>&1

echo.
echo ===============================================
echo   OISHA-OS SERVER IS NOW RUNNING LOCALLY
echo   Do not close this window to keep server alive.
echo ===============================================
pause
