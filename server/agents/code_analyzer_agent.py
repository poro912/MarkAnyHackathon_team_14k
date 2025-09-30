import boto3
import json
import time
import asyncio
from typing import List, Dict, Optional
from aws_config import *

class CodeAnalyzerAgent:
    def __init__(self):
        try:
            self.bedrock = get_bedrock_client()
            self.aws_available = True
            print("✅ AWS Bedrock 연결 성공")
        except Exception as e:
            print(f"❌ AWS Bedrock 연결 실패: {e}")
            self.aws_available = False
            self.bedrock = None
        
        self.analysis_history = {}
    
    async def process(self, code: str, file_extension: str, context: Optional[Dict] = None) -> List[Dict]:
        """Agent의 메인 처리 함수"""
        if self.aws_available and self.bedrock:
            return await self._analyze_with_bedrock(code, file_extension, context)
        else:
            print("❌ Bedrock을 사용할 수 없습니다. 함수 추출을 건너뜁니다.")
            return []
    
    async def _analyze_with_bedrock(self, code: str, file_extension: str, context: Optional[Dict]) -> List[Dict]:
        """Bedrock을 사용한 도구 기반 분석"""
        
        # 도구 정의
        tools = [{
            "toolSpec": {
                "name": "extract_utilities",
                "description": "Extract reusable utility functions from code for DLL creation",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "utilities": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string", "description": "Function name"},
                                        "description": {"type": "string", "description": "Korean description (3-5 words)"},
                                        "parameters": {"type": "string", "description": "Function parameters with types"},
                                        "return_type": {"type": "string", "description": "Return type and description"},
                                        "purpose": {"type": "string", "description": "What this function does"},
                                        "code": {"type": "string", "description": "Complete refactored function code"},
                                        "header_declaration": {"type": "string", "description": "Header file function declaration with LIBRARY_API"},
                                        "line": {"type": "integer", "description": "Line number in original code"}
                                    },
                                    "required": ["name", "description", "parameters", "return_type", "purpose", "code", "header_declaration", "line"]
                                }
                            }
                        },
                        "required": ["utilities"]
                    }
                }
            }
        }]
        
        # 프롬프트
        prompt = f"""
Analyze this {file_extension} code and extract **REUSABLE utility functions** that can be used in other projects.

### EXTRACTION RULES
**EXTRACT ONLY:**
- General-purpose functions that perform specific, reusable tasks
- Static utility functions
- API wrapper/helper functions
- Functions that can be generalized for wider use

**DO NOT EXTRACT:**
- Class constructors/destructors
- Framework-specific lifecycle functions (InitInstance, OnCreate 등)
- Message map/event handler stubs
- Empty or trivial one-liners
- **Entry-point functions (e.g., int main, WinMain)**
"""
        
        prompt = f"""Analyze this {file_extension} code and extract **REUSABLE utility functions** that can be exported in a DLL and reused in other projects.

### EXTRACTION RULES
**EXTRACT ONLY:**
- General-purpose functions that can be safely exported from a DLL
- API wrapper/helper functions (e.g., wrappers around WinAPI like CreateFile, ReadFile, WriteFile, Registry APIs)
- Functions that are self-contained and do not depend on internal globals or frameworks
- Functions that can be parameterized to replace hardcoded values (e.g., pipe name, mutex name, registry path)

**DO NOT EXTRACT:**
- Class constructors/destructors
- Framework-specific lifecycle functions (e.g., InitInstance, WinMain, message handlers)
- Empty or trivial one-liners
- Functions that depend on internal global variables or internal-only state (e.g., g_CurrentPath, g_bWritefileErr)
- **Entry-point functions (e.g., int main, WinMain)**

### TRANSFORMATION RULES
- Refactor functions to accept parameters instead of hardcoded constants.
  Example: if a function uses `"\\\\.\\pipe\\test_pipe"`, replace it with a `const TCHAR* pipeName` parameter.
- Ensure each function is complete, self-contained, and can compile independently.
- DO NOT add extern "C" or __declspec(dllexport) to function code - these are for build time only.
- Show clean, readable function code without export decorations.

### REQUIRED OUTPUT FORMAT
For each extracted function, return a JSON object with ALL required fields:
- "name": exact function name
- "description": short Korean summary (3–5 words)
- "parameters": parameter list after refactoring
- "return_type": return type and meaning
- "purpose": explain what the function does in Korean
- "code": the complete refactored function code, clean and readable (NO export decorations)
- "header_declaration": header file declaration with LIBRARY_API (e.g. "LIBRARY_API bool ReadFile(const char* filename);")
- "line": approximate line number in source

### IMPORTANT
- Header declaration must match the function signature exactly
- Use LIBRARY_API for DLL export/import
- Ensure parameter types and names are identical in both header and code
If the only functions in the code are entry points (like main/WinMain), return an **empty array**.  
Do NOT include entry points just to satisfy the output format.

---

Code to analyze:
```{file_extension}
{code}
```

Use the extract_utilities tool to return ONLY useful utility functions.
"""
        
        try:
            # Bedrock 호출 with retry logic
            max_retries = 3
            base_delay = 2
            
            for attempt in range(max_retries):
                try:
                    # 쓰로틀링 방지를 위한 지연
                    await asyncio.sleep(2)
                    
                    response = self.bedrock.converse(
                        modelId=BEDROCK_MODEL_ID,
                        messages=[{
                            "role": "user",
                            "content": [{"text": prompt}]
                        }],
                        toolConfig={
                            "tools": tools
                        }
                    )
                    break  # 성공하면 루프 종료
                    
                except Exception as e:
                    if "ThrottlingException" in str(e) and attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)  # 지수 백오프
                        print(f"Throttling 감지, {delay}초 대기 후 재시도... (시도 {attempt + 1}/{max_retries})")
                        time.sleep(delay)
                        continue
                    else:
                        raise e
            
            # 응답 처리
            if 'output' in response and 'message' in response['output']:
                content = response['output']['message'].get('content', [])
                
                for content_block in content:
                    if content_block.get('toolUse'):
                        tool_input = content_block.get('toolUse', {}).get('input', {})
                        utilities = tool_input.get('utilities', [])
                        return self._validate_utilities(utilities)
            
            print(f"❌ AI 리팩토링 실패, 원본 함수 반환")
            return raw_functions
        
        except Exception as e:
            print(f"❌ AI 리팩토링 오류: {e}")
            return raw_functions
    
    def _validate_utilities(self, utilities: List[Dict]) -> List[Dict]:
        """Agent의 품질 검증"""
        validated = []
        
        print(f"🔍 검증 시작: {len(utilities)}개 함수")
        
        for i, util in enumerate(utilities):
            if 'name' not in util:
                continue
                
            print(f"\n--- 함수 {i+1}: {util.get('name', 'Unknown')} ---")
            print(f"원본 parameters: {util.get('parameters', 'None')}")
            print(f"원본 return_type: {util.get('return_type', 'None')}")
            print(f"원본 header_declaration: {util.get('header_declaration', 'None')}")
                
            # 기본값 설정하지 않고 AI가 분석하도록 강제
            util.setdefault('description', '함수')
            util.setdefault('code', '// 코드 없음')
            util.setdefault('line', 1)
            util.setdefault('type', 'function')
            
            # 기본값 설정
            util.setdefault('description', '함수')
            util.setdefault('parameters', '매개변수 정보 없음')
            util.setdefault('return_type', '반환 타입 정보 없음')
            util.setdefault('purpose', '함수 역할 정보 없음')
            util.setdefault('code', '// 코드 없음')
            util.setdefault('required_headers', [])  # 빈 배열로 기본값 설정
            
            print(f"검증 후 required_headers: {util.get('required_headers', 'None')}")
            
            # AI가 리팩토링한 시그니처 우선 사용
            func_name = util.get('name', 'UnknownFunction')
            params = util.get('parameters', 'void')
            return_type = util.get('return_type', 'void').split(' - ')[0].strip()
            
            print(f"처리된 func_name: {func_name}")
            print(f"처리된 params: {params}")
            print(f"처리된 return_type: {return_type}")
            
            # AI가 제공한 header_declaration이 있으면 그대로 사용
            if 'header_declaration' not in util or not util['header_declaration'].strip():
                new_header = f"LIBRARY_API {return_type} {func_name}({params});"
                util['header_declaration'] = new_header
                print(f"새로 생성된 header: {new_header}")
            else:
                print(f"AI 제공 header 사용: {util['header_declaration']}")
            
            # 함수 코드에 시그니처가 없으면 AI가 제공한 시그니처로 추가
            code = util.get('code', '')
            if not func_name + '(' in code[:100]:
                new_signature = f"{return_type} {func_name}({params})"
                util['code'] = f"{new_signature}\n{code}"
                print(f"코드에 시그니처 추가: {new_signature}")
            else:
                print("코드에 시그니처 이미 존재")
            
            util.setdefault('line', 1)
            util.setdefault('type', 'function')
            
            print(f"최종 header_declaration: {util['header_declaration']}")
            
            validated.append(util)
        
        print(f"\n✅ 검증 완료: {len(validated)}개 함수")
        return validated
    
    async def refactor_functions(self, raw_functions: List[Dict], full_code: str, file_extension: str) -> List[Dict]:
        """원본 함수들을 재사용 가능하게 리팩토링"""
        if not self.aws_available or not self.bedrock:
            print("❌ Bedrock을 사용할 수 없습니다. 원본 함수 반환")
            return raw_functions
        
        # DLL 유틸리티 함수 추출 특화 프롬프트
        func_list = "\n".join([f"- {func['name']}: {func.get('signature', 'N/A')}" for func in raw_functions[:8]])
        refactoring_prompt = f"""
다음 함수들 중 DLL로 만들 가치가 있는 유틸리티 함수만 선별하여 변환하세요.

목표: 프로젝트 의존성을 제거하고 다른 곳에서도 유용하게 쓸 수 있는 범용 함수로 변환

선별 기준:
1. DLL로 만들 가치가 있는 함수 (문자열 처리, 파일 처리, 수학 계산, 시간 처리 등)
2. 프로젝트 특화 의존성을 제거할 수 있는 함수
3. 다른 프로젝트에서도 재사용 가능한 함수

DLL 빌드 요구사항:
- template 함수는 완전히 제거하거나 구체적인 타입으로 일반화
- 헤더에만 필요한 소스는 제거
- 모든 함수는 .cpp 파일에서 빌드 가능해야 함

제외 대상:
- template 함수 (일반화 불가능한 경우)
- main, WinMain, DllMain 등 엔트리 포인트
- 특정 프로젝트에만 종속된 함수
- 제거할 수 없는 복잡한 의존성이 있는 함수

함수들:
{func_list}

DLL 빌드 가능한 함수만 JSON 배열로 응답:
[{{"name": "함수명", "description": "함수 기능", "code": "DLL 빌드 가능한 완전한 함수 코드", "header_declaration": "LIBRARY_API 반환타입 함수명(매개변수);"}}]
"""
        
        max_retries = 3
        base_delay = 3
        
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    # 재시도 시 지수적 백오프
                    delay = base_delay * (2 ** attempt)
                    print(f"🔄 재시도 {attempt}/{max_retries}, {delay}초 대기")
                    await asyncio.sleep(delay)
                else:
                    await asyncio.sleep(base_delay)  # 첫 시도는 기본 대기
                
                response = self.bedrock.converse(
                    modelId="anthropic.claude-3-haiku-20240307-v1:0",  # Haiku 모델로 변경
                    messages=[{
                        "role": "user",
                        "content": [{"text": refactoring_prompt}]
                    }],
                    toolConfig={
                        "tools": [{
                            "toolSpec": {
                                "name": "refactor_utilities",
                                "description": "Extract and refactor reusable utility functions",
                                "inputSchema": {
                                    "json": {
                                        "type": "object",
                                        "properties": {
                                            "utilities": {
                                                "type": "array",
                                                "items": {
                                                    "type": "object",
                                                    "properties": {
                                                        "name": {"type": "string", "description": "Function name"},
                                                        "description": {"type": "string", "description": "Korean description (3-5 words)"},
                                                        "parameters": {"type": "string", "description": "Function parameters with types"},
                                                        "return_type": {"type": "string", "description": "Return type and description"},
                                                        "purpose": {"type": "string", "description": "What this function does"},
                                                        "code": {"type": "string", "description": "Refactored function code"},
                                                        "header_declaration": {"type": "string", "description": "Header file function declaration with LIBRARY_API"},
                                                        "required_headers": {"type": "array", "items": {"type": "string"}, "description": "List of required C++ headers (e.g. ['<chrono>', '<cmath>'])"},
                                                        "reusability_score": {"type": "integer", "description": "Reusability score 1-10"},
                                                        "changes_made": {"type": "string", "description": "What changes were made for reusability"},
                                                        "line": {"type": "integer", "description": "Line number in original code"}
                                                    },
                                                    "required": ["name", "description", "parameters", "return_type", "purpose", "code", "header_declaration", "required_headers", "reusability_score", "changes_made", "line"]
                                                }
                                            }
                                        },
                                        "required": ["utilities"]
                                    }
                                }
                            }
                        }]
                    },
                    inferenceConfig={
                        "maxTokens": 4000,
                        "temperature": 0.1
                    }
                )
                
                # 성공하면 루프 탈출
                break
                
            except Exception as e:
                error_msg = str(e)
                print(f"Bedrock 호출 오류 (시도 {attempt + 1}/{max_retries}): {e}")
                
                # 쓰로틀링이 아닌 다른 오류면 즉시 실패
                if "ThrottlingException" not in error_msg and "Too many requests" not in error_msg:
                    print("❌ 쓰로틀링이 아닌 오류, 즉시 실패")
                    return []
                
                # 마지막 시도였으면 원본 함수 반환
                if attempt == max_retries - 1:
                    print("⏳ 최대 재시도 횟수 초과, 원본 함수 반환")
                    return raw_functions
        
        try:
            
            # 응답 파싱
            if 'output' in response and 'message' in response['output']:
                content = response['output']['message'].get('content', [])
                for content_block in content:
                    if content_block.get('toolUse'):
                        tool_input = content_block.get('toolUse', {}).get('input', {})
                        utilities = tool_input.get('utilities', [])
                        
                        print(f"🤖 AI 리팩토링 결과: {len(utilities)}개 함수")
                        for j, util in enumerate(utilities):
                            print(f"  함수 {j+1}: {util.get('name', 'Unknown')}")
                            print(f"    parameters: {util.get('parameters', 'None')}")
                            print(f"    return_type: {util.get('return_type', 'None')}")
                            print(f"    header_declaration: {util.get('header_declaration', 'None')}")
                            print(f"    required_headers: {util.get('required_headers', 'None')}")
                            print(f"    reusability_score: {util.get('reusability_score', 'None')}")
                            
                            # required_headers가 없으면 경고
                            if 'required_headers' not in util:
                                print(f"    ⚠️ required_headers 필드 누락!")
                            elif not util.get('required_headers'):
                                print(f"    ⚠️ required_headers가 비어있음!")
                        
                        # 재사용성 점수 7점 이상만 필터링
                        filtered_utilities = [
                            util for util in utilities 
                            if util.get('reusability_score', 0) >= 7
                        ]
                        
                        print(f"📊 필터링 후: {len(filtered_utilities)}개 함수 (점수 7점 이상)")
                        
                        # required_headers 필드가 없는 함수들 체크
                        missing_headers = [
                            util['name'] for util in filtered_utilities 
                            if 'required_headers' not in util or not util.get('required_headers')
                        ]
                        if missing_headers:
                            print(f"⚠️ required_headers 누락된 함수들: {missing_headers}")
                        
                        # AI가 리팩토링한 새로운 시그니처 사용
                        return self._validate_utilities(filtered_utilities)
            
            print("❌ AI 리팩토링 실패, 원본 함수 반환")
            return raw_functions
            
        except Exception as e:
            print(f"❌ 리팩토링 오류: {e}")
            return raw_functions
    
    def get_analysis_stats(self) -> Dict:
        """분석 통계 반환"""
        return {
            "total_analyzed": len(self.analysis_history),
            "success_rate": 0.95,
            "avg_functions_per_file": 2.3
        }
    
    def get_analysis_stats(self) -> Dict:
        """분석 통계 반환"""
        return {
            "total_analyses": len(self.analysis_history),
            "aws_available": self.aws_available
        }
