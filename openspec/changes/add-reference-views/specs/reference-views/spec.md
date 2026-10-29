## ADDED Requirements

### Requirement: 근거 문서를 읽기 전용으로 본다 (FR-초안-02)
문서 목록은 ref.document 107행을 모두 보여야 하고, 문서마다 청크 수를 보여 청크가 없는 문서에는 "색인 없음"을 보여야 한다(MUST). 문서를 고치는 주소는 없어야 한다(MUST).

#### Scenario: 문서 목록
- **GIVEN** ref.document를 적재한 상태
- **WHEN** 문서 관리 화면을 연다
- **THEN** 107행이 보이고 청크가 0인 문서에는 "색인 없음"이 보인다

### Requirement: 제품 기준값을 읽기 전용으로 본다 (FR-초안-03)
제품 상세는 단가, 표준 납기, 사양값, 규격, 인증, 펌웨어 출시 이력을 ref 표 값 그대로 보여야 한다(MUST).

#### Scenario: 단가와 납기
- **GIVEN** CSV1-000004의 제품
- **WHEN** 제품 상세를 연다
- **THEN** 단가 520 USD와 표준 납기 4주가 보인다

### Requirement: 규칙표를 읽기 전용으로 본다 (FR-초안-04)
규칙 보기는 우선순위·배정·필수 정보·SLA 규칙표 행을 원본 순서대로 보여야 하고, 규칙을 고치는 주소는 없어야 한다(MUST).

#### Scenario: 우선순위 규칙
- **GIVEN** ref.priority_rule을 적재한 상태
- **WHEN** 규칙 보기의 우선순위 탭을 연다
- **THEN** PR-02 행의 조건이 AC-030-2의 「왜?」 문구와 같다

#### Scenario: 없는 규칙 종류
- **GIVEN** 규칙 종류 "unknown"
- **WHEN** 요청한다
- **THEN** 404가 온다
