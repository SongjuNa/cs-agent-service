# Design: 이관 처리

## Context

DB에는 이관에 쓸 열과 전이가 이미 있다: sub_ticket의 escalated·escalated_to·escalation_reason(11값 CHECK, 이관 부서가 있으면 사유 필수), 전이 IN_PROGRESS → ESCALATED(ESCALATE, 사유 없으면 이력 CHECK가 거부), ticket_message의 ESCALATION_NOTE SENT(sender AGENT)(근거: schema.sql sub_ticket·status_transition·ticket_status_history·ticket_message_kind_combo). 접수함은 이미 `assigned_dept = 부서 OR escalated_to = 부서`로 읽고 "{원 부서}에서 이관됨"을 계산하며, 나의 업무 현황은 ESCALATED의 이관 회신 대기와 오늘 이관 수를 ESCALATE 이력에서 센다(근거: `backend/app/db/inbox.py`, `workload.py`, FR-029·047). 이관 후보는 변경 23이 Q9a 결과(부서, 사유 코드)로 남긴다(근거: openspec/specs/escalation-candidates, 변경 23 결정 기록 C-146).

## Decisions

### 1. 이관 확정 (`backend/app/status/escalation.py`)

| 항목 | 정한 것 | 근거 |
|---|---|---|
| 입력 | dept(필수, ref.department 13개 중 하나), reason_code(필수, escalation_reason 11값 중 하나), memo(선택), 상담원 ID(X-Agent-Id, 필수), expected_version(선택) | FR-033 입력, §8-1, FR-025 예외 2행, 구현 선택 C-153 |
| 검사 순서 | 사유 없음 → 이미 ESCALATED → 처리 중 아님 → 같은 부서. 부서·사유 값이 목록 밖이면 거부. 처리 중이 아닌 거부는 화면 정의서 v1 P4 문구 "처리 중인 문의만 이관할 수 있음"으로 돌려주고, FR-025 예외 1행대로 실행 로그(trigger AGENT_EDIT, 단계 T6 FAILED·VALIDATION)에 남긴다. 발송 API의 거부 기록과 같은 모양이다. 버전이 다르면 "다른 사용자가 먼저 변경함. 새로고침" | FR-033 처리 1·2, 예외 표, 화면 정의서 v1 P4 오류 문구, FR-025 예외 1·2행, `app/db/store.py` send_draft 거부 기록, 구현 선택 C-157(문구·순서) |
| 저장 | 한 트랜잭션: sub_ticket escalated = true, escalated_to, escalation_reason → 전이 ESCALATE(reason = 사유 코드, actor = 상담원 ID) → ESCALATION_NOTE SENT(sender AGENT, sent_by_name = 상담원 ID) | FR-033 처리 3·4, §6-4, §5-6 저장, §6-2 ticket_message |
| 메모가 빈 경우 | 메시지 본문을 "이관: {부서} ({사유})"로 쓴다(본문 1자 이상 CHECK). 메모가 있으면 메모 그대로 | schema.sql ticket_message.body CHECK, 구현 선택 C-154 |
| 메모 언어 | 상담원 사이 글이므로 language = 'ko' | 구현 선택 C-155 |
| 개인정보 | 원문 저장, mask_count는 다른 글처럼 가리기 함수로 센다 | 기술 명세서 §7, `app/status/reminder.py` 선례 |
| 원래 부서 | assigned_dept는 바꾸지 않는다 | FR-033 처리 3 |
| SLA | 아무것도 하지 않는다(ESCALATED는 해결 시계를 멈추지 않음) | FR-033 처리 7, §6-4 |
| 다시 처리 | 이관 확정은 그래프를 다시 돌리지 않는다. 다시 돌리는 것은 부서 회신 뒤(변경 25)다. §2-2의 "이관과 회신은 API가 상태를 바꾸고 필요한 노드부터 다시 돌린다"에서 이관 확정 뒤 다시 돌릴 노드가 §2-4 재실행 표에 없다 | §2-2, §2-4 표(이관 부서 회신 행만 있음), 구현 선택 C-158 |

- 이 모듈은 규칙·상태 코드라 언어 모델 호출 계층을 import하지 않는다(근거: CLAUDE.md 규칙 1).

### 2. API (`backend/app/api/sub_tickets.py`)

- `POST /sub-tickets/{sub_ticket_id}/escalate`, 본문 {dept, reason_code, memo, expected_version}, 머리 X-Agent-Id. 거부는 400(사유·부서 값), 409(상태·이미 이관·동시 수정), 404(문의 없음)로 돌려준다(근거: §8-1, FR-028 API와 같은 모양 `post_priority`, 구현 선택).
- 응답: 상태, escalated_to, escalation_reason, 메모 message_id(근거: FR-033 출력).

### 3. 상세 응답과 화면 (`detail.py`, `TicketDetailPage.tsx`, `ActionPopups.tsx`)

- 상세의 하위 문의에 escalated, escalated_to, escalation_reason과 마지막 ESCALATE 시각을 더한다(근거: 화면 정의서 v1 C-04 "→ {이관 부서} ({사유}, {시각})").
- 근거 줄 ⑤ 부서: ESCALATED면 근거에 "→ {이관 부서} ({사유}, {시각})"를 더한다(근거: 화면 정의서 v1 SCR-03 C-04).
- "보낼 것" 탭의 [이관] 버튼: 처리 중(IN_PROGRESS)인 하위 문의가 있을 때 켜진다. 팝업 P4: 하위 문의(복합이면 고름. 화면 정의서 v1 P4 입력에는 없고, [이관] 버튼이 탭에 하나뿐이라 고른다, 구현 선택 C-159), 이관 부서(기본 = 그 문의의 이관 후보 첫 부서, 없으면 비움, 13개), 이관 사유(기본 = 후보의 사유 코드, 11값 CP-6), 메모. 오류는 팝업 안에 보인다(근거: 화면 정의서 v1 R-07·P4·CP-6, FR-033 입력 "기본값 = FR-020의 예상 이관 부서", 변경 23 C-146).
- 이관된 하위 문의는 상태 배지가 ESCALATED가 되고 [이관]이 꺼진다("이미 이관됨")(근거: 화면 정의서 v1 "이관됨" 상태 표).
- 이력 탭은 이미 메시지·상태 이력을 시각순으로 보이므로 이관 메모와 ESCALATE 전이가 함께 나온다(근거: §8-1 timeline, 화면 정의서 v1 B-01).

### 4. 시험 (`tests/acceptance/test_escalation.py`)

- AC-033-1: CSV1-000017을 접수 API로 처리 → 사유 ONSITE_REQUIRED, 부서 FIELD_SVC로 이관 → ESCALATED, escalated_to FIELD_SVC, ESCALATION_NOTE SENT, FIELD_SVC 접수함에 "TS_LV에서 이관됨"과 같은 표시, 이관 안내 초안 없음(근거: AC-033-1, FR-029 처리 1).
- AC-033-2: 사유가 빈 이관 → 400 "이관 사유를 고르세요", 상태 그대로(근거: AC-033-2).
- AC-033-4: ESCALATED 동안 시각을 늘리면 해결 경과가 늘어난다(근거: AC-033-4).
- AC-033-5(참고 지표): tickets.csv에서 이관된 행마다 정답지 입력으로 문의를 만들고(시험 함수 seed, 롤백) 담당 부서를 정답 assigned_dept로 둔 뒤 정답 이관 부서·사유(사유는 필수 입력이라 함께)로 이관을 재생 → 모두 오류 없이 ESCALATED. 정답 열을 읽는 시험 코드다(근거: AC-033-5, CLAUDE.md 규칙 6 예외, 구현 선택 C-156).
- 예외: 이미 ESCALATED, 같은 부서, 처리 중 아님(WAITING_CUSTOMER), 목록 밖 부서·사유(근거: FR-033 예외 표).
- AC-033-3·6·7은 변경 25, AC-033-8은 변경 21 시험이 확인한다(근거: proposal 범위 밖).

## Risks / Trade-offs

- 이관 사유 11값 중 FR-033 입력에 이름이 나오지 않는 값(P1, SAFETY, OUT_OF_SCOPE_TEST, CUSTOM_SPEC)도 고를 수 있게 둔다. P1·SAFETY는 이관 후보 규칙이 쓰는 값이다(근거: FR-033 입력 "정답지의 값", 화면 정의서 v1 CP-6, schema.sql CHECK, 변경 23 C-146).
- 이관된 문의는 회신이 오기 전까지(변경 25) ESCALATED에 머문다. 그 사이 C/S 상담원이 최종 답변을 보내면 ESCALATED → RESOLVED 전이로 끝날 수 있다(근거: §6-4 전이표, 2순위 발송 API).
