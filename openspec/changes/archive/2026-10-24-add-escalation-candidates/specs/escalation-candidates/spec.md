# Spec Delta: escalation-candidates

## Purpose

진단 후보의 현장 출동·교체 필요 표시, 긴급도, 팀 보충 이관 규칙으로 이관 후보와 예상 이관 부서를 상담원에게 보여 준다(명세서 v1.5 FR-020).

## ADDED Requirements

### Requirement: 이관 후보 판정 (FR-020)
시스템은 하위 문의마다 routing_rules.csv의 이관 행 3개(SAFETY·교체·현장 출동)와 팀 보충 이관 규칙 2개(반품 품질, 설치 P1)로 이관 후보(예상 이관 부서, rule_id, 이유)를 판정해 남겨야 하며, 맞는 행이 없으면 "없음"과 FR-012의 이관 조건 문구를 남기고, 하위 문의의 상태를 바꿔서는 안 된다(MUST)(근거: FR-020 처리 1~6, AC-020-4). 진단이 없으면 SAFETY만 판정하고 "진단 없음 — 이관 조건만 표시"를, 규칙을 읽지 못하면 후보 없이 "이관 규칙을 읽을 수 없음"을 보여야 하며, 맞은 행은 부서별 한 줄로 모두 보여야 한다(MUST)(근거: FR-020 예외 1~3행).

#### Scenario: AC-020-1 SAFETY
- **GIVEN** 긴급도 SAFETY인 고장 문의 CSV1-000202(ESS-BMS-V3)
- **WHEN** 처리하면
- **THEN** 이관 후보가 켜지고 근거 rule_id가 RT-ESC-DEFECT-SAFETY다

#### Scenario: AC-020-2 교체 필요
- **GIVEN** 진단 후보의 교체 필요 표시가 Y인 문의 CSV1-000007(FLT-028)
- **WHEN** 처리하면
- **THEN** RT-ESC-DEFECT-RMA 행의 부서 QA_CLAIM이 예상 이관 부서로 보인다

#### Scenario: AC-020-3 후보 없음
- **GIVEN** 진단 후보가 없고 SAFETY가 아닌 문의
- **WHEN** 처리하면
- **THEN** 이관 후보는 "없음"이고 FR-012의 이관 조건 문구만 보인다

#### Scenario: AC-020-4 상태 그대로
- **GIVEN** 이관 후보가 켜진 문의
- **WHEN** 상태를 보면
- **THEN** 상태는 바뀌지 않는다(ESCALATED가 아님)

#### Scenario: AC-020-5 재현율 보고
- **GIVEN** 정답에서 이관된 행(팀 정답지 대신 tickets.csv)
- **WHEN** 예상 이관 부서를 정답 이관 부서와 비교하면
- **THEN** 재현율을 보고한다

#### Scenario: AC-020-6 반품 품질
- **GIVEN** 반품 사유 "The unit was dead on arrival and does not power up"인 반품 문의 CSV1-000229
- **WHEN** 처리하면
- **THEN** 이관 후보 QA_CLAIM, 근거 RT-ESC-TEAM-RETURN-QUALITY(팀 규칙)가 보인다

#### Scenario: AC-020-7 포장 파손
- **GIVEN** 반품 사유 "The goods arrived with damaged packaging and a cracked housing"인 반품 문의 CSV1-000200
- **WHEN** 처리하면
- **THEN** 이관 후보는 "없음"이다

#### Scenario: AC-020-8 설치 P1
- **GIVEN** 우선순위 P1인 설치 문의 CSV1-000133
- **WHEN** 처리하면
- **THEN** 이관 후보 FIELD_SVC, 근거 RT-ESC-TEAM-INSTALL-P1(팀 규칙)이 보인다

### Requirement: 이관 후보 표시 (FR-020)
티켓 상세는 하위 문의 구역에 이관 후보 줄("이관 후보: {부서} — {rule_id} ({이유})", 팀 규칙 표시, 없으면 "없음 — 이관 조건: {문구}")과 근거 줄을 버튼 없이 보여야 한다(MUST)(근거: FR-020 출력, 화면 정의서 v1 SCR-03 C-09).

#### Scenario: AC-024-1 상세의 이관 후보 줄
- **GIVEN** 처리가 끝난 CSV1-000017
- **WHEN** 티켓 상세를 열면
- **THEN** 근거 영역에 이관 후보 줄이 보인다
