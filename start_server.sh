#!/bin/bash

# 서버 시작 스크립트
cd /path/to/MarkAnyHackathon_team_14k/server

# Python 가상환경 활성화 (선택사항)
# source venv/bin/activate

# 필요한 패키지 설치
pip install fastapi uvicorn boto3 python-multipart

# AWS 자격증명 설정 (환경변수)
export AWS_ACCESS_KEY_ID="your_access_key"
export AWS_SECRET_ACCESS_KEY="your_secret_key"
export AWS_DEFAULT_REGION="us-east-1"

# 서버 시작
python aws_backend.py