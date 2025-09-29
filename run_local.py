#!/usr/bin/env python3
import os
import sys
import subprocess

def main():
    # 서버 디렉토리로 이동
    server_dir = os.path.join(os.path.dirname(__file__), 'server')
    
    if not os.path.exists(server_dir):
        print("❌ server 디렉토리를 찾을 수 없습니다.")
        return
    
    os.chdir(server_dir)
    
    print("🚀 로컬 서버 시작 중...")
    print("💻 윈도우 로컬 환경")
    print("🌐 브라우저에서 http://localhost 접속하세요")
    
    # 로컬 백엔드 실행
    subprocess.run([sys.executable, "local_backend.py"])

if __name__ == "__main__":
    main()