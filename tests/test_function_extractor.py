import unittest
import tempfile
import os
import sys

# 서버 모듈 경로 추가
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'server'))

from function_extractor import FunctionExtractor


class TestFunctionExtractor(unittest.TestCase):
    
    def setUp(self):
        self.extractor = FunctionExtractor()
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
    
    def test_extract_python_functions(self):
        """Python 함수 추출 테스트"""
        content = """
def simple_function():
    '''Simple function'''
    return True

class TestClass:
    def method_one(self, param):
        '''Method with parameter'''
        return param * 2
    
    def method_two(self):
        '''Another method'''
        pass

async def async_function():
    '''Async function'''
    await some_operation()
"""
        file_path = self.create_test_file("test.py", content)
        functions = self.extractor.extract_functions_from_file(file_path)
        
        self.assertGreater(len(functions), 0)
        
        # 함수명 확인
        function_names = [f['name'] for f in functions]
        self.assertIn('simple_function', function_names)
        self.assertIn('method_one', function_names)
        self.assertIn('async_function', function_names)
    
    def test_extract_javascript_functions(self):
        """JavaScript 함수 추출 테스트"""
        content = """
function regularFunction() {
    return 'regular';
}

const arrowFunction = () => {
    return 'arrow';
};

class MyClass {
    constructor() {
        this.value = 0;
    }
    
    methodFunction() {
        return this.value;
    }
}

async function asyncFunction() {
    const result = await fetch('/api');
    return result;
}
"""
        file_path = self.create_test_file("test.js", content)
        functions = self.extractor.extract_functions_from_file(file_path)
        
        self.assertGreater(len(functions), 0)
        
        # 함수명 확인
        function_names = [f['name'] for f in functions]
        self.assertIn('regularFunction', function_names)
        self.assertIn('asyncFunction', function_names)
    
    def test_extract_from_directory(self):
        """디렉토리에서 함수 추출 테스트"""
        # Python 파일
        self.create_test_file("module1.py", """
def func1():
    pass

def func2():
    pass
""")
        
        # JavaScript 파일
        self.create_test_file("script.js", """
function jsFunc() {
    return true;
}
""")
        
        # 지원하지 않는 파일
        self.create_test_file("readme.txt", "This is not code")
        
        all_functions = self.extractor.extract_functions_from_directory(self.test_dir)
        
        self.assertGreater(len(all_functions), 0)
        
        # 파일별로 그룹화되어 있는지 확인
        self.assertIsInstance(all_functions, dict)
        
        # Python과 JavaScript 파일이 모두 처리되었는지 확인
        file_paths = list(all_functions.keys())
        py_files = [f for f in file_paths if f.endswith('.py')]
        js_files = [f for f in file_paths if f.endswith('.js')]
        
        self.assertGreater(len(py_files), 0)
        self.assertGreater(len(js_files), 0)
    
    def test_function_metadata(self):
        """함수 메타데이터 추출 테스트"""
        content = """
def documented_function(param1, param2='default'):
    '''
    This is a documented function.
    
    Args:
        param1: First parameter
        param2: Second parameter with default
    
    Returns:
        bool: Success status
    '''
    return True
"""
        file_path = self.create_test_file("documented.py", content)
        functions = self.extractor.extract_functions_from_file(file_path)
        
        self.assertEqual(len(functions), 1)
        func = functions[0]
        
        self.assertEqual(func['name'], 'documented_function')
        self.assertIn('docstring', func)
        self.assertIn('This is a documented function', func['docstring'])
        self.assertIn('line_number', func)
        self.assertGreater(func['line_number'], 0)
    
    def test_empty_file(self):
        """빈 파일 처리 테스트"""
        file_path = self.create_test_file("empty.py", "")
        functions = self.extractor.extract_functions_from_file(file_path)
        
        self.assertEqual(len(functions), 0)
    
    def test_unsupported_file_type(self):
        """지원하지 않는 파일 타입 테스트"""
        file_path = self.create_test_file("test.txt", "This is not code")
        functions = self.extractor.extract_functions_from_file(file_path)
        
        self.assertEqual(len(functions), 0)


if __name__ == '__main__':
    unittest.main()
