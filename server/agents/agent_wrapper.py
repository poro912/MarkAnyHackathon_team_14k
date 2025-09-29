from typing import List, Dict, Optional
from .code_analyzer_agent import CodeAnalyzerAgent

class AgentWrapper:
    def __init__(self):
        self.code_analyzer = CodeAnalyzerAgent()
        print("Agent 래퍼 초기화 완료")
    
    async def refactor_for_reusability(self, raw_functions: List[Dict], full_code: str, file_extension: str) -> List[Dict]:
        """원본 함수들을 재사용 가능하게 리팩토링"""
        if not raw_functions:
            return []
        
        # 코드 분석기를 통한 리팩토링
        refactored = await self.code_analyzer.refactor_functions(raw_functions, full_code, file_extension)
        
        return refactored
    
    async def generate_documentation(self, utilities):
        """유틸리티 함수들에 대한 문서 생성"""
        try:
            # 함수 정보를 문서화용 프롬프트로 변환
            functions_info = []
            for utility in utilities:
                func_info = f"""
함수명: {utility.get('name', 'Unknown')}
설명: {utility.get('description', '설명 없음')}
목적: {utility.get('purpose', '목적 없음')}
매개변수: {utility.get('parameters', '매개변수 없음')}
반환타입: {utility.get('return_type', '반환타입 없음')}
코드:
```cpp
{utility.get('code', '// 코드 없음')}
```
"""
                functions_info.append(func_info)
            
            documentation_prompt = f"""
다음 C++ 유틸리티 함수들에 대한 상세한 사용 가이드 문서를 마크다운 형식으로 작성해주세요.

**포함할 내용:**
1. 각 함수의 목적과 사용법
2. 매개변수 설명
3. 반환값 설명
4. 사용 예제 코드
5. 주의사항이나 제한사항

**함수 목록:**
{chr(10).join(functions_info)}

사용자가 이 라이브러리를 쉽게 사용할 수 있도록 친절하고 상세한 문서를 작성해주세요.
"""

            # Bedrock 클라이언트 직접 생성
            from aws_config import get_bedrock_client, BEDROCK_MODEL_ID
            import json
            
            bedrock_client = get_bedrock_client()
            
            response = bedrock_client.invoke_model(
                modelId=BEDROCK_MODEL_ID,
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 4000,
                    "messages": [
                        {
                            "role": "user",
                            "content": documentation_prompt
                        }
                    ]
                })
            )
            
            response_body = json.loads(response['body'].read())
            documentation = response_body['content'][0]['text']
            return documentation
            
        except Exception as e:
            print(f"문서 생성 오류: {e}")
            # 기본 문서 생성
            basic_doc = "# 유틸리티 라이브러리 문서\n\n"
            for utility in utilities:
                basic_doc += f"## {utility.get('name', 'Unknown')}\n\n"
                basic_doc += f"**설명:** {utility.get('description', '설명 없음')}\n\n"
                basic_doc += f"**목적:** {utility.get('purpose', '목적 없음')}\n\n"
                basic_doc += f"**매개변수:** `{utility.get('parameters', '매개변수 없음')}`\n\n"
                basic_doc += f"**반환타입:** `{utility.get('return_type', '반환타입 없음')}`\n\n"
                basic_doc += "```cpp\n" + utility.get('code', '// 코드 없음') + "\n```\n\n"
            
            return basic_doc
    
    async def get_agent_stats(self) -> Dict:
        """Agent 통계 정보"""
        return {
            "code_analyzer": self.code_analyzer.get_analysis_stats() if self.code_analyzer else {},
            "total_processed": 0,
            "success_rate": 0.0
        }
