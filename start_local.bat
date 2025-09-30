@echo off
chcp 65001 >nul
cd /d "%~dp0"

REM Load AWS credentials from file
if exist "aws_credentials.txt" (
    echo Loading AWS credentials...
    for /f "tokens=1,2 delims==" %%a in (aws_credentials.txt) do (
        set %%a=%%b
    )
    echo AWS credentials loaded.
) else (
    echo aws_credentials.txt not found!
    pause
    exit /b 1
)

cd server
echo Starting AWS backend server...
if exist "..\venv\Scripts\python.exe" (
    "..\venv\Scripts\python.exe" -m uvicorn aws_backend:app --host 0.0.0.0 --port 80
) else (
    python -m uvicorn aws_backend:app --host 0.0.0.0 --port 80
)
pause
