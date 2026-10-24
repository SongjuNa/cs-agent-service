# Proposal: 이관 처리 (add-escalation)

## Why

상담원이 이관 후보(FR-020)를 보거나 직접 판단해 전문 부서로 이관을 확정해야 한다. 문의는 ESCALATED가 되고 이관 부서 접수함에도 보여야 한다(근거: 명세서 v1.5 FR-033 기능 설명). 이번 변경은 FR-033 처리 1~7(이관 확정까지)이고, 이관 부서의 [회신 등록]과 예외 부서 메일(처리 8~10)은 다음 변경 25가 한다(근거: 3순위_시작_전후비교.md §3 변경 순서(Claude 제안), 조장 승인 2026-10-24 "네 승인합니다". 예외 부서 메일(FR-031 처리 9)은 FR-033의 마지막 변경 25에서 함께 만든다, openspec/config.yaml).

## What Changes

- **이관 API (FR-033 처리 1~4)**: `POST /sub-tickets/{sub_ticket_id}/escalate`(dept, reason_code 필수, memo 선택). IN_PROGRESS에서만 받는다. sub_ticket에 escalated = true, escalated_to, escalation_reason을 쓰고, 상태를 ESCALATE 전이로 ESCALATED로 바꾸며, 원래 담당 부서(assigned_dept)는 그대로 둔다(근거: FR-033 처리 1~3, 기술 명세서 v1.4 §8-1, §6-4 전이표 "IN_PROGRESS → ESCALATED, ESCALATE(사유 필수)").
  - 이관 메모를 메시지 이력에 ESCALATION_NOTE, SENT(sender AGENT)로 남긴다(근거: FR-033 처리 4, FR-035, schema.sql ticket_message_kind_combo).
  - 이관 시각·주체는 ticket_status_history의 ESCALATE 행이다(근거: §5-6 저장, §6-2 표 ticket_status_history).
  - 예외 4개: 사유 없음 "이관 사유를 고르세요", 이미 ESCALATED "이미 이관됨({부서})", 같은 부서 "같은 부서로는 이관할 수 없음", 처리 중이 아님 "처리 중인 문의만 이관할 수 있음"(근거: FR-033 예외 처리 표 3행, 화면 정의서 v1 SCR-03-P4 오류 문구 4개). 처리 중이 아닌 거부는 FR-025 예외 1행대로 실행 로그에도 남긴다(근거: FR-025 예외 1행, 구현 선택 C-157).
  - 고객에게 가는 이관 안내 초안은 만들지 않는다(근거: FR-033 처리 5, openspec/config.yaml).
- **접수함·나의 업무 현황 (FR-033 처리 6)**: 이관 부서 접수함에 "{원 부서}에서 이관됨"으로, 원래 부서 접수함에도 남는다. 이미 2순위에서 만든 화면이 escalated_to를 읽으므로 이 변경으로 실제 데이터가 생긴다(근거: FR-033 처리 6, FR-029 처리 1, §8-1 `GET /tickets`, `backend/app/db/inbox.py`, `workload.py`).
- **SLA (FR-033 처리 7)**: ESCALATED 동안 해결 시계는 멈추지 않는다(근거: FR-033 처리 7, §6-4 SLA 함수 주석). 코드는 이미 그렇다.
- **티켓 상세 화면**: "보낼 것" 탭의 [이관] 버튼(지금은 비활성 "3순위")을 켜고 이관 팝업 P4(이관 부서 기본 = 이관 후보 부서, 사유 11값, 메모)를 단다. 근거 줄 ⑤ 부서에 ESCALATED면 "→ {이관 부서} ({사유}, {시각})"를 보인다(근거: 화면 정의서 v1 SCR-03 R-07·P4·C-04·CP-6, 조장 결정 2026-10-23 기존 레이아웃 유지).

## Capabilities

### New Capabilities
- `escalation`: 하위 문의 이관 확정(ESCALATED 전이, 이관 부서·사유, 이관 메모)과 그 표시.

## 범위 밖

- **이관 부서 [회신 등록], 예외 부서 고객 메일, 부서별 작성 영역**: 다음 변경 25 add-dept-reply(근거: FR-033 처리 8·9, FR-031 처리 9, 3순위_시작_전후비교.md §3).
- **고객 이관 안내 초안**: 여유 시 FR-048(근거: FR-033 처리 5).
- **시연용 상담원 ID(처리 10, AC-033-8)**: 변경 21 add-agent-roster에서 이미 만들었다(근거: `backend/app/roster/agent_roster.json`, `test_agent_roster.py`).
- **팀 정답지 재생(AC-033-5)**: 팀 정답지 적재(W9)가 없어 tickets.csv의 이관 행으로 대신한다(근거: 결정 기록 C-3·C-137·C-147 선례, 구현 선택).

## Impact

- 새 파일: `backend/app/status/escalation.py`(이관 확정), 시험 `backend/tests/acceptance/test_escalation.py`(근거: design 결정 1~4).
- 고치는 파일: `backend/app/api/sub_tickets.py`(API), `backend/app/db/detail.py`(상세 응답·⑤ 줄), `frontend/src/TicketDetailPage.tsx`·`ActionPopups.tsx`·`api.ts`(근거: design 결정 2·3).
- DB 구조는 고치지 않는다. 쓰는 열과 전이는 테이블 정의서 v1.3에 이미 있다(근거: CLAUDE.md 규칙 4, schema.sql sub_ticket.escalated·escalated_to·escalation_reason, status_transition ESCALATE).
