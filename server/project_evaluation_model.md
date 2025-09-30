# 프로젝트 평가
Claude에 적용된 소프트웨어공학 이론 적용하여 평가함
- COCOMO
- McCabe의 순환복잡도 이론
- Halstead 복잡도
- GoF 디자인 패턴, 아키텍처 패턴
- 언어별 코딩 컨벤션 등

## 평가 항목
### 1. cyclomatic_complexity (순환복잡도)
- **범위**: 1-50
- **설명**: 코드의 복잡도를 측정하는 지표
- **계산 방식**:
  - AI 분석: 1-50 범위로 평가
  - Fallback: min(complexity, 50) - if, for, while, try, case 키워드 개수 기반
- **의미**: 높을수록 복잡한 코드

### 2. maintainability_index (유지보수성 지수)
- **범위**: 1-100
- **설명**: 코드의 유지보수 용이성
- **계산 방식**:
  - AI 분석: 1-100 범위로 평가
  - Fallback: max(0, min(100, int(100 - max(0, (len(content.split('\n')) - 100) / 10))))
- **의미**: 높을수록 유지보수하기 쉬운 코드

### 3. estimated_dev_hours (예상 개발 시간)
- **범위**: 시간 단위 (제한 없음)
- **설명**: 해당 코드를 개발하는데 필요한 예상 시간
- **계산 방식**:
  - AI 분석: 자유 범위
  - Fallback: round(len(content.split('\n')) * 0.1, 1) (라인 수 × 0.1시간)
- **의미**: 개발 공수 추정

### 4. difficulty_score (난이도 점수)
- **범위**: 1-10
- **설명**: 코드의 구현 난이도
- **계산 방식**:
  - AI 분석: 1-10 범위로 평가
  - Fallback: min(10, 1 + 복잡한 키워드 개수 + 라인 수 보정)
- **의미**: 높을수록 구현하기 어려운 코드

### 5. developer_level (필요 개발자 수준)
- **범위**: Entry/Junior/Mid/Senior/Architect
- **설명**: 해당 코드를 이해하고 수정할 수 있는 개발자 수준
- **계산 방식**:
  - AI 분석: 5단계 중 선택
  - Fallback: levels[min(4, (difficulty - 1) // 2)]
- **의미**: 코드 복잡도에 따른 필요 개발자 경력

### 6. pattern_score (패턴 사용 점수)
- **범위**: 1-10
- **설명**: 디자인 패턴 사용도
- **계산 방식**:
  - AI 분석: 1-10 범위로 평가
  - Fallback: min(10, 1 + class, interface, factory 키워드 개수)
- **의미**: 높을수록 좋은 설계 패턴 사용

### 7. optimization_score (최적화 점수)
- **범위**: 1-10
- **설명**: 코드 최적화 수준
- **계산 방식**:
  - AI 분석: 1-10 범위로 평가
  - Fallback: min(10, 5 + cache, async, parallel 키워드 개수)
- **의미**: 높을수록 성능 최적화가 잘 된 코드

### 8. best_practices_score (모범사례 준수도)
- **범위**: 1-10
- **설명**: 코딩 모범사례 준수 정도
- **계산 방식**:
  - AI 분석: 1-10 범위로 평가
  - Fallback: min(10, 1 + try:, def, class 키워드 개수)
- **의미**: 높을수록 좋은 코딩 관례를 따르는 코드

### 9. 추가 계산 항목들
- **total_lines**: 전체 라인 수 (제한 없음)
- **code_lines**: 실제 코드 라인 수 (주석/빈 줄 제외)
- **comment_lines**: 주석 라인 수
- **code_comment_ratio**: 코드/주석 비율 (소수점 2자리)
- **tech_stack_identification**: 사용된 기술 스택 (문자열)
- **language**: 프로그래밍 언어
- **tech_stack**: 기술 스택 배열

### 특징
- AI 분석 실패 시 Fallback 분석으로 대체
- 대부분 항목이 1-10 또는 1-100 범위로 정규화됨
- 실제 값은 키워드 빈도와 코드 구조를 기반으로 계산