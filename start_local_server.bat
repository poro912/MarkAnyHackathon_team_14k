@echo off
echo ========================================
echo    로컬 환경에서 서버 시작 (AWS 없음)
echo ========================================

cd /d "%~dp0server"

REM 필요한 패키지 설치
echo 패키지 설치 중...
pip install fastapi uvicorn python-multipart

REM 컴파일러 확인
echo 컴파일러 확인 중...
g++ --version >nul 2>&1
if %errorlevel% neq 0 (
    echo 경고: g++ 컴파일러가 설치되지 않았습니다.
    echo MinGW 또는 Visual Studio Build Tools를 설치하세요.
)

REM 로컬 서버 시작
echo 서버 시작 중...
echo 브라우저에서 http://localhost:8000 접속하세요
python local_backend.py

pause