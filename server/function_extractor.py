import re
from typing import List, Dict

class FunctionExtractor:
    def __init__(self):
        # C/C++ 함수 패턴 (템플릿 제외)
        self.function_patterns = [
            # C++ 함수 (std::string, 네임스페이스 포함)
            r'^\s*(?:inline\s+|static\s+|virtual\s+|explicit\s+)*([a-zA-Z_:][a-zA-Z0-9_:<>,\s*&\[\]]*)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(([^)]*)\)\s*(?:const\s*)?(?:override\s*)?$',
            # 기본 C 함수
            r'^\s*([a-zA-Z_][a-zA-Z0-9_*\s]*)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(([^)]*)\)\s*$'
        ]
        
    def extract_functions(self, code: str) -> List[Dict]:
        """소스 코드에서 함수 시그니처 추출"""
        functions = []
        lines = code.split('\n')
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            # 주석이나 전처리기 지시문 제외
            if line.startswith('//') or line.startswith('#') or line.startswith('/*') or not line:
                i += 1
                continue
            
            # 함수 선언 찾기 (여러 줄에 걸쳐 있을 수 있음)
            func_declaration = self._extract_function_declaration(lines, i)
            if func_declaration:
                func_info, end_line = func_declaration
                
                # 템플릿 함수 완전 제외 (DLL 빌드 불가)
                full_code = '\n'.join(lines[i:end_line+10])  # 앞뒤 코드 확인
                if 'template' in full_code.lower() or func_info.get('name', '').startswith('template'):
                    print(f"❌ 템플릿 함수 제외: {func_info.get('name', 'Unknown')} (DLL 빌드 불가)")
                    i = end_line + 1
                    continue
                
                # main, WinMain 등 엔트리 포인트 제외
                if func_info['name'] in ['main', 'WinMain', 'DllMain']:
                    i = end_line + 1
                    continue
                
                # 함수 본문 추출
                func_body = self._extract_function_body(lines, end_line)
                func_info['code'] = func_body
                
                functions.append(func_info)
                
                # 함수 본문 끝까지 건너뛰기
                i = self._find_function_end(lines, end_line) + 1
            else:
                i += 1
        
        return functions
    
    def _extract_function_declaration(self, lines: List[str], start_line: int) -> tuple:
        """함수 선언 추출 (여러 줄 지원)"""
        declaration_lines = []
        
        # 함수 선언이 여러 줄에 걸쳐 있을 수 있음
        for i in range(start_line, min(start_line + 5, len(lines))):
            line = lines[i].strip()
            if not line or line.startswith('//'):
                continue
                
            declaration_lines.append(line)
            
            # 여는 중괄호를 찾으면 함수 시작
            if '{' in line:
                break
        
        if not declaration_lines:
            return None
            
        # 선언 합치기
        full_declaration = ' '.join(declaration_lines)
        
        # 중괄호 앞까지만 추출
        if '{' in full_declaration:
            full_declaration = full_declaration.split('{')[0].strip()
        
        # 패턴 매칭
        for pattern in self.function_patterns:
            match = re.search(pattern, full_declaration)
            if match:
                return_type = match.group(1).strip()
                func_name = match.group(2).strip()
                params = match.group(3).strip()
                
                # 원본 시그니처 그대로 사용
                original_signature = f"{return_type} {func_name}({params})"
                header_signature = f"LIBRARY_API {return_type} {func_name}({params});"
                
                return ({
                    'name': func_name,
                    'description': f'{func_name} 함수',
                    'parameters': params if params else 'void',
                    'return_type': f'{return_type} - 함수 반환값',
                    'purpose': f'{func_name} 함수의 기능을 수행합니다',
                    'header_declaration': header_signature,
                    'original_signature': original_signature,  # 원본 시그니처 보존
                    'line': start_line + 1
                }, start_line + len(declaration_lines) - 1)
        
        return None
    
    def _extract_function_body(self, lines: List[str], start_line: int) -> str:
        """함수 본문 추출 (중괄호 매칭)"""
        body_lines = []
        brace_count = 0
        started = False
        
        for i in range(start_line, len(lines)):
            line = lines[i]
            body_lines.append(line)
            
            for char in line:
                if char == '{':
                    brace_count += 1
                    started = True
                elif char == '}':
                    brace_count -= 1
                    
            if started and brace_count == 0:
                break
                
        return '\n'.join(body_lines)
    
    def _find_function_end(self, lines: List[str], start_line: int) -> int:
        """함수 끝 위치 찾기"""
        brace_count = 0
        started = False
        
        for i in range(start_line, len(lines)):
            line = lines[i]
            
            for char in line:
                if char == '{':
                    brace_count += 1
                    started = True
                elif char == '}':
                    brace_count -= 1
                    
            if started and brace_count == 0:
                return i
                
        return len(lines) - 1
    
    def generate_header(self, functions: List[Dict]) -> str:
        """헤더 파일 생성"""
        header = """#ifndef UTILITY_LIBRARY_H
#define UTILITY_LIBRARY_H

#ifdef __cplusplus
extern "C" {
#endif

#ifdef BUILDING_DLL
#define LIBRARY_API __declspec(dllexport)
#else
#define LIBRARY_API __declspec(dllimport)
#endif

// 함수 선언
"""
        
        for func in functions:
            header += f"{func['header_declaration']}\n"
        
        header += """
#ifdef __cplusplus
}
#endif

#endif // UTILITY_LIBRARY_H
"""
        
        return header
