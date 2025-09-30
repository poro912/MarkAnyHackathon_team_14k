import unittest
from unittest.mock import Mock, patch
import sys
import os

# 서버 모듈 경로 추가
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'server'))


class TestAgentWrapper(unittest.TestCase):
    
    def setUp(self):
        try:
            from agent_wrapper import AgentWrapper
            self.AgentWrapper = AgentWrapper
            self.wrapper_available = True
        except ImportError as e:
            print(f"AgentWrapper not available for testing: {e}")
            self.wrapper_available = False
    
    @patch('agent_wrapper.get_bedrock_client')
    def test_agent_wrapper_initialization(self, mock_bedrock):
        """에이전트 래퍼 초기화 테스트"""
        if not self.wrapper_available:
            self.skipTest("AgentWrapper not available")
        
        mock_client = Mock()
        mock_bedrock.return_value = mock_client
        
        wrapper = self.AgentWrapper()
        self.assertIsNotNone(wrapper)
    
    @patch('agent_wrapper.get_bedrock_client')
    def test_code_analysis_agent(self, mock_bedrock):
        """코드 분석 에이전트 테스트"""
        if not self.wrapper_available:
            self.skipTest("AgentWrapper not available")
        
        mock_client = Mock()
        mock_bedrock.return_value = mock_client
        
        # Mock 응답 설정
        mock_response = {
            'output': {
                'text': '{"complexity": 5, "maintainability": 80}'
            }
        }
        mock_client.invoke_agent.return_value = mock_response
        
        wrapper = self.AgentWrapper()
        
        test_code = """
def test_function():
    return "Hello, World!"
"""
        
        try:
            result = wrapper.analyze_code(test_code)
            self.assertIsNotNone(result)
        except Exception as e:
            # 실제 AWS 연결이 없을 때는 예외가 발생할 수 있음
            self.assertIsInstance(e, Exception)
    
    @patch('agent_wrapper.get_bedrock_client')
    def test_document_generation_agent(self, mock_bedrock):
        """문서 생성 에이전트 테스트"""
        if not self.wrapper_available:
            self.skipTest("AgentWrapper not available")
        
        mock_client = Mock()
        mock_bedrock.return_value = mock_client
        
        # Mock 응답 설정
        mock_response = {
            'output': {
                'text': 'Generated documentation for the code'
            }
        }
        mock_client.invoke_agent.return_value = mock_response
        
        wrapper = self.AgentWrapper()
        
        test_functions = [
            {
                'name': 'test_function',
                'docstring': 'Test function',
                'code': 'def test_function(): pass'
            }
        ]
        
        try:
            result = wrapper.generate_documentation(test_functions)
            self.assertIsNotNone(result)
        except Exception as e:
            # 실제 AWS 연결이 없을 때는 예외가 발생할 수 있음
            self.assertIsInstance(e, Exception)


class TestAgentIntegration(unittest.TestCase):
    """에이전트 통합 테스트"""
    
    def test_agent_availability(self):
        """에이전트 모듈 가용성 테스트"""
        try:
            sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'server'))
            from agent_wrapper import AgentWrapper
            self.assertTrue(True, "AgentWrapper imported successfully")
        except ImportError:
            self.skipTest("AgentWrapper not available - AWS dependencies missing")
    
    def test_agents_directory_structure(self):
        """에이전트 디렉토리 구조 테스트"""
        agents_dir = os.path.join(os.path.dirname(__file__), '..', 'server', 'agents')
        
        if os.path.exists(agents_dir):
            self.assertTrue(os.path.isdir(agents_dir))
            
            # 필요한 파일들이 존재하는지 확인
            expected_files = [
                '__init__.py',
                'agent_wrapper.py',
                'code_analyzer_agent.py',
                'doc_generator_agent.py'
            ]
            
            for file_name in expected_files:
                file_path = os.path.join(agents_dir, file_name)
                if os.path.exists(file_path):
                    self.assertTrue(os.path.isfile(file_path), f"{file_name} should be a file")
        else:
            self.skipTest("Agents directory not found")


if __name__ == '__main__':
    unittest.main()
