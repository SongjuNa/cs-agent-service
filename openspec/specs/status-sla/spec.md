# status-sla Specification

## Purpose
하위 문의 상태를 허용 전이표대로만 바꾸고 이력을 사건 시각으로 남기며, SLA 두 시계를 이력에서 계산해 보인다(명세서 v1.5 FR-025, FR-026, 기술 명세서 v1.4 §6-4).

## Requirements

### Requirement: 상태는 허용 전이표대로만 바뀌고 이력이 남는다 (FR-025)
상태는 `svc.transition()` 하나로만 바꾸고, 허용 전이표에 없는 전이는 거부해야 한다(MUST)(근거: 명세서 FR-025 처리 1, 기술 명세서 §6-4). 전이마다 이전·새 상태, 사건 시각, 주체, 사건 종류를 이력에 남겨야 한다(MUST)(근거: FR-025 처리 2). 처리 흐름이 끝나면 NEW인 문의를 IN_PROGRESS로(전이가 실패하면 NEW로 두고 실행 PARTIAL), 정보 요청을 발송하면 WAITING_CUSTOMER로, 최종 답변을 발송하면 RESOLVED로 바꿔야 한다(MUST)(근거: 기술 명세서 §2-2 T6 행과 실패 칸, 명세서 FR-001 처리 4, FR-031 처리 4). 발송 때 전이표에 없는 전이면 발송 기록은 남기고 상태는 그대로 두며 실행 로그를 남겨야 한다(MUST)(근거: FR-031 예외 3행). 같은 문의를 동시에 바꾸면 먼저 저장된 것만 반영해야 한다(MUST)(근거: FR-025 예외 2행).

#### Scenario: AC-025-1 정보 요청 발송
- **GIVEN** CSV1-000017을 접수해 처리 흐름이 끝난 문의
- **WHEN** 정보 요청(serial_no)을 승인·발송한다
- **THEN** 상태가 IN_PROGRESS → WAITING_CUSTOMER로 바뀌고 이력에 발송 시각·상담원 ID·사건 INFO_REQUEST_SENT가 남는다

#### Scenario: AC-025-4 허용되지 않은 전이
- **GIVEN** NEW 상태 문의
- **WHEN** RESOLVED로 바로 바꾸려 한다
- **THEN** "현재 상태(NEW)에서는 할 수 없는 작업"으로 거부되고 상태는 NEW 그대로다

#### Scenario: 동시 변경
- **GIVEN** 상담원 두 명이 같은 version을 읽은 문의
- **WHEN** 한 명이 먼저 발송한 뒤 다른 한 명이 그 version으로 바꾸려 한다
- **THEN** 뒤 요청은 "다른 사용자가 먼저 변경함. 새로고침"으로 거부된다

#### Scenario: 발송 때 허용되지 않은 전이
- **GIVEN** 정보 요청을 보내 WAITING_CUSTOMER인 문의의 답변 초안
- **WHEN** 승인·발송한다
- **THEN** SENT 행은 남고 상태는 WAITING_CUSTOMER 그대로이며, 안내 "현재 상태(WAITING_CUSTOMER)에서는 할 수 없는 작업 — 메시지만 기록됨"과 실행 기록 T6 FAILED가 남는다

#### Scenario: AC-031-2 상태 부분 최종 답변 발송
- **GIVEN** CSV1-000004 답변 초안
- **WHEN** 승인·발송한다
- **THEN** 상태가 RESOLVED가 되고 해결 시각이 발송 시각이다

### Requirement: 168시간 무응답이면 시스템이 종료한다 (FR-025)
기준 시각을 받아 WAITING_CUSTOMER 문의의 마지막 정보 요청 발송 뒤 168시간 회신이 없으면 CLOSED(final_action = CLOSED_NO_RESPONSE)로, RESOLVED 문의의 마지막 최종 답변 발송 뒤 168시간 회신이 없으면 CLOSED로 바꿔야 하며, 전이 시각은 그 발송 시각 + 168시간이어야 한다(MUST)(근거: 명세서 FR-025 처리 4·4-1, D20, D22, 기술 명세서 §6-4 주기 점검 3·4).

#### Scenario: AC-025-3 시계 돌리기 무응답 종료
- **GIVEN** CSV1-000085의 입력으로 만든 문의에 정보 요청을 2025-10-09 18:55:19에 발송, 회신 없음
- **WHEN** 기준 시각 2025-10-16 18:55:19로 점검한다
- **THEN** 상태가 CLOSED, final_action = CLOSED_NO_RESPONSE이고 종료 시각이 정답지 resolved_at_utc와 같다

#### Scenario: 해결 뒤 168시간 종료
- **GIVEN** 최종 답변을 보내 RESOLVED가 된 문의
- **WHEN** 발송 시각 + 168시간이 되기 전과 된 뒤에 점검한다
- **THEN** 전에는 그대로이고 뒤에는 CLOSED(NO_REPLY_168H_AFTER_RESOLVED)가 된다

### Requirement: SLA 두 시계를 이력에서 계산해 보인다 (FR-026)
1차 응답 시계는 멈추지 않고 해결 시계는 WAITING_CUSTOMER 구간을 빼서, 저장하지 않고 기준 시각마다 계산해야 한다(MUST)(근거: 명세서 FR-026 처리 1~4, 기술 명세서 §6-4). 상세 API는 하위 문의마다 상태, 두 시계, 남은 시간, 대기 시간 합, 이력, 대기 구간, 해결 시각과 티켓 대표 상태를 돌려줘야 한다(MUST)(근거: FR-025·026 출력, FR-025 처리 5). 목표가 없으면 "SLA 미정", 경과가 음수면 0과 "시간 기록 확인 필요"를 보여야 한다(MUST)(근거: FR-026 예외 1·3행).

#### Scenario: AC-026-1 CSV1-000017
- **GIVEN** CSV1-000017을 정답지 시각으로 재생(1차 응답 1.34h, 대기 30.8h, 목표 1h/24h)
- **WHEN** 계산한다
- **THEN** 1차 응답 BREACHED, 해결 경과 약 8.76h(정답 8.7h와 0.1h 이내), 해결 MET

#### Scenario: AC-026-2 대기 중 문의
- **GIVEN** CSV1-003578(WAITING_CUSTOMER, 대기 100.9h)을 재생
- **WHEN** 기준 시각 = 스냅샷으로 계산한다
- **THEN** 해결 경과 105.5h, ON_TRACK, 1차 응답 BREACHED

#### Scenario: AC-026-3 위험
- **GIVEN** CSV1-003401(IN_PROGRESS, 목표 360h)을 재생
- **WHEN** 기준 시각 = 스냅샷으로 계산한다
- **THEN** 경과 323.0h(계산 322.94h, 오차 0.1h 이내) → AT_RISK

#### Scenario: AC-026-4 1차 응답 없음
- **GIVEN** CSV1-003950(NEW, 1차 응답 없음, 목표 16h)을 재생
- **WHEN** 기준 시각 = 스냅샷으로 계산한다
- **THEN** 1차 응답 경과 20.0h → BREACHED

#### Scenario: AC-026-5 무응답 종료
- **GIVEN** CSV1-000085(CLOSED_NO_RESPONSE)를 재생
- **WHEN** 계산한다
- **THEN** 해결 상태 N/A

#### Scenario: AC-026-6 운영진 데이터 재생 채점
- **GIVEN** 운영진 데이터 4,000건을 정답지 시각으로 scoring 스키마에 재생
- **WHEN** 스냅샷 기준으로 채점한다
- **THEN** SLA 목표·해결 상태는 100% 일치하고, 1차 응답 상태는 D19 두 건(C-53), 경과(오차 0.1h, D19 10건 제외)는 무응답 종료 159건(C-54)만 어긋나며, 결과를 eval_run·eval_case·eval_summary와 csv로 남긴다

#### Scenario: AC-025-5 상태 재생 기록
- **GIVEN** 위 재생
- **WHEN** 이력을 본다
- **THEN** 4,000건 모두 상태 이력이 생기고 그 건수를 기록한다(일치율 대신 생성·존재 기록, 기술 명세서 §10-3)
