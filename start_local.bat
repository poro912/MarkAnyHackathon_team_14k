@echo off
echo ========================================
echo    Windows Local Server Start
echo ========================================

cd /d "%~dp0server"

echo Installing packages...
pip install fastapi uvicorn python-multipart

echo Checking compiler...
g++ --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Warning: g++ compiler not found.
    echo Install MinGW: https://www.mingw-w64.org/downloads/
)

echo Starting local server...
python local_backend.py

pause