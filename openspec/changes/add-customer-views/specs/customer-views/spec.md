## ADDED Requirements

### Requirement: 고객별 문의 이력을 읽기 전용으로 본다 (FR-초안-01)
고객 관리 화면은 고객 목록(문의 수·미해결 수·최근 문의 시각), 고객 상세의 문의 이력(접수 시각 내림차순), 나라별 고객·문의 수를 ref.customer와 svc 값 그대로 보여야 한다(MUST). 고객 정보를 고치는 주소는 없어야 한다(MUST).

#### Scenario: 고객 상세 이력
- **GIVEN** CSV1-000017(고객 CUST-0350)을 접수한 상태
- **WHEN** CUST-0350 상세를 연다
- **THEN** 그 티켓(원본 번호 CSV1-000017)이 문의 이력에 있고 이력은 접수 시각 내림차순이다

#### Scenario: 나라별 고객 수
- **GIVEN** ref.customer를 적재한 상태
- **WHEN** 나라별 집계를 연다
- **THEN** TH의 고객 수가 33이다

#### Scenario: 없는 고객
- **GIVEN** 없는 고객 ID
- **WHEN** 상세를 요청한다
- **THEN** 404 "고객을 찾을 수 없음"이 온다
