#!/usr/bin/env python3
import os
import sys
import subprocess

# 서버 디렉토리로 이동
server_dir = os.path.join(os.path.dirname(__file__), 'server')
os.chdir(server_dir)

# uvicorn으로 서버 실행
if __name__ == "__main__":
    subprocess.run([
        sys.executable, "-m", "uvicorn", 
        "aws_backend:app", 
        "--host", "0.0.0.0", 
        "--port", "8000",
        "--reload"
    ])