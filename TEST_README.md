# 테스트 가이드

## 개요
이 프로젝트의 주요 기능들에 대한 테스트 코드입니다.

## 테스트 구조

```
tests/
├── __init__.py
├── test_code_analyzer.py      # 코드 분석기 테스트
├── test_function_extractor.py # 함수 추출기 테스트
├── test_agent_wrapper.py      # AI 에이전트 래퍼 테스트
├── test_aws_backend.py        # AWS 백엔드 API 테스트
└── test_integration.py        # 통합 테스트
```

## 테스트 실행 방법

### 1. 의존성 설치
```bash
pip install -r test_requirements.txt
```

### 2. 모든 테스트 실행
```bash
# unittest 사용
python run_tests.py

# pytest 사용 (권장)
pytest
```

### 3. 특정 테스트만 실행
```bash
# unittest
python run_tests.py test_code_analyzer

# pytest
pytest tests/test_code_analyzer.py
```

### 4. 커버리지 포함 실행
```bash
pytest --cov=server --cov-report=html
```

## 테스트 범위

### 1. CodeAnalyzer 테스트 (`test_code_analyzer.py`)
- ✅ 단일 파일 분석
- ✅ 복잡한 코드 분석
- ✅ 프로젝트 디렉토리 분석
- ✅ 캐시 기능
- ✅ Fallback 분석

### 2. FunctionExtractor 테스트 (`test_function_extractor.py`)
- ✅ Python 함수 추출
- ✅ JavaScript 함수 추출
- ✅ 디렉토리 전체 추출
- ✅ 함수 메타데이터
- ✅ 빈 파일 처리

### 3. AgentWrapper 테스트 (`test_agent_wrapper.py`)
- ✅ 에이전트 초기화
- ✅ 코드 분석 에이전트
- ✅ 문서 생성 에이전트
- ✅ 에러 처리

### 4. AWS Backend 테스트 (`test_aws_backend.py`)
- ✅ API 엔드포인트
- ✅ 파일 업로드
- ✅ 응답 형식
- ✅ 에러 처리

### 5. 통합 테스트 (`test_integration.py`)
- ✅ 전체 워크플로우
- ✅ 캐시 지속성
- ✅ API 통합
- ✅ 성능 테스트

## 테스트 환경 설정

### Mock 사용
AWS 서비스나 외부 의존성이 없어도 테스트가 실행되도록 Mock을 사용합니다.

```python
@patch('aws_backend.analyze_project_directory')
def test_api_endpoint(self, mock_analyze):
    mock_analyze.return_value = {...}
    # 테스트 코드
```

### 임시 파일 사용
테스트용 파일은 `tempfile`을 사용하여 생성하고 자동으로 정리됩니다.

```python
def setUp(self):
    self.test_dir = tempfile.mkdtemp()

def tearDown(self):
    shutil.rmtree(self.test_dir, ignore_errors=True)
```

## 테스트 실행 결과 예시

```
🧪 테스트 실행 시작...
==================================================
✅ tests.test_code_analyzer 로드됨
✅ tests.test_function_extractor 로드됨
✅ tests.test_agent_wrapper 로드됨
✅ tests.test_aws_backend 로드됨
✅ tests.test_integration 로드됨
==================================================

test_analyze_complex_python_file (tests.test_code_analyzer.TestCodeAnalyzer) ... ok
test_analyze_simple_python_file (tests.test_code_analyzer.TestCodeAnalyzer) ... ok
test_cache_functionality (tests.test_code_analyzer.TestCodeAnalyzer) ... ok
...

==================================================
📊 테스트 결과 요약
==================================================
실행된 테스트: 25
실패: 0
오류: 0
건너뜀: 3

🎉 모든 테스트가 성공했습니다!
```

## 주의사항

1. **AWS 의존성**: AWS 서비스 연결이 필요한 테스트는 Mock을 사용하거나 건너뜁니다.
2. **환경 변수**: 테스트 실행 시 AWS 자격 증명이 없어도 동작합니다.
3. **파일 권한**: 임시 파일 생성/삭제 권한이 필요합니다.

## CI/CD 통합

GitHub Actions나 다른 CI/CD 시스템에서 사용할 수 있습니다:

```yaml
- name: Run tests
  run: |
    pip install -r test_requirements.txt
    pytest --cov=server --cov-report=xml
```

## 기여 가이드

새로운 기능을 추가할 때는 해당하는 테스트도 함께 작성해주세요:

1. 단위 테스트 작성
2. 통합 테스트 업데이트
3. 테스트 실행 확인
4. 커버리지 확인
