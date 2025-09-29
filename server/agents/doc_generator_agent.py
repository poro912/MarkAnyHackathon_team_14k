import boto3
import json
from typing import List, Dict
from aws_config import *

class DocumentationAgent:
    def __init__(self):
        self.bedrock = boto3.client('bedrock-runtime', region_name=AWS_REGION)
        self.model_id = "anthropic.claude-3-haiku-20240307-v1:0"  # 올바른 Haiku 모델 ID
    
    async def generate_documentation(self, build_data: Dict) -> str:
        """AI를 사용하여 문서 생성"""
        try:
            utilities = build_data.get('utilities', [])
            library_type = build_data.get('build_config', {}).get('library_type', 'dll')
            architecture = build_data.get('build_config', {}).get('architecture', 'x64')
            runtime = build_data.get('build_config', {}).get('runtime', 'MD')
            
            prompt = f"""다음 함수들을 포함한 {library_type.upper()} 라이브러리의 상세한 사용법 문서를 한국어로 작성해주세요.

라이브러리 정보:
- 타입: {library_type.upper()}
- 아키텍처: {architecture}
- 런타임: {runtime}

포함된 함수들:
{json.dumps(utilities, ensure_ascii=False, indent=2)}

다음 형식으로 문서를 작성해주세요:

# 라이브러리 사용법 문서

## 개요
라이브러리의 목적과 주요 기능을 설명

## 포함된 함수들
각 함수별로:
- 함수명과 간단한 설명
- 매개변수 상세 설명
- 반환값 설명
- 사용 예시 코드
- 주의사항

## 사용 방법
{"DLL" if library_type == "dll" else "정적 라이브러리"} 사용법:
- 프로젝트 설정 방법
- 코드 작성 방법
- 빌드 설정

## 주의사항
- 메모리 관리
- 오류 처리
- 호환성 문제

실용적이고 개발자가 바로 사용할 수 있는 문서로 작성해주세요."""

            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 3000,  # 토큰 수 복원
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            }
            
            response = self.bedrock.invoke_model(
                modelId=self.model_id,
                body=json.dumps(body)
            )
            
            response_body = json.loads(response['body'].read())
            return response_body['content'][0]['text']
            
        except Exception as e:
            print(f"AI 문서 생성 오류: {e}")
            return self._generate_fallback_doc(build_data)
    
    def _generate_fallback_doc(self, build_data: Dict) -> str:
        """AI 실패 시 기본 문서 생성"""
        utilities = build_data.get('utilities', [])
        library_type = build_data.get('build_config', {}).get('library_type', 'dll')
        
        doc = f"""# 라이브러리 사용법 문서

## 포함된 함수들

"""
        
        for i, utility in enumerate(utilities, 1):
            doc += f"""
### {i}. {utility.get('name', 'Unknown')}

**설명:** {utility.get('description', '설명 없음')}
**역할:** {utility.get('purpose', '역할 정보 없음')}
**매개변수:** {utility.get('parameters', '매개변수 정보 없음')}
**반환값:** {utility.get('return_type', '반환 타입 정보 없음')}

```cpp
{utility.get('code', '// 코드 없음')}
```

---
"""
        
        doc += f"""
## 사용 방법

{"DLL" if library_type == "dll" else "정적 라이브러리"} 사용법을 참고하세요.

## 주의사항

- 적절한 런타임 라이브러리 링크 필요
- 아키텍처 호환성 확인 필요
- 메모리 관리 주의
"""
        
        return doc
