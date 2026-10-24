# Spec Delta: escalation

## Purpose

C/S 상담원이 하위 문의를 전문 부서로 이관 확정하고, 그 문의가 ESCALATED로 이관 부서 접수함에도 보이게 한다(명세서 v1.5 FR-033 처리 1~7).

## ADDED Requirements

### Requirement: 이관 확정 (FR-033)
시스템은 IN_PROGRESS인 하위 문의에서만 이관 부서와 이관 사유(필수)를 받아 상태를 ESCALATED로 바꾸고, 이관 부서·사유를 그 하위 문의에 기록하며, 이관 메모를 ESCALATION_NOTE SENT로 남겨야 하고, 원래 담당 부서는 바꿔서는 안 된다(MUST)(근거: FR-033 처리 1~4). 사유가 없거나, 이미 ESCALATED이거나, 이관 부서가 원래 담당 부서와 같으면 거부하고 상태를 그대로 두어야 한다(MUST)(근거: FR-033 예외 표). 처리 중이 아닌 문의의 이관 요청은 거부하고 실행 로그에 남겨야 한다(MUST)(근거: FR-033 처리 1, FR-025 예외 1행). 고객에게 가는 이관 안내 초안은 만들지 않아야 한다(MUST)(근거: FR-033 처리 5).

#### Scenario: AC-033-1 FIELD_SVC로 이관
- **GIVEN** 처리가 끝난 CSV1-000017(이관 후보 FIELD_SVC)
- **WHEN** 사유 ONSITE_REQUIRED로 FIELD_SVC에 이관하면
- **THEN** 상태 ESCALATED, 이관 부서 FIELD_SVC로 기록되고 FIELD_SVC 접수함에 "이관됨" 표시로 나타나며, 이관 안내 초안은 생기지 않는다

#### Scenario: AC-033-2 사유 없음
- **GIVEN** 사유가 빈 상태
- **WHEN** 이관하면
- **THEN** 거부되고("이관 사유를 고르세요") 상태는 그대로다

#### Scenario: AC-033-4 SLA는 멈추지 않음
- **GIVEN** ESCALATED인 문의
- **WHEN** 시간이 지난 뒤 SLA를 보면
- **THEN** 해결 경과가 계속 늘어난다

#### Scenario: AC-033-5 정답 이관 재생
- **GIVEN** 정답에서 이관된 행(팀 정답지 대신 tickets.csv)
- **WHEN** 상담원 대신 정답 이관 부서(사유는 필수라 정답 사유를 함께)로 이관을 재생하면
- **THEN** 상태 전이와 기록이 오류 없이 끝난다(참고 지표)

### Requirement: 이관 화면 (FR-033)
티켓 상세는 "보낼 것" 탭의 [이관] 버튼을 IN_PROGRESS인 하위 문의가 있을 때만 켜고, 팝업에서 이관 부서(기본 = 이관 후보 부서)·사유(11값)·메모를 받아야 하며, 이관된 문의의 부서 줄에 "→ {이관 부서} ({사유}, {시각})"를 보여야 한다(MUST)(근거: 화면 정의서 v1 SCR-03 R-07·P4·C-04, FR-033 입력).

#### Scenario: AC-033-1 상세의 이관 표시
- **GIVEN** FIELD_SVC로 이관된 CSV1-000017
- **WHEN** 티켓 상세를 열면
- **THEN** 부서 줄에 "→ FIELD_SVC (ONSITE_REQUIRED, {시각})"가 보이고 이력에 이관 메모가 있다
