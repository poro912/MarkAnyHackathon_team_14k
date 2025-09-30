import unittest
import tempfile
import os
import sys
import json
from unittest.mock import patch, Mock

# 서버 모듈 경로 추가
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'server'))


class TestProjectIntegration(unittest.TestCase):
    """프로젝트 전체 통합 테스트"""
    
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def create_sample_project(self):
        """샘플 프로젝트 생성"""
        # Python 파일들
        with open(os.path.join(self.test_dir, 'main.py'), 'w') as f:
            f.write("""
def main():
    '''Main function'''
    processor = DataProcessor()
    result = processor.process_data([1, 2, 3])
    print(f"Result: {result}")

if __name__ == "__main__":
    main()
""")
        
        with open(os.path.join(self.test_dir, 'processor.py'), 'w') as f:
            f.write("""
class DataProcessor:
    '''Data processing class'''
    
    def __init__(self):
        self.cache = {}
    
    def process_data(self, data):
        '''Process input data'''
        try:
            results = []
            for item in data:
                if isinstance(item, int):
                    result = item * 2
                else:
                    result = str(item)
                results.append(result)
            return results
        except Exception as e:
            return f"Error: {e}"
    
    def clear_cache(self):
        '''Clear internal cache'''
        self.cache.clear()
""")
        
        # JavaScript 파일
        with open(os.path.join(self.test_dir, 'utils.js'), 'w') as f:
            f.write("""
function formatData(data) {
    if (!data) return null;
    
    return data.map(item => {
        if (typeof item === 'number') {
            return item.toFixed(2);
        }
        return String(item);
    });
}

async function fetchData(url) {
    try {
        const response = await fetch(url);
        return await response.json();
    } catch (error) {
        console.error('Fetch error:', error);
        return null;
    }
}
""")
    
    def test_full_project_analysis_workflow(self):
        """전체 프로젝트 분석 워크플로우 테스트"""
        self.create_sample_project()
        
        try:
            # 1. 함수 추출 테스트
            from function_extractor import FunctionExtractor
            extractor = FunctionExtractor()
            functions = extractor.extract_functions_from_directory(self.test_dir)
            
            self.assertGreater(len(functions), 0)
            self.assertIn('main.py', str(functions) or '')
            
            # 2. 코드 분석 테스트
            from code_analyzer import CodeAnalyzer
            analyzer = CodeAnalyzer()
            analysis_result = analyzer.analyze_project(self.test_dir)
            
            self.assertIn('files', analysis_result)
            self.assertIn('summary', analysis_result)
            self.assertGreater(len(analysis_result['files']), 0)
            
            # 3. 분석 결과 검증
            for file_analysis in analysis_result['files']:
                self.assertIn('file_path', file_analysis)
                self.assertIn('total_lines', file_analysis)
                self.assertIn('cyclomatic_complexity', file_analysis)
                self.assertIn('difficulty_score', file_analysis)
                self.assertIn('developer_level', file_analysis)
            
            # 4. 요약 정보 검증
            summary = analysis_result['summary']
            self.assertIn('total_files', summary)
            self.assertIn('total_lines', summary)
            self.assertGreater(summary['total_files'], 0)
            self.assertGreater(summary['total_lines'], 0)
            
        except ImportError as e:
            self.skipTest(f"Required modules not available: {e}")
    
    def test_cache_persistence(self):
        """캐시 지속성 테스트"""
        self.create_sample_project()
        
        try:
            from code_analyzer import CodeAnalyzer
            
            # 첫 번째 분석기 인스턴스
            analyzer1 = CodeAnalyzer()
            result1 = analyzer1.analyze_project(self.test_dir)
            
            # 두 번째 분석기 인스턴스 (캐시 공유)
            analyzer2 = CodeAnalyzer()
            result2 = analyzer2.analyze_project(self.test_dir)
            
            # 결과가 동일해야 함 (캐시 사용)
            self.assertEqual(len(result1['files']), len(result2['files']))
            
        except ImportError as e:
            self.skipTest(f"CodeAnalyzer not available: {e}")
    
    @patch('aws_backend.analyze_project_directory')
    def test_api_integration(self, mock_analyze):
        """API 통합 테스트"""
        try:
            from fastapi.testclient import TestClient
            from aws_backend import app
            
            # Mock 설정
            mock_analyze.return_value = {
                'summary': {
                    'total_files': 3,
                    'total_lines': 50,
                    'avg_complexity': 2.5,
                    'max_difficulty': 6
                },
                'files': [
                    {
                        'file_path': 'main.py',
                        'total_lines': 20,
                        'cyclomatic_complexity': 3,
                        'difficulty_score': 5,
                        'developer_level': 'Mid'
                    }
                ]
            }
            
            client = TestClient(app)
            
            # 파일 업로드 테스트
            with open(os.path.join(self.test_dir, 'main.py'), 'rb') as f:
                response = client.post(
                    "/analyze-directory",
                    files={"files": ("main.py", f, "text/plain")}
                )
            
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertIn('summary', data)
            self.assertIn('files', data)
            
        except ImportError as e:
            self.skipTest(f"FastAPI or AWS Backend not available: {e}")
    
    def test_error_handling(self):
        """오류 처리 테스트"""
        # 잘못된 Python 파일 생성
        with open(os.path.join(self.test_dir, 'invalid.py'), 'w') as f:
            f.write("def invalid_syntax(\n    # 문법 오류")
        
        try:
            from code_analyzer import CodeAnalyzer
            analyzer = CodeAnalyzer()
            
            # 오류가 있어도 분석이 완료되어야 함
            result = analyzer.analyze_project(self.test_dir)
            self.assertIn('files', result)
            self.assertIn('summary', result)
            
        except ImportError as e:
            self.skipTest(f"CodeAnalyzer not available: {e}")


class TestPerformance(unittest.TestCase):
    """성능 테스트"""
    
    def test_large_project_analysis(self):
        """대용량 프로젝트 분석 성능 테스트"""
        test_dir = tempfile.mkdtemp()
        
        try:
            # 여러 파일 생성
            for i in range(10):
                with open(os.path.join(test_dir, f'file_{i}.py'), 'w') as f:
                    f.write(f"""
def function_{i}():
    '''Function {i}'''
    result = []
    for j in range(100):
        if j % 2 == 0:
            result.append(j * 2)
        else:
            result.append(j + 1)
    return result

class Class_{i}:
    def method_{i}(self):
        return function_{i}()
""")
            
            from code_analyzer import CodeAnalyzer
            analyzer = CodeAnalyzer()
            
            import time
            start_time = time.time()
            result = analyzer.analyze_project(test_dir)
            end_time = time.time()
            
            # 분석이 완료되어야 함
            self.assertIn('files', result)
            self.assertEqual(len(result['files']), 10)
            
            # 성능 로그 (실패하지 않음)
            analysis_time = end_time - start_time
            print(f"Analysis time for 10 files: {analysis_time:.2f} seconds")
            
        except ImportError as e:
            self.skipTest(f"CodeAnalyzer not available: {e}")
        finally:
            import shutil
            shutil.rmtree(test_dir, ignore_errors=True)


if __name__ == '__main__':
    unittest.main()
