import unittest
import tempfile
import os
from pathlib import Path
import sys

# 서버 모듈 경로 추가
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'server'))

from code_analyzer import CodeAnalyzer


class TestCodeAnalyzer(unittest.TestCase):
    
    def setUp(self):
        self.analyzer = CodeAnalyzer()
        self.test_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)
    
    def create_test_file(self, filename, content):
        """테스트용 파일 생성"""
        file_path = os.path.join(self.test_dir, filename)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return file_path
    
    def test_analyze_simple_python_file(self):
        """간단한 Python 파일 분석 테스트"""
        content = """
def hello_world():
    print("Hello, World!")
    return True

if __name__ == "__main__":
    hello_world()
"""
        file_path = self.create_test_file("test.py", content)
        result = self.analyzer.analyze_file(file_path)
        
        self.assertIn('file_path', result)
        self.assertIn('total_lines', result)
        self.assertIn('code_lines', result)
        self.assertIn('cyclomatic_complexity', result)
        self.assertIn('difficulty_score', result)
        self.assertIn('developer_level', result)
        self.assertEqual(result['language'], 'Python')
        self.assertGreater(result['total_lines'], 0)
    
    def test_analyze_complex_python_file(self):
        """복잡한 Python 파일 분석 테스트"""
        content = """
import asyncio
import threading
from typing import List, Dict

class DataProcessor:
    def __init__(self):
        self.cache = {}
    
    async def process_data(self, data: List[Dict]) -> Dict:
        try:
            results = []
            for item in data:
                if item.get('type') == 'complex':
                    result = await self._complex_processing(item)
                elif item.get('type') == 'simple':
                    result = self._simple_processing(item)
                else:
                    result = None
                
                if result:
                    results.append(result)
            
            return {'status': 'success', 'results': results}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}
    
    async def _complex_processing(self, item):
        # 복잡한 비동기 처리
        await asyncio.sleep(0.1)
        return item
    
    def _simple_processing(self, item):
        return item
"""
        file_path = self.create_test_file("complex.py", content)
        result = self.analyzer.analyze_file(file_path)
        
        self.assertGreater(result['cyclomatic_complexity'], 1)
        self.assertGreater(result['difficulty_score'], 3)
        self.assertIn(result['developer_level'], ['Mid', 'Senior', 'Architect'])
    
    def test_analyze_project_directory(self):
        """프로젝트 디렉토리 분석 테스트"""
        # 여러 파일 생성
        self.create_test_file("main.py", "print('main')")
        self.create_test_file("utils.py", "def helper(): pass")
        self.create_test_file("config.js", "const config = {};")
        
        result = self.analyzer.analyze_project(self.test_dir)
        
        self.assertIn('files', result)
        self.assertIn('summary', result)
        self.assertEqual(len(result['files']), 3)
        self.assertIn('total_files', result['summary'])
        self.assertIn('total_lines', result['summary'])
    
    def test_cache_functionality(self):
        """캐시 기능 테스트"""
        self.create_test_file("cached.py", "print('test')")
        
        # 첫 번째 분석
        result1 = self.analyzer.analyze_project(self.test_dir)
        
        # 두 번째 분석 (캐시 사용)
        result2 = self.analyzer.analyze_project(self.test_dir)
        
        self.assertEqual(result1, result2)
    
    def test_fallback_analysis(self):
        """AI 실패시 fallback 분석 테스트"""
        content = """
def test_function():
    if True:
        for i in range(10):
            while i > 0:
                try:
                    print(i)
                except:
                    pass
"""
        result = self.analyzer._fallback_analysis(content)
        
        self.assertIn('cyclomatic_complexity', result)
        self.assertIn('difficulty_score', result)
        self.assertIn('developer_level', result)
        self.assertGreater(result['cyclomatic_complexity'], 1)


if __name__ == '__main__':
    unittest.main()
