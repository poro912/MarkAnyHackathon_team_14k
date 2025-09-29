#!/usr/bin/env python3
import os
import sys
import subprocess

# 윈도우에서 서버 실행
def main():
    # 서버 디렉토리로 이동
    server_dir = os.path.join(os.path.dirname(__file__), 'server')
    os.chdir(server_dir)
    
    print("🚀 윈도우에서 서버 시작...")
    
    # uvicorn으로 서버 실행
    subprocess.run([
        sys.executable, "-m", "uvicorn", 
        "aws_backend:app", 
        "--host", "0.0.0.0", 
        "--port", "8000",
        "--reload"
    ])

if __name__ == "__main__":
    main()