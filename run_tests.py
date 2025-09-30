#!/usr/bin/env python3
"""
프로젝트 테스트 실행 스크립트
"""

import unittest
import sys
import os
from pathlib import Path

# 프로젝트 루트 디렉토리를 Python 경로에 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'server'))

def run_all_tests():
    """모든 테스트 실행"""
    # 테스트 디렉토리에서 테스트 발견
    test_dir = project_root / 'tests'
    
    if not test_dir.exists():
        print("테스트 디렉토리가 존재하지 않습니다.")
        return False
    
    # 테스트 로더 생성
    loader = unittest.TestLoader()
    
    # 테스트 스위트 생성
    suite = unittest.TestSuite()
    
    # 개별 테스트 모듈들
    test_modules = [
        'tests.test_code_analyzer',
        'tests.test_function_extractor',
        'tests.test_agent_wrapper',
        'tests.test_aws_backend',
        'tests.test_integration'
    ]
    
    print("🧪 테스트 실행 시작...")
    print("=" * 50)
    
    # 각 테스트 모듈 로드
    for module_name in test_modules:
        try:
            module_suite = loader.loadTestsFromName(module_name)
            suite.addTest(module_suite)
            print(f"✅ {module_name} 로드됨")
        except Exception as e:
            print(f"❌ {module_name} 로드 실패: {e}")
    
    print("=" * 50)
    
    # 테스트 실행
    runner = unittest.TextTestRunner(
        verbosity=2,
        stream=sys.stdout,
        descriptions=True,
        failfast=False
    )
    
    result = runner.run(suite)
    
    # 결과 요약
    print("\n" + "=" * 50)
    print("📊 테스트 결과 요약")
    print("=" * 50)
    print(f"실행된 테스트: {result.testsRun}")
    print(f"실패: {len(result.failures)}")
    print(f"오류: {len(result.errors)}")
    print(f"건너뜀: {len(result.skipped)}")
    
    if result.failures:
        print("\n❌ 실패한 테스트:")
        for test, traceback in result.failures:
            print(f"  - {test}")
    
    if result.errors:
        print("\n💥 오류가 발생한 테스트:")
        for test, traceback in result.errors:
            print(f"  - {test}")
    
    if result.skipped:
        print("\n⏭️ 건너뛴 테스트:")
        for test, reason in result.skipped:
            print(f"  - {test}: {reason}")
    
    success = len(result.failures) == 0 and len(result.errors) == 0
    
    if success:
        print("\n🎉 모든 테스트가 성공했습니다!")
    else:
        print("\n⚠️ 일부 테스트가 실패했습니다.")
    
    return success

def run_specific_test(test_name):
    """특정 테스트만 실행"""
    print(f"🧪 {test_name} 테스트 실행...")
    
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromName(f'tests.{test_name}')
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return len(result.failures) == 0 and len(result.errors) == 0

def main():
    """메인 함수"""
    if len(sys.argv) > 1:
        # 특정 테스트 실행
        test_name = sys.argv[1]
        success = run_specific_test(test_name)
    else:
        # 모든 테스트 실행
        success = run_all_tests()
    
    sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()
