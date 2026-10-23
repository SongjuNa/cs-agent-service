# Spec Delta: intake-simulator

## Purpose

외부 채널 연동 대신 시연·테스트 담당자가 문의를 입력하거나 운영진 데이터에서 불러와 접수하고, 처리 흐름이 실패하면 같은 티켓으로 다시 시도한다(명세서 v1.5 FR-001, FR-003).

## ADDED Requirements

### Requirement: 접수 검증과 저장 (FR-001)
접수 API는 채널·고객·제품·언어·본문·접수 시각을 검사해 실패하면 항목별 오류를 돌려주고 티켓을 만들지 않아야 한다(MUST)(근거: FR-001 처리 1, 예외 표). 통과하면 NEW 티켓, INQUIRY 메시지, NEW 상태 이력을 남기고 처리 흐름을 시작해야 하며, 제목과 보낸 사람 연락처는 저장만 하고 처리 흐름 입력에 넣지 않아야 한다(MUST)(근거: FR-001 처리 2~4, 입력 표, AC-001-3).

#### Scenario: AC-001-1 정상 접수
- **GIVEN** 유효한 채널·고객·언어·본문
- **WHEN** 접수한다
- **THEN** 상태 NEW인 티켓이 생기고 INQUIRY 메시지와 NEW 상태 이력이 각 1건이며 처리 흐름이 시작된다

#### Scenario: AC-001-2 미등록 고객
- **GIVEN** customers.csv에 없는 customer_id
- **WHEN** 접수한다
- **THEN** 티켓이 생기지 않고 customer_id 항목에 "고객 ID를 찾을 수 없음"이 온다

#### Scenario: AC-001-3 제목은 분류 입력에 없다
- **GIVEN** 제목을 넣은 티켓
- **WHEN** 처리 흐름이 돈다
- **THEN** 실행 로그의 분류 호출 입력에 제목이 없다

### Requirement: 다시 시도 (FR-001 예외 4행)
처리 흐름이 실패한 티켓은 NEW로 남아야 하고, 다시 시도하면 같은 티켓으로 새 실행에서 처리 흐름이 다시 돌아야 한다(MUST)(근거: FR-001 예외 4행, AC-001-4, 기술 명세서 §2-4 재처리).

#### Scenario: AC-001-4 실패 후 다시 시도
- **GIVEN** 언어 모델 호출이 실패하는 상태
- **WHEN** 접수하고 다시 시도한다
- **THEN** 처음에는 티켓이 NEW로 남고 실행이 FAILED이며, 다시 시도하면 같은 ticket_id로 새 RETRY 실행이 돌아 처리된다

### Requirement: 시연용 불러오기 (FR-003)
불러오기 API는 운영진 문의 번호로 `gold.v_inputs`의 입력 열 6개만 돌려줘야 하고, 제목과 정답 열은 돌려주지 않아야 하며, data_split과 상관없이 4,000건 모두를 불러와야 한다(MUST)(근거: FR-003 처리 1~3, CLAUDE.md 규칙 6). 팀 정답지 문의면 채점용 표시를 함께 돌려줘야 한다(MUST)(근거: FR-003 처리 2).

#### Scenario: AC-003-1 추적표 CSV1-000017
- **GIVEN** CSV1-000017
- **WHEN** 불러온다
- **THEN** channel=PHONE, customer_id=CUST-0350, product_code=ACB-AS-2000, language=en, 본문, received_at=2025-10-02 09:45:43이 오고 제목·정답 열은 없다

#### Scenario: AC-003-2 평가용 문의
- **GIVEN** v1.3에서 평가용(test)이라 막혔던 CSV1-001112
- **WHEN** 불러온다
- **THEN** 다른 문의와 똑같이 입력 열이 온다

### Requirement: 접수 시뮬레이터 화면 (SCR-01)
`/intake` 화면은 접수 폼, 문의 번호로 불러오기 팝업, 원본 표시와 채점용 문의 배지, 칸별 오류를 보여야 하고, 접수에 성공하면 티켓 상세로 옮겨야 한다(MUST)(근거: 화면 정의서 v1 SCR-01, SCR-01-P1, FR-001 처리 5).

#### Scenario: 불러와 접수
- **GIVEN** 접수 시뮬레이터 화면
- **WHEN** CSV1-000017을 불러와 [접수]를 누른다
- **THEN** 6칸이 채워지고 "원본 CSV1-000017에서 불러옴"이 보이며, 접수 뒤 새 티켓의 상세 화면으로 옮긴다
