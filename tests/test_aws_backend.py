import unittest
from unittest.mock import Mock, patch, MagicMock
import tempfile
import os
import sys
import json

# 서버 모듈 경로 추가
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'server'))

from fastapi.testclient import TestClient


class TestAWSBackend(unittest.TestCase):
    
    def setUp(self):
        # AWS 백엔드 모듈을 동적으로 import (의존성 문제 방지)
        try:
            from aws_backend import app
            self.client = TestClient(app)
            self.app_available = True
        except ImportError as e:
            print(f"AWS Backend not available for testing: {e}")
            self.app_available = False
    
    def test_health_check(self):
        """헬스 체크 엔드포인트 테스트"""
        if not self.app_available:
            self.skipTest("AWS Backend not available")
        
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
    
    @patch('aws_backend.analyze_project_directory')
    def test_analyze_directory_endpoint(self, mock_analyze):
        """디렉토리 분석 엔드포인트 테스트"""
        if not self.app_available:
            self.skipTest("AWS Backend not available")
        
        # Mock 응답 설정
        mock_analyze.return_value = {
            'summary': {'total_files': 1, 'total_lines': 10},
            'files': [{'file_path': 'test.py', 'total_lines': 10}]
        }
        
        # 테스트 파일 업로드
        with tempfile.NamedTemporaryFile(suffix='.py', delete=False) as tmp:
            tmp.write(b"print('test')")
            tmp.flush()
            
            with open(tmp.name, 'rb') as f:
                response = self.client.post(
                    "/analyze-directory",
                    files={"files": ("test.py", f, "text/plain")}
                )
        
        os.unlink(tmp.name)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('summary', data)
        self.assertIn('files', data)
    
    def test_invalid_file_upload(self):
        """잘못된 파일 업로드 테스트"""
        if not self.app_available:
            self.skipTest("AWS Backend not available")
        
        response = self.client.post(
            "/analyze-directory",
            files={"files": ("test.txt", b"not code", "text/plain")}
        )
        
        # 지원하지 않는 파일 형식이므로 빈 결과 또는 오류 응답
        self.assertIn(response.status_code, [200, 400])


class TestUtilityFunctions(unittest.TestCase):
    
    def setUp(self):
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'server'))
    
    def test_decimal_default(self):
        """Decimal 직렬화 함수 테스트"""
        try:
            from aws_backend import decimal_default
            from decimal import Decimal
            
            # 정수 Decimal
            result = decimal_default(Decimal('10'))
            self.assertEqual(result, 10)
            self.assertIsInstance(result, int)
            
            # 소수 Decimal
            result = decimal_default(Decimal('10.5'))
            self.assertEqual(result, 10.5)
            self.assertIsInstance(result, float)
            
            # 다른 타입은 TypeError 발생
            with self.assertRaises(TypeError):
                decimal_default("string")
        except ImportError:
            self.skipTest("AWS Backend not available")


if __name__ == '__main__':
    unittest.main()
