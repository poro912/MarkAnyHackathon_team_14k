import os
from typing import List, Dict, Optional
from fastapi import UploadFile
from agents.code_analyzer_agent import CodeAnalyzerAgent

class AgentWrapper:
    def __init__(self):
        self.agent = CodeAnalyzerAgent()
        self.session_context = {}
    
    async def analyze(self, files: List[UploadFile], user_session: Optional[str] = None) -> List[Dict]:
        """웹 요청을 Agent 형식으로 변환하여 처리"""
        
        # 세션 컨텍스트 가져오기
        context = self.session_context.get(user_session, {
            'previous_files': [],
            'analysis_count': 0
        })
        
        utilities = []
        processed_files = []
        
        for file in files:
            try:
                print(f"파일 처리 시작: {file.filename}")
                
                # 파일 내용 읽기
                content = await file.read()
                if len(content) == 0:
                    print(f"파일이 비어있음: {file.filename}")
                    continue
                
                print(f"파일 크기: {len(content)} bytes")
                
                # 인코딩 처리
                try:
                    text = content.decode('utf-8')
                except UnicodeDecodeError:
                    try:
                        text = content.decode('euc-kr', errors='ignore')
                    except:
                        text = content.decode('latin-1', errors='ignore')
                
                print(f"디코딩된 텍스트 길이: {len(text)}")
                
                file_ext = os.path.splitext(file.filename)[1].lower()
                print(f"파일 확장자: {file_ext}")
                
                # 지원하는 파일 타입만 처리
                if file_ext not in ['.cpp', '.c', '.h', '.cs']:
                    print(f"지원하지 않는 파일 타입: {file_ext}")
                    continue
                
                # Agent 호출
                try:
                    print(f"Agent 처리 시작: {file.filename}")
                    file_utilities = await self.agent.process(text, file_ext, context)
                    print(f"Agent 결과: {len(file_utilities)}개 함수 발견")
                except Exception as agent_error:
                    print(f"Agent 처리 오류 ({file.filename}): {agent_error}")
                    continue
                
                # 파일 정보 추가
                for util in file_utilities:
                    util['file'] = file.filename
                    util['source_file_ext'] = file_ext
                
                utilities.extend(file_utilities)
                processed_files.append(file.filename)
                
            except Exception as e:
                print(f"파일 {file.filename} 처리 중 오류: {e}")
                continue
        
        # 컨텍스트 업데이트
        context['previous_files'].extend(processed_files)
        context['analysis_count'] += 1
        
        # 컨텍스트 크기 제한
        if len(context['previous_files']) > 20:
            context['previous_files'] = context['previous_files'][-10:]
        
        if user_session:
            self.session_context[user_session] = context
        
        return utilities
    
    async def refactor_for_reusability(self, raw_functions: List[Dict], full_code: str, file_extension: str) -> List[Dict]:
        """원본 함수들을 재사용 가능하게 리팩토링"""
        if not raw_functions:
            return []
        
        # 코드 분석기를 통한 리팩토링
        try:
            refactored = await self.agent.refactor_functions(raw_functions, full_code, file_extension)
            return refactored
        except Exception as e:
            print(f"리팩토링 오류: {e}")
            return raw_functions
    
    async def get_agent_stats(self) -> Dict:
        """Agent 통계 정보 반환"""
        return self.agent.get_analysis_stats()
    
    def clear_session(self, user_session: str):
        """세션 컨텍스트 초기화"""
        if user_session in self.session_context:
            del self.session_context[user_session]
    
    def get_session_info(self, user_session: str) -> Dict:
        """세션 정보 반환"""
        return self.session_context.get(user_session, {})
