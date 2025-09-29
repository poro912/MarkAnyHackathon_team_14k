@echo off
echo ========================================
echo    AWS 환경에서 서버 시작 (풀 기능)
echo ========================================

cd /d "%~dp0server"

REM AWS 관련 패키지 설치
pip install fastapi uvicorn boto3 python-multipart

REM AWS 자격증명 설정
set AWS_ACCESS_KEY_ID=your_access_key
set AWS_SECRET_ACCESS_KEY=your_secret_key
set AWS_DEFAULT_REGION=us-east-1

REM AWS 서버 시작
echo AWS Bedrock AI 기능 포함
echo 브라우저에서 http://localhost:8000 접속하세요
python aws_backend.py

pause