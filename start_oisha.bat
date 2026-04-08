@echo off
title Oisha-OS Server Mode
cd /d "C:\Users\baxti\playground\oisha-os"

echo Setting Power Scheme to High Performance (Server Mode)...
powercfg /requestsoverride process python.exe display system awaymode
powercfg /x -standby-timeout-ac 0

if exist .venv_oi\Scripts\activate.bat (
    call .venv_oi\Scripts\activate.bat
)

echo Starting Oisha-OS Main Service...
start "" /b pythonw src/main.py

echo Starting Self-Healing Watchdog (Self-Healing)...
start "" /b pythonw src/services/watchdog.py

echo.
echo ===============================================
echo   OISHA-OS SERVER IS NOW RUNNING LOCALLY
echo   Do not close this window to keep server alive.
echo ===============================================
pause
