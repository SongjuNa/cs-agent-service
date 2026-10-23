# Design: 우선순위 조정과 SLA 재계산

## Context

동기는 proposal.md의 Why를 본다. 따를 기준은 다음과 같다(근거: 아래 문서들).
- 명세서 v1.5 FR-028(처리 1~6, 예외 3행, AC-028-1~3), FR-014 처리 5, FR-027 처리 6·AC-027-5.
- 기술 명세서 v1.4 §5-4(목표 복사 저장, 조정 때 덮어쓰기), §8-1(`POST /sub-tickets/{id}/priority`, 입력 new_priority, reason_kind, reason_text), §10-1 3.
- 화면 정의서 v1 SCR-03-P3(입력, 미리 보기, 오류 문구, 결과).
- schema.sql: svc.priority_adjustment(reason_kind 3값, reason 비어 있지 않음, from ≠ to, INSERT만), sub_ticket.priority·priority_adjusted_by_agent·sla_id·목표 두 열·version.

## Goals / Non-Goals

**Goals**
- 사유가 있는 조정만 받아 목표를 다시 정하고 경고를 다시 점검하며 이력을 남긴다(근거: FR-028 처리 1~5).

**Non-Goals**
- 화면, 현황 집계(proposal "범위 밖") (근거: proposal 범위 밖).

## Decisions

### 1. 조정 함수 (`app/sla/adjust.py`)

`preview(conn, sub_ticket_id, new_priority, at)`과 `adjust(conn, sub_ticket_id, new_priority, reason_kind, reason, agent_id, at, confirm_breach=False, expected_version=None)` (구현 선택. 이름은 기술 명세서에 없음).

| 단계 | 정한 것 | 근거 |
|---|---|---|
| 입력 확인 | reason_kind나 reason이 비면 "조정 사유를 입력하세요"(400). reason_kind가 3값 밖이면 "사유 분류는 CUSTOMER_REQUEST·IMPACT_REASSESSED·OTHER"(400), new_priority가 P1~P4 밖이면 "우선순위는 P1~P4"(400) | FR-028 처리 1·6, 예외 1행, schema.sql CHECK. 뒤 두 문구와 응답 코드는 구현 선택 |
| 상태 확인 | RESOLVED·CLOSED면 "종료된 문의는 바꿀 수 없음"(409) | FR-028 예외 2행. 409는 구현 선택(입력이 틀리면 400, 문의 상태 때문이면 409) |
| 같은 값 | 지금 priority와 같으면 "현재와 같은 우선순위"(409) | FR-028 처리 1, 화면 정의서 v1 P3 오류 문구 |
| 우선순위 없음 | 처리 실패로 priority가 비면 "우선순위가 없는 문의"(409) | priority_adjustment.from_priority NOT NULL. 명세서 FR-011·FR-014 예외 1행은 이때 조정으로 직접 지정하라고 하므로 문서끼리 다름(C-68). 문구는 구현 선택 |
| 목표 조회 | `find_sla_target(category_code, ticket.customer_tier, new_priority)`(1순위 규칙 엔진). 정책 행이 없으면 목표 NULL | FR-014 처리 1~3·5, 예외 2행 |
| 즉시 위반 | 새 목표로 계산한 해결 경과 > 새 해결 목표, 또는 1차 응답 전이고 1차 응답 경과 > 새 1차 응답 목표인데 지금은 위반이 아니면, confirm_breach가 없을 때 409 "이 조정으로 SLA 위반 상태가 됩니다. 계속할까요?" + 미리 보기 | 화면 정의서 v1 P3 미리 보기(C-65). 문구는 FR-028 예외 3행(C-66) |
| 저장 | 한 트랜잭션: sub_ticket 행을 잠그고(expected_version이 다르면 "다른 사용자가 먼저 변경함. 새로고침") priority, priority_adjusted_by_agent = true, sla_id, 목표 두 열, version + 1을 쓰고 priority_adjustment 1행 | FR-028 처리 2·3·5, FR-025 예외 2행, schema.sql version "동시 수정". version을 올리는 것은 구현 선택 |
| 경고 재점검 | 저장 트랜잭션이 끝난 뒤 그 문의만 raise_alerts·clear_alerts(as_of = 조정 시각). 점검이 실패해도 조정은 남고 5분 주기 점검이 다시 단다 | FR-028 처리 4, FR-027 처리 6, 화면 정의서 v1 P3 "경고 재평가". 트랜잭션을 나눈 것은 구현 선택 |
| 돌려주는 값 | priority, adjusted, from/to 목표·sla_id, 다시 계산한 sla(10번의 clocks), 새 경고·해제 경고, 조정 이력 줄 | FR-028 출력. "다시 판정한 SLA 상태"는 계산값으로 돌려주고 저장 열 sla_first_response_status·sla_resolution_status는 쓰지 않는다(구현 선택. 1순위·10번 코드도 이 열을 쓰지 않음) |

- 경과는 바꾸지 않는다. 목표만 바뀌므로 inquiry_sla가 새 목표로 상태를 다시 판정한다(근거: FR-028 처리 4, FR-026 처리 6).
- FR-028 예외 3행은 "그대로 반영하고 확인 창"이고 화면 정의서 v1 P3는 미리 보기에서 경고한 뒤 [조정]이다. 반영 전에 확인을 받는 화면 정의서 쪽을 따른다(C-65). (근거: 명세서 FR-028 예외 3행, 화면 정의서 v1 SCR-03-P3)

### 2. API (`app/api/sub_tickets.py`)

- `POST /sub-tickets/{sub_ticket_id}/priority` 입력 `{new_priority, reason_kind, reason_text, confirm_breach?, expected_version?}`, 헤더 X-Agent-Id(근거: 기술 명세서 §8-1, 화면 정의서 v2 0-3). 없으면 400 "상담원 ID를 입력하세요"(구현 선택. 발송 API messages.py와 같음). X-Agent-Dept는 조정에 쓰지 않는다(구현 선택).
- `GET /sub-tickets/{sub_ticket_id}/priority?new_priority=P3`: 저장 없이 미리 보기(이전·새 목표, sla_id, 즉시 위반 여부)(구현 선택. 화면 정의서 v1 P3 미리 보기용).
- 없는 문의는 404 "문의를 찾을 수 없음"(구현 선택).

### 3. 경고 함수 좁히기

- 11번의 due_alerts·raise_alerts·clear_alerts에 선택 인자 `sub_ticket_ids`를 더해 그 문의만 점검한다. 주기 점검은 지금처럼 전체를 본다(구현 선택).

### 4. 상세 API

- 하위 문의 `state`에 priority, priority_rule_id, priority_adjusted_by_agent를 더하고, `adjustments`(priority_adjustment 시각순, 열 이름 그대로)를 더한다(근거: FR-028 출력 "변경 이력", 화면 정의서 v1 C-03).

### 5. 시험 (`tests/acceptance/test_priority_override.py`)

- AC-028-1: CSV1-000031(MANUAL × STANDARD)을 svc에 끝나지 않은 문의로 만들고, 정답 행 priority는 이미 조정값 P3이므로 규칙 PR-07의 P4·72/168h를 시작값으로 넣은 뒤 P3로 조정 → 24/120h, SLA-MANUAL-STANDARD-P3, priority_rule_id PR-07 그대로, 조정 표시 켜짐, 이력에 이전·새 값과 사유(근거: AC-028-1).
- AC-028-2: 사유가 빈 칸이면 400이고 값이 그대로(근거: AC-028-2).
- AC-028-3: 운영진 데이터의 조정 120건에서 정답 우선순위로 다시 조회한 목표가 정답 목표 두 열과 100% 같다(근거: 기술 명세서 §10-1 1·3번, C-67). 조정 함수를 거치는 재생이 아니고, 기존 `tests/rules/test_reproduce_gold.py::test_w1_6_sla_target`(4,000건)의 120건 부분과 같은 확인이다.
- AC-027-5: CSV1-000031을 P4로 두고 접수 + 130h에 점검해 RES_AT_RISK가 있는 상태에서 P3로 올리면 RES_BREACHED가 새로 생긴다(근거: AC-027-5). 시험은 위반 확인(confirm_breach)을 넣는다. 명세서 AC-027-5에 없는 조건이며 C-65의 결과다.
- 같은 우선순위 거부, 종료 문의 거부, 즉시 위반 확인 요구, 목표가 늘면 경고 해제, API 미리 보기·조정, 동시 수정 거부, 언어 모델 import 금지(근거: FR-028 처리 1, 예외 2·3행, FR-027 처리 6, FR-025 예외 2행, 명세서 그룹 4 머리).

## Risks / Trade-offs

- C-60: 목표가 늘어 해제된 경고는 같은 종류로 다시 달 수 없다. 조정을 여러 번 하면 경고가 사라진 채로 남을 수 있다(근거: 개발_결정_기록 C-60).
