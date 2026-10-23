# Spec Delta: customer-reply

## Purpose

상담원이 대신 입력한 고객 회신을 메시지 이력에 남기고, 대기를 끝내고, 회신에서 제공 항목을 다시 뽑아 새 초안을 만든다(명세서 v1.5 FR-032, FR-035).

## ADDED Requirements

### Requirement: 회신을 저장하고 상태를 바꾼다 (FR-032 처리 1·2)
회신은 CUSTOMER_REPLY RECEIVED 한 행으로 원문 저장해야 한다(MUST)(근거: FR-032 처리 1, FR-035 처리 2·5). 대상 문의가 WAITING_CUSTOMER나 RESOLVED면 IN_PROGRESS로 바꿔야 하고, 그 밖의 상태는 그대로 두고 저장만 해야 한다(MUST)(근거: FR-032 처리 2, FR-025 예외 3행). 빈 본문, 미래 시각, 요청 발송보다 앞선 시각은 거부해야 하고, 종료 문의는 메시지만 저장해야 한다(MUST)(근거: FR-032 입력, 예외 1~3행).

#### Scenario: AC-032-3 대기 구간이 닫힌다
- **GIVEN** CSV1-003578(product_model 정보 요청 발송 2026-09-26 19:07:45, WAITING_CUSTOMER)
- **WHEN** 스냅샷 시각에 회신을 입력한다
- **THEN** 대기 구간이 회신 시각에 닫히고 대기 시간 합이 100.9h(100.85h)로 확정된다

#### Scenario: AC-025-2 대기 구간 1개
- **GIVEN** WAITING_CUSTOMER인 문의
- **WHEN** 회신을 입력한다
- **THEN** IN_PROGRESS가 되고 대기 구간(들어간 시각, 나온 시각) 1개가 남는다

#### Scenario: 대기 중이 아닌 문의의 회신
- **GIVEN** IN_PROGRESS 문의
- **WHEN** 회신을 입력한다
- **THEN** 상태는 그대로이고 회신은 메시지 이력에만 저장된다

#### Scenario: AC-032-5 요청보다 앞선 회신
- **GIVEN** 정보 요청을 발송한 문의
- **WHEN** 발송보다 앞선 시각으로 회신을 입력한다
- **THEN** "회신 시각은 요청 발송 이후여야 합니다"로 거부되고 아무것도 저장되지 않는다

#### Scenario: 종료 문의 회신
- **GIVEN** CLOSED 문의
- **WHEN** 회신을 입력한다
- **THEN** 메시지만 저장되고 "종료 후 회신으로 기록됨"이 돌아오며 다시 처리하지 않는다

#### Scenario: 해결 뒤 회신
- **GIVEN** 최종 답변을 보내 RESOLVED인 문의
- **WHEN** 168시간 안에 회신을 입력한다
- **THEN** IN_PROGRESS가 되고 해결 뒤 자동 종료가 일어나지 않는다

### Requirement: 회신 뒤 Q1부터 다시 처리한다 (FR-032 처리 3·4)
회신으로 IN_PROGRESS가 된 문의를 원문과 모든 회신으로 Q1부터 다시 돌려야 하고(근거: FR-032 처리 2·3, C-72), 제공 항목은 이전 값을 유지하며 늘기만 해야 한다(MUST)(근거: FR-032 처리 3, 기술 명세서 §2-4). 막는 항목이 남으면 정보 요청 초안(앞 요청과 같은 항목이면 "재요청" 표시)을, 없으면 답변 초안을 만들어야 한다(MUST)(근거: FR-032 처리 4). 다시 처리가 실패해도 회신과 전이는 남아야 한다(MUST)(근거: FR-032 예외 4행).

#### Scenario: AC-032-1 제조번호 회신
- **GIVEN** CSV1-000017이 serial_no 정보 요청 뒤 WAITING_CUSTOMER
- **WHEN** "Serial number is LVB-2024-00117."을 회신으로 입력한다
- **THEN** 상태가 IN_PROGRESS가 되고 대기 구간이 닫히며 제공 항목에 serial_no가 더해져 막는 항목이 비고 TG-ACB-AS-2000을 인용한 답변 초안이 생긴다

#### Scenario: AC-032-2 제조번호 없는 회신
- **GIVEN** 같은 티켓
- **WHEN** "We will check and let you know."를 회신으로 입력한다
- **THEN** 상태는 IN_PROGRESS가 되지만 막는 항목 serial_no가 남아 "재요청" 표시가 붙은 정보 요청 초안이 생긴다

### Requirement: 다시 처리해도 조정값을 지킨다 (FR-011 예외 3행)
흐름이 다시 돌 때 규칙값은 다시 계산하되 상담원이 조정한 우선순위와 SLA 목표는 덮어쓰지 않아야 한다(MUST)(근거: FR-011 예외 3행, C-69).

#### Scenario: 조정값 보존
- **GIVEN** 상담원이 우선순위를 조정한 문의
- **WHEN** 회신 뒤 다시 처리된다
- **THEN** 최종 우선순위와 SLA 목표는 조정값 그대로이고 priority_rule_id는 규칙값이다

### Requirement: 메시지 이력 (FR-035)
메시지 행은 한 번 쓰고 바꾸지 않아야 하며(예외: DRAFT → APPROVED, 임시 저장, 재처리로 밀린 초안의 superseded_at), 티켓의 메시지를 시각순으로, 문의 순번으로 걸러 돌려줘야 한다(MUST)(근거: FR-035 처리 1·7, 기술 명세서 §6-3).

#### Scenario: AC-035-3 접수부터 답변까지
- **GIVEN** 접수 → 정보 요청 발송 → 고객 회신 → 답변 발송까지 돌린 새 티켓
- **WHEN** 메시지를 조회한다
- **THEN** INQUIRY RECEIVED, INFO_REQUEST DRAFT→APPROVED, INFO_REQUEST SENT, CUSTOMER_REPLY RECEIVED, FINAL_REPLY DRAFT→APPROVED, FINAL_REPLY SENT 순으로 있고 1차 응답 시각은 INFO_REQUEST SENT 시각이다

#### Scenario: AC-035-4 발송 행 수정 거부
- **GIVEN** SENT 행
- **WHEN** 본문을 고치려 한다
- **THEN** 거부된다

#### Scenario: AC-032-4 아래 띠 재료 (앞부분)
- **GIVEN** 회신을 입력한 티켓
- **WHEN** 상세의 메시지 이력을 본다
- **THEN** 고객 회신 메시지가 시각순으로 들어 있다(회신 수신 확인 안내는 FR-048, C-71)
