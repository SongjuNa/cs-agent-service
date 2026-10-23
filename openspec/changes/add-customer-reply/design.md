# Design: 고객 회신 입력과 메시지 이력

## Context

동기는 proposal.md의 Why를 본다. 따를 기준은 다음과 같다(근거: 아래 문서들).
- 명세서 v1.5 FR-032(입력, 처리 1~6, 예외 5행, AC-032-1~5), FR-035(처리 1·2·4·5·7, 예외, AC-035-3·4), FR-011 예외 3행.
- 기술 명세서 v1.4 §2-4(고객 회신 재처리, 재처리 때 superseded_at), §2-5 분기⑥, §6-3(지우지 않는 기록), §6-4 전이표, §6-5 trigger, §8-1 `POST /tickets/{id}/replies`.
- 화면 정의서 v1 SCR-03-P6(입력, 결과, 오류 문구).
- schema.sql: svc.ticket_message(종류·상태·보낸 쪽 조합 CHECK, message_no 자동, 수정 거부 트리거), svc.inquiry_field(source CUSTOMER_REPLY, source_message_id), svc.status_transition CUSTOMER_REPLY 2행.

## Goals / Non-Goals

**Goals**
- 회신을 저장하고 상태를 바꾸고, 대상 문의를 Q1부터 다시 돌려 새 초안을 만든다(근거: FR-032 처리 1~4).
- 메시지 이력을 시각순으로 돌려준다(근거: FR-035 처리 7).

**Non-Goals**
- 진행 안내, 화면, 운영진 데이터 메시지 적재, 복합 문의(proposal "범위 밖") (근거: proposal 범위 밖).

## Decisions

### 1. 회신 저장 (`app/db/replies.py`)

`record_reply(conn, ticket_id, body, language, received_at, target_ids, agent_id)` (구현 선택. 이름은 기술 명세서에 없음).

| 단계 | 정한 것 | 근거 |
|---|---|---|
| 본문 | 공백이면 "회신 내용을 입력하세요"(400). 2,000자를 넘으면 "길이 초과"(400) | FR-032 입력·예외 1행, FR-035 예외 3행 문구, 화면 정의서 v1 P6 |
| 언어 | 비우면 ticket.language. 15개 언어 코드 밖이면 400 | FR-032 입력 "기본값 = 고객 언어", schema.sql ticket.language CHECK. 거부는 구현 선택 |
| 대상 | 비우면 WAITING_CUSTOMER인 하위 문의 전부, 하나도 없으면 그 티켓의 하위 문의 전부(메시지를 어느 문의에 붙일지만 정하고, 다시 처리는 아래 "다시 처리" 행). 그 티켓의 하위 문의가 아니면 400 | FR-032 입력 "기본값 = 대기 중인 모든 문의". 대기 중이 없을 때의 기본값은 구현 선택 |
| 시각 | 비우면 지금. 지금보다 뒤면 "회신 시각은 지금보다 뒤일 수 없습니다"(400). 대상 문의의 마지막 INFO_REQUEST·FINAL_REPLY SENT 시각보다 앞이면 "회신 시각은 요청 발송 이후여야 합니다"(400) | FR-032 입력 "미래 거부", 예외 2행, 화면 정의서 v1 P6. 미래 문구와 FINAL_REPLY도 함께 보는 것은 구현 선택(RESOLVED → IN_PROGRESS 전이가 발송 뒤여야 하므로). 전이할 문의의 마지막 상태 이력보다 앞이면 "회신 시각은 마지막 상태 변경 이후여야 합니다"(400, 구현 선택: 과거 시각 입력이 상태 이력 순서를 뒤집지 않게) |
| 저장 | CUSTOMER_REPLY, RECEIVED, sender CUSTOMER, sent_by_name CUSTOMER, sent_at_utc = 회신 시각, 원문 body, mask_count. sub_ticket_id는 대상이 하나면 그 문의, 둘 이상이면 NULL | FR-032 처리 1, FR-035 처리 2·5, schema.sql 조합 CHECK. 대상 둘 이상일 때 NULL은 구현 선택(복합 문의는 16번) |
| 전이 | 대상마다 WAITING_CUSTOMER·RESOLVED면 `transition(→ IN_PROGRESS, CUSTOMER_REPLY, at = 회신 시각, actor = 상담원 ID)`. 그 밖은 그대로 | FR-032 처리 2, §6-4 전이표 |
| 종료 문의 | CLOSED인 대상은 다시 처리하지 않고 "종료 후 회신으로 기록됨"을 돌려준다 | FR-032 예외 3행 |
| 다시 처리 | 이번 회신으로 IN_PROGRESS가 된 문의만. NEW·IN_PROGRESS·ESCALATED는 저장만 한다(처리 중인 접수와 겹치지 않는다) | FR-032 처리 2 "저장만", FR-025 예외 3행 "메시지 이력에만". 처리 3 "대상 문의마다"와 달라 C-72 |
| 안내 | 가린 곳이 있으면 notes에 "개인정보 n곳(LLM·로그에는 가림)" | FR-035 예외 4행 |
| 한 트랜잭션 | 메시지와 전이를 한 트랜잭션으로 쓴다. 다시 처리는 그 뒤 백그라운드 | §2-4 "실행 시작"과 같은 방식(구현 선택) |

- 해결 뒤 자동 종료(D20)와 무응답 종료(D22)는 회신으로 상태가 IN_PROGRESS가 되므로 10번 `close_due`가 더는 고르지 않는다(근거: §6-4 주기 점검 3·4, `app/status/closing.py`의 상태 조건). 대상이 둘 이상이라 회신 행의 sub_ticket_id가 NULL이면 close_due·리마인드의 "그 뒤 회신" 조건이 그 회신을 보지 못하는 문제는 복합 문의 16번에서 다룬다(구현 선택).

### 2. 다시 처리 (`app/pipeline/reprocess.py`, `graph.py`)

- `run_ticket(..., understand_fn=None)`: 그래프 첫 노드를 바꿔 끼울 수 있게 한다. 기본은 지금처럼 접수 이해(T1·T2·Q1)(구현 선택).
- `reextract(conn, transport, ticket_id, target_ids)`: T2를 다시 부르지 않는다. 유형·근거 문장·긴급도·제품은 sub_ticket 열에서(상담원이 고친 값이 있으면 그 값), 열이 없는 query_en·분류 확신도·긴급도 근거는 마지막 처리 실행의 T2 단계 결과에서 읽은 뒤 Q1(L2)만 다시 부른다. 회신 재처리 실행도 T2 단계 행을 이어 받아 남기므로 두 번째 회신부터도 같은 곳에서 읽는다(근거: §2-4 "대상 하위 문의의 Q1(원문 + 모든 회신)부터", 에이전트 설계서 "Q1부터". 읽는 곳은 구현 선택).
  - L2 입력 본문 = 접수 원문과 모든 CUSTOMER_REPLY 본문을 시각순으로 빈 줄로 이어 붙여 가린 글. `<customer_message>` 안에만 들어간다(근거: FR-032 처리 3, CLAUDE.md 규칙 2·5). 이어 붙이는 방식은 구현 선택.
  - 제공 항목 = 이전 inquiry_field 값 ∪ 새로 뽑은 값. 이전 값이 있는 항목은 이전 값을 둔다(근거: FR-032 처리 3 "이전에 제공된 값은 유지").
- 그 뒤 Q2~Q6 규칙, 분기③(막는 항목) → 정보 요청 또는 근거·답변 → 대역 → 검증은 1순위 그래프 그대로(근거: FR-032 처리 4, §2-5 분기⑥ "③이 그대로 판단").
- 실행 기록: 새 agent_run(trigger CUSTOMER_REPLY, sub_ticket_id = 대상이 하나면 그 문의)(근거: §6-5, schema.sql agent_run).
- 실패: 회신과 전이는 남기고 run FAILED, sub_ticket.pipeline_error에 "자동 처리 실패. 다시 처리"(근거: FR-032 예외 4행).

### 3. 회신 결과 저장 (`app/db/store.py`)

- `save_outcome(conn, run_id, ticket_id, outcome, reply_id=None)`: reply_id가 있으면 회신 결과로 저장한다(구현 선택).
  - inquiry_field에는 새로 생긴 항목만 source CUSTOMER_REPLY, source_message_id = 회신 행으로 넣는다(근거: schema.sql inquiry_field.source, FR-032 처리 3).
  - 새 항목이 없으면 Q1 단계 결과에 "제공 항목 변화 없음"을 남긴다(근거: FR-032 예외 5행, 화면 정의서 v1 P6).
  - 조정 표시(priority_adjusted_by_agent)가 켜진 문의는 priority_rule_id만 새 규칙값으로 쓰고 priority·sla_id·목표 두 열은 그대로 둔다(근거: FR-011 예외 3행, C-69).
  - 새 초안을 넣기 전, 그 문의의 아직 DRAFT인 SYSTEM 초안(정보 요청·답변)에 superseded_at = 지금을 쓴다(근거: §2-4 "재처리", schema.sql superseded_at).
- 상세 API와 초안 다루기가 읽는 "마지막 처리 실행"은 trigger INTAKE·CUSTOMER_REPLY 중 최신으로 바꾼다(근거: §2-4 재처리 = 새 run. 구현 선택). 지금 RETRY 실행은 대역·검증만 다시 하므로 넣지 않는다. `/tickets/{id}/reprocess`(전체 다시 처리)를 만들 때 넣는다.

### 4. 상세 API (`app/db/detail.py`)

- `messages(conn, ticket_id, seq=None)`: 티켓의 SENT·RECEIVED 행을 sent_at_utc, message_no 순으로, seq를 주면 그 문의 행만(message_id, seq, sender, message_type, message_status, sent_at_utc, language, body, sent_by_name, mask_count). DRAFT는 지금처럼 drafts에 둔다(근거: FR-035 처리 4·7, 출력 "DRAFT 행은 오른쪽 칸, SENT·RECEIVED 행은 아래 띠").
- 정보 요청 초안의 `re_request`: 바로 앞서 발송한 정보 요청이 있고, 이 초안의 요청 항목(그 초안을 만든 실행의 Q7 결과)이 모두 앞 요청의 항목(앞 초안을 만든 실행의 Q7 결과)에 있으면 참(근거: FR-032 처리 4 "이전 요청과 같은 항목이면 재요청"). 요청 항목을 담는 열이 없어 실행 기록에서 읽고, "같은 항목"을 "모두 앞 요청에 있던 항목"으로 읽은 것은 구현 선택(C-73).
- `customer_followups`: 회신 행 중 (그 회신 직전 대상이 WAITING_CUSTOMER가 아니었거나) 다시 처리가 돌았는데 그 회신에서 새 inquiry_field가 하나도 없었던 행의 수. 다시 처리가 실패한 회신은 "새 항목 없음"으로 세지 않는다. svc.sub_ticket에 열이 없어 저장하지 않고 계산한다(근거: FR-032 처리 6, 테이블 정의서 v1.3 svc.sub_ticket에 customer_followups 없음, C-70).

### 5. API (`app/api/tickets.py`)

- `POST /tickets/{ticket_id}/replies` 입력 `{body, language?, received_at?, target_sub_ticket_ids?}`, 헤더 X-Agent-Id(근거: 기술 명세서 §8-1). 없으면 400 "상담원 ID를 입력하세요"(구현 선택, 발송 API와 같음).
- 응답 `{message_id, transitions, reprocess, notes, processing}`. 다시 처리는 접수와 같이 백그라운드 작업(근거: §2-4 "실행 시작"과 같은 방식, 구현 선택).
- 없는 티켓은 404 "문의를 찾을 수 없음"(구현 선택, 상세 API와 같음).

### 6. 시험 (`tests/acceptance/test_customer_reply.py`)

- AC-032-1: CSV1-000017을 접수(대역 언어 모델) → 정보 요청(serial_no) 발송 → WAITING_CUSTOMER → 회신 "Serial number is LVB-2024-00117." → IN_PROGRESS, 대기 구간 닫힘, provided_info에 serial_no, 막는 항목 없음, TG-ACB-AS-2000을 인용한 답변 초안(근거: AC-032-1).
- AC-032-2: 같은 흐름에서 "We will check and let you know." → IN_PROGRESS, 막는 항목 serial_no 남음, re_request가 참인 정보 요청 초안(근거: AC-032-2).
- AC-032-3: CSV1-003578을 svc에 만들고 product_model 정보 요청을 정답지 1차 응답 시각(2026-09-26 19:07:45)에 발송, 스냅샷 시각에 회신 → 대기 구간이 회신 시각에 닫히고, 회신 뒤 시각에 물어도 wait_h가 100.85h(정답지 100.9)로 확정(근거: AC-032-3, FR-035 처리 6 "정보 요청 시각 = first_response_at_utc").
- AC-032-4(앞부분): 회신 뒤 상세 messages에 INQUIRY → INFO_REQUEST SENT → CUSTOMER_REPLY가 시각순(근거: AC-032-4. 회신 수신 확인 안내는 FR-048, C-71).
- AC-032-5: 회신 시각이 정보 요청 발송보다 앞이면 400(근거: AC-032-5).
- AC-025-2: 회신으로 IN_PROGRESS, 대기 구간 1개의 나온 시각 = 회신 시각(근거: AC-025-2, 10번 변경에서 넘김).
- AC-035-3: 접수 → 정보 요청 발송 → 회신 → 답변 발송까지 돌린 뒤 행 순서와 1차 응답 시각 = INFO_REQUEST SENT 시각(근거: AC-035-3).
- AC-035-4: SENT 행 본문 수정이 거부된다(근거: AC-035-4).
- 종료 문의 회신(메시지만, 다시 처리 없음), RESOLVED 회신으로 IN_PROGRESS·자동 종료 멈춤, IN_PROGRESS 회신은 저장만, 빈 본문·미래 시각 거부, 조정값 보존(C-69), 이전 초안 superseded, 다시 처리 실패 때 회신·전이 유지, 순번 필터(근거: FR-032 예외 3·4행, 처리 2, FR-025 예외 3행, FR-011 예외 3행, FR-035 처리 7, §2-4).

## Risks / Trade-offs

- C-70: 재문의 횟수는 저장 열이 없어 계산한다. 정답지 customer_followups와 맞는지 확인할 수 없다(근거: FR-032 9 "참고 지표로만").
- 회신 본문을 이어 붙여 L2에 다시 보내므로, 회신이 쌓일수록 입력이 길어진다. 접수 본문 2,000자 + 회신 2,000자씩이다(근거: FR-032 입력 2,000자. 상한을 두지 않는 것은 구현 선택).
