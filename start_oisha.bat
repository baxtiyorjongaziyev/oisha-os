@echo off
cd /d "C:\Users\baxti\playground\oisha\os"
if exist .venv\Scripts\activate.bat (
    call .venv\Scripts\activate.bat
)
start "" /b pythonw src/main.py
