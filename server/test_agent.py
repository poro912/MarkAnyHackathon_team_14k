#!/usr/bin/env python3

import asyncio
import sys
import os
sys.path.append('/home/ec2-user/server')

from agents.code_analyzer_agent import CodeAnalyzerAgent

async def test_agent():
    # Agent 초기화
    agent = CodeAnalyzerAgent()
    
    # 테스트 파일 읽기
    test_file = "/home/ec2-user/server/QDRM_EX_Agent.cpp"
    
    try:
        with open(test_file, 'r', encoding='utf-8') as f:
            code = f.read()
    except:
        with open(test_file, 'r', encoding='euc-kr') as f:
            code = f.read()
    
    print(f"파일 크기: {len(code)} 문자")
    print(f"첫 100자: {code[:100]}")
    
    # Agent로 분석
    try:
        print("Agent 분석 시작...")
        utilities = await agent.process(code, '.cpp', {})
        print(f"분석 결과: {len(utilities)}개 함수 발견")
        
        for i, util in enumerate(utilities):
            print(f"\n함수 {i+1}:")
            print(f"  이름: {util.get('name', 'N/A')}")
            print(f"  설명: {util.get('description', 'N/A')}")
            print(f"  매개변수: {util.get('parameters', 'N/A')}")
            print(f"  반환값: {util.get('return_type', 'N/A')}")
            print(f"  역할: {util.get('purpose', 'N/A')}")
            
    except Exception as e:
        print(f"Agent 분석 오류: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_agent())
