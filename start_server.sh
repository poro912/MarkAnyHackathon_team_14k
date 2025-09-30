#!/bin/bash
cd "$(dirname "$0")/server"

# 기존 서버 종료
sudo pkill -f aws_backend

# 서버 시작
echo "Starting AWS backend server..."
sudo -E ../venv/bin/python -m uvicorn aws_backend:app --host 0.0.0.0 --port 80
