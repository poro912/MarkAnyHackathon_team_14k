@echo off
cd /d "%~dp0server"

REM 필요한 패키지 설치
pip install fastapi uvicorn python-multipart

REM 로컬 서버 시작 (AWS 없음)
python local_backend.py

pause