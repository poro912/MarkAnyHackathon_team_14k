import os
import re
import json
import time
from pathlib import Path
from aws_config import get_bedrock_client

class CodeAnalyzer:
    def __init__(self):
        self.supported_extensions = {'.py', '.js', '.java', '.cpp', '.c', '.cs', '.php', '.rb', '.go', '.ts'}
        self.language_map = {'.py': 'Python', '.js': 'JavaScript', '.cpp': 'C++', '.java': 'Java', '.c': 'C', '.cs': 'C#', '.php': 'PHP', '.rb': 'Ruby', '.go': 'Go', '.ts': 'TypeScript'}
        try:
            self.bedrock_client = get_bedrock_client()
            self.use_ai = True
        except:
            self.bedrock_client = None
            self.use_ai = False
    

    def _analyze_summary(self, results):
        """파일 분석 결과를 종합하여 최종 분석 수행"""
        if not self.use_ai or not results:
            return {"result": "분석 불가", "desc": "AI 분석을 사용할 수 없습니다."}
        
        # 분석 데이터 수집
        avg_difficulty = sum(r['difficulty_score'] for r in results) / len(results)
        total_hours = sum(r['estimated_dev_hours'] for r in results)
        avg_complexity = sum(r['cyclomatic_complexity'] for r in results) / len(results)
        developer_levels = [str(r['developer_level']) for r in results]
        tech_stacks = [str(r.get('tech_stack_identification', '')) for r in results if r.get('tech_stack_identification')]
        
        prompt = f"""다음 프로젝트 분석 결과를 종합하여 최종 평가해주세요:

- 평균 난이도: {avg_difficulty:.1f}/10
- 총 예상 개발시간: {total_hours:.1f}시간
- 평균 복잡도: {avg_complexity:.1f}
- 개발자 수준: {', '.join(developer_levels)}
- 기술 스택: {', '.join(tech_stacks)}

다음 중 하나로 응답해주세요:
- 신입사원도 충분히 개발 가능함
- 1~2년차 개발자에 적합함
- 3~5년차 개발자에 적합함
- 5~10년차 개발자에 적합함
- 10년차 이상 개발자에 적합함

JSON 형태로 응답:
{{"result": "선택된 결과", "desc": "분석 근거 설명"}}"""

        try:
            response = self.bedrock_client.invoke_model(
                modelId="anthropic.claude-3-haiku-20240307-v1:0",
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 1000,
                    "messages": [{"role": "user", "content": prompt}]
                })
            )
            
            result = json.loads(response['body'].read())
            ai_response = result['content'][0]['text']
            
            # JSON 추출
            json_start = ai_response.find('{')
            json_end = ai_response.rfind('}') + 1
            if json_start != -1 and json_end != -1:
                return json.loads(ai_response[json_start:json_end])
            else:
                return {"result": "분석 실패", "desc": "응답 파싱 오류"}
                
        except Exception as e:
            return {"result": "분석 오류", "desc": f"오류: {str(e)}"}

    def _analyze_with_ai(self, content: str, file_path: str):
        """AI를 사용한 코드 분석"""
        if not self.use_ai:
            return self._fallback_analysis(content)
        
        prompt = f"""다음 코드를 분석하여 JSON 형태로 결과를 반환해주세요:

파일: {file_path}
코드:
```
{content[:2000]}  # 처음 2000자만 분석
```

다음 항목들을 1-10 점수로 평가해주세요:
- cyclomatic_complexity: 순환복잡도 (1-50)
- maintainability_index: 유지보수성 지수 (1-100)
- estimated_dev_hours: 예상 개발 시간 (시간 단위)
- difficulty_score: 난이도 점수 (1-10)
- developer_level: 필요 개발자 수준 (Entry/Junior/Mid/Senior/Architect)
- pattern_score: 패턴 사용 점수 (1-10)
- optimization_score: 최적화 점수 (1-10)
- best_practices_score: 모범사례 준수도 (1-10)
- tech_stack_identification: 사용된 기술 스택 (프레임워크, 라이브러리 등을 간단히 나열)

JSON 형태로만 응답해주세요:"""

        try:
            response = self.bedrock_client.invoke_model(
                #modelId='anthropic.claude-3-5-sonnet-20240620-v1:0',
                modelId='anthropic.claude-3-haiku-20240307-v1:0',
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 1000,
                    "messages": [{"role": "user", "content": prompt}]
                })
            )
            
            result = json.loads(response['body'].read())
            ai_response = result['content'][0]['text']
            
            # JSON 추출
            json_start = ai_response.find('{')
            json_end = ai_response.rfind('}') + 1
            if json_start != -1 and json_end != -1:
                ai_analysis = json.loads(ai_response[json_start:json_end])
                print(f"AI 분석 성공: {file_path}")
                return ai_analysis
            
        except Exception as e:
            print(f"AI 분석 실패: {e}")
        
        return self._fallback_analysis(content)
    
    def _fallback_analysis(self, content):
        """AI 실패시 기본 분석"""
        complexity = 1 + sum(len(re.findall(rf'\b{k}\b', content, re.IGNORECASE)) 
                           for k in ['if', 'for', 'while', 'try', 'case'])
        
        difficulty = min(10, 1 + len([k for k in ['async', 'threading', 'regex'] if k in content.lower()]) + 
                        (2 if len(content.split('\n')) > 200 else 1 if len(content.split('\n')) > 100 else 0))
        
        levels = ["Entry", "Junior", "Mid", "Senior", "Architect"]
        dev_level = levels[min(4, (difficulty - 1) // 2)]
        
        return {
            'cyclomatic_complexity': min(complexity, 50),
            'maintainability_index': max(0, min(100, int(100 - max(0, (len(content.split('\n')) - 100) / 10)))),
            'estimated_dev_hours': round(len(content.split('\n')) * 0.1, 1),
            'difficulty_score': difficulty,
            'developer_level': dev_level,
            'pattern_score': min(10, 1 + len([p for p in ['class', 'interface', 'factory'] if p in content.lower()])),
            'optimization_score': min(10, 5 + len([o for o in ['cache', 'async', 'parallel'] if o in content.lower()])),
            'best_practices_score': min(10, 1 + len([b for b in ['try:', 'def ', 'class '] if b in content]))
        }
    
    def analyze_file(self, file_path: str):
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        lines = content.split('\n')
        total_lines = len(lines)
        code_lines = len([l for l in lines if l.strip() and not l.strip().startswith(('#', '//', '/*', '*'))])
        comment_lines = len([l for l in lines if l.strip().startswith(('#', '//', '/*', '*'))])
        
        # AI 분석 수행
        ai_analysis = self._analyze_with_ai(content, file_path)
        
        # 기술 스택 식별
        ext = Path(file_path).suffix
        tech_stack = []
        if ext in {'.py': 'Python', '.js': 'JavaScript', '.cpp': 'C++', '.java': 'Java'}.keys():
            tech_stack.append({'.py': 'Python', '.js': 'JavaScript', '.cpp': 'C++', '.java': 'Java'}[ext])
        
        return {
            'file_path': file_path,
            'total_lines': total_lines,
            'code_lines': code_lines,
            'comment_lines': comment_lines,
            'code_comment_ratio': round(code_lines / max(comment_lines, 1), 2),
            'cyclomatic_complexity': ai_analysis['cyclomatic_complexity'],
            'maintainability_index': ai_analysis['maintainability_index'],
            'estimated_dev_hours': ai_analysis['estimated_dev_hours'],
            'difficulty_score': ai_analysis['difficulty_score'],
            'developer_level': ai_analysis['developer_level'],
            'pattern_score': ai_analysis['pattern_score'],
            'optimization_score': ai_analysis['optimization_score'],
            'best_practices_score': ai_analysis['best_practices_score'],
            'tech_stack_identification': ai_analysis.get('tech_stack_identification', 'AI 분석 불가'),            'language': self.language_map.get(ext, 'Unknown'),
            'tech_stack': tech_stack
        }
    
    def analyze_project(self, project_path: str):
        results = []
        for root, dirs, files in os.walk(project_path):
            for file in files:
                if Path(file).suffix in self.supported_extensions:
                    results.append(self.analyze_file(os.path.join(root, file)))
                # AI rate limit 고려, 실제 값이 얼마인지 확인후 처리 필요
                # 여기서는 매 요청마다 2초 대기
                if self.use_ai:
                    time.sleep(2)
        
        if results:
            summary = {
                'total_files': len(results),
                'total_lines': sum(r['total_lines'] for r in results),
                'avg_complexity': round(sum(r['cyclomatic_complexity'] for r in results) / len(results), 2),
                'total_estimated_hours': round(sum(r['estimated_dev_hours'] for r in results), 1),
                'max_difficulty': max(r['difficulty_score'] for r in results)
            }
            
            # 최종 분석 수행
            final_analysis = self._analyze_summary(results)
            summary.update(final_analysis)
        else:
            summary = {}
        
        return {'files': results, 'summary': summary}
