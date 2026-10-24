# Design: 부서 회신과 예외 부서 메일

## Context

DB에는 이 변경에 쓸 행 모양과 전이가 이미 있다: ESCALATION_NOTE RECEIVED(sender DEPT), FINAL_REPLY DRAFT·APPROVED·SENT(sender DEPT), 전이 ESCALATED → IN_PROGRESS의 DEPT_REPLY·DEPT_MAIL_SENT, agent_run.trigger DEPT_REPLY(근거: schema.sql ticket_message_kind_combo, status_transition, agent_run.trigger CHECK). 변경 24가 이관 확정을 만들어 sub_ticket.escalated_to와 ESCALATE 이력이 생겼고, 상단 막대의 상담원·부서는 모든 요청에 X-Agent-Id·X-Agent-Dept로 실린다(근거: 기술 명세서 v1.4 §8-1 머리 문단, D23, `frontend/src/api.ts` call()). 상담원 수정(FR-030 처리 6)은 이미 "저장값으로 Q2부터 다시 처리"하는 첫 노드(reprocess.reuse)를 쓴다(근거: `backend/app/pipeline/reprocess.py`, openspec/specs/ticket-detail). SubTicketState에는 dept_reply 칸이 있고 L8 지시문에는 `<dept_reply>`가 이미 있다(근거: 기술 명세서 v1.4 §2-3 TicketState 주석 "DEPT_REPLY 재실행 때만 채움", `prompts/l8_verify_v1.md`, 에이전트 설계서 v1.1 L8 입력).

## Decisions

### 1. 이관 부서 회신 등록 (`backend/app/status/dept_reply.py`)

| 항목 | 정한 것 | 근거 |
|---|---|---|
| 입력 | body(필수), 상담원 ID(X-Agent-Id 필수), 부서(X-Agent-Dept), expected_version(선택) | FR-033 입력 "이관 부서 회신: 회신 본문, 작성 상담원", §8-1 dept-reply 행, FR-025 예외 2행 |
| 검사 순서 | 본문 빔 "내용을 입력하세요"(400) → 문의 없음(404) → 버전 다름(409) → 부서가 escalated_to와 다름 "이관받은 부서만 회신할 수 있음"(403) → ESCALATED가 아님 "이관된 문의만 회신할 수 있음"(409, 실행 로그 T6 FAILED·VALIDATION) | FR-033 예외 표 4행, §8-1 "X-Agent-Dept가 escalated_to와 같아야 한다", FR-025 예외 1·2행, 변경 24 C-157 모양, 구현 선택 C-166(문구·응답 코드) |
| 저장 | 한 트랜잭션: ESCALATION_NOTE RECEIVED(sender DEPT, sent_by_name = 상담원 ID, language 'ko', mask_count) → 전이 DEPT_REPLY(actor = 상담원 ID) → 다시 처리 run(trigger DEPT_REPLY)을 연다 | FR-033 처리 8, §8-1, §6-4 전이표, §6-5 trigger 5개, 구현 선택 C-163(언어 'ko', 변경 24 C-155와 같음) |
| 임시 저장 | 없다. 등록 한 번으로 끝난다 | FR-033 처리 8 "임시 저장은 없다" |

- 이 모듈은 규칙·상태 코드라 언어 모델 호출 계층을 import하지 않는다(근거: CLAUDE.md 규칙 1).

### 2. 회신 뒤 다시 처리 (`tickets.process_dept_reply`, `reprocess.with_dept_reply`, `graph.py`)

| 항목 | 정한 것 | 근거 |
|---|---|---|
| 시작 노드 | 언어 모델은 Q8부터 부른다. 첫 노드는 상담원 수정과 같이 저장값을 읽고(언어 모델 없음), 규칙 단계 Q2~Q6은 규칙이라 다시 계산해도 같은 값이며, Q8a·Q9a는 다시 돌리지 않고 직전 결과를 옮겨 적는다. 상세 화면과 "왜?"가 그 하위 문의의 마지막 처리 흐름 실행 하나의 단계를 읽기 때문에 새 run에 모든 단계를 남긴다. 문서는 모두 "Q8부터"다: §2-4, §8-1 dept-reply 행, 에이전트 설계서 v1.1 3-1절·9-1 표·9-2절 4번, 화면 정의서 v2 부록 B-1 SCR-03-C 행, schema.sql status_transition 설명 | 위 문서들, FR-036 처리 7, `app/db/detail.py` _sub_detail, 구현 선택 C-160(조장 확인 필요) |
| 답변 경로 | 부서 회신이 있는 하위 문의는 막는 정보가 빠져 있어도 정보 요청(Q7)이 아니라 답변 경로(Q8 → Q9 → Q10 → Q11 → Q13 → Q14)로 간다. 발송 때 "막는 정보가 아직 없습니다" 확인은 그대로 뜬다. FR-021 처리 1("막는 항목이 있으면 정보 요청만")과 다르다 | §2-4 "Q8(문서 검색)부터 Q10 초안 → Q11 → Q13 → Q14"(Q7을 지나지 않음), FR-021 처리 1과 다름, 구현 선택 C-161(조장 확인 필요) |
| 부서 회신 글 | 그 하위 문의의 ESCALATION_NOTE RECEIVED 본문을 시각순으로 빈 줄로 이은 글. state.dept_reply에 넣는다. 언어 모델로 갈 때 다른 칸처럼 가린다 | §2-3 dept_reply 주석, CLAUDE.md 규칙 2, `app/llm/client.py` generate_json의 prepare_llm_input, 구현 선택 C-162 |
| L4 | 부서 회신이 있을 때만 `prompts/l4_draft_v3.md`(v2에 `<dept_reply>` 칸과 "부서 회신의 사실·숫자도 쓸 수 있다"는 규칙을 더함)를 쓴다. 없으면 v2 그대로 | §2-2 Q10 입력 "부서 회신 본문(있을 때)", §3-1 L4 행, 에이전트 설계서 v1.1 4-6절 지시문에 부서 회신 칸이 없음, 구현 선택 C-162 |
| Q11 | 허용 목록에 그 하위 문의의 부서 회신 본문을 더한다(초안 만들 때와 임시 저장·발송 때 모두) | §3-4 2번, 에이전트 설계서 v1.1 6-1절 2번, FR-021 처리 5, FR-031 처리 2 |
| L8 | 검증 입력 dept_reply에 같은 글을 넣는다([다시 검증] 때도) | §2-2 Q14 입력, 에이전트 설계서 v1.1 L8 입력 "부서 회신(있을 때)" |
| 근거 없음 | 근거 절이 없으면 부서 회신이 있어도 초안을 만들지 않는다("근거 없음 — 상담원 작성 필요") | FR-021 처리 2, 구현 선택 C-168 |
| 저장 | 상담원 수정처럼 T2·Q1 행은 쓰지 않고, 밀린 SYSTEM 초안은 superseded_at을 채운다. 실패하면 첫 단계 Q2에 남긴다. 처리 흐름 실행 조건(pipeline_run)에 DEPT_REPLY를 더해 상세가 "처리 중"을 본다 | §2-4 재처리, `app/db/store.py` _save_sub·_save_failure, `app/db/runs.py` pipeline_run |

### 3. 예외 부서 고객 메일 (`dept_reply.py`, `sub_tickets.py`, `messages.py`, `store.send_draft`)

| 항목 | 정한 것 | 근거 |
|---|---|---|
| 초안 만들기 | `POST /sub-tickets/{id}/dept-mail`(body): FINAL_REPLY DRAFT(sender DEPT, sent_by_name = 상담원 ID, language = 고객 언어). 그 하위 문의에 아직 안 보낸 DEPT 초안이 있으면 새로 만들지 않고 그 본문을 바꾼다 | §8-1 dept-mail 행, FR-031 처리 7, 구현 선택 C-165 |
| 부서 검사 | X-Agent-Dept가 FIELD_SVC·SALES_OPS가 아니면 "고객 메일은 FIELD_SVC·SALES_OPS만 보낼 수 있음"(403), escalated_to와 다르면 "이관받은 부서만 회신할 수 있음"(403). 초안 만들 때·임시 저장 때·발송 때 모두 본다 | §8-1 "초안 만들 때와 send 때 모두 확인", FR-033 처리 9, 구현 선택 C-166(임시 저장 때도, 문구) |
| 임시 저장 | `PUT /messages/{id}`: DEPT 초안은 본문을 바꾸고 대역(L7)을 다시 만든다. 자체 대조(Q11)는 하지 않는다. 화면의 첫 [임시 저장]은 초안 만들기 뒤 이 API를 부른다 | FR-031 처리 7·9, §8-1 PUT 행 "저장 뒤 대역(L7)을 다시 만든다", §3-1 L7 행, 화면 정의서 v2 부록 B-1 "검토 표시·Q11·L8 없음", 구현 선택 C-165 |
| 승인·발송 | `POST /messages/{id}/send`: DEPT 초안은 확인 목록(Q11·막는 정보·⑤)을 만들지 않고 바로 FINAL_REPLY SENT(sender DEPT, sent_by_name = 상담원 ID)를 쓰고 초안을 APPROVED로, 전이 DEPT_MAIL_SENT로 IN_PROGRESS. 1차 응답 시각이 비어 있으면 채운다. 원본 초안 ID·수정 여부, 같은 초안 두 번 발송 거부는 C/S 발송과 같다. 전이가 거부되면(이미 IN_PROGRESS) C/S 발송처럼 메시지만 기록하고 실행 로그에 남긴다 | FR-031 처리 3·5·9, 예외 3·4행, FR-033 처리 9, D34, §6-4, 구현 선택 C-167 |
| [다시 검증] | DEPT 초안은 받지 않는다(400) | FR-031 처리 9 "검증 에이전트(FR-049)를 거치지 않는다", 구현 선택 C-165 |
| 해결 | 예외 부서 메일 뒤 상태는 IN_PROGRESS이고, 해결은 C/S 상담원이 마무리 답변을 보낼 때다 | FR-033 처리 9, D34, D20 |

### 4. 상세 응답과 화면 (`detail.py`, `TicketDetailPage.tsx`, `DetailTabs.tsx`)

- 하위 문의마다 dept_replies(회신 본문, 작성 상담원, 회신 시각)와 dept_mails(DEPT 초안·발송 행)를 더한다(근거: FR-030 처리 2 "부서 회신" 영역 항목, FR-033 출력).
- 하위 문의마다 writer를 X-Agent-Dept로 계산해 돌려준다: escalated_to가 고른 부서와 같으면 예외 부서는 DEPT_MAIL, 그 밖의 부서는 DEPT_REPLY, 나머지는 CS. 화면은 이 값으로 작성 영역을 고른다(근거: §8-2 "오른쪽 칸은 고른 부서에 따라 다르다", FR-033 처리 9, AC-033-7, 구현 선택 C-164). 예외 부서 화면에는 메일 작성란만 두고 [회신 등록]은 두지 않는다(근거: §8-2 "예외 부서는 고객에게 보낼 메일 작성란과 [임시 저장]·[승인]이 있다", 구현 선택 C-164).
- "보낼 것" 탭: writer가 CS면 지금 그대로다. DEPT_REPLY면 회신 작성란과 [회신 등록](ESCALATED일 때만 켜짐, 등록 뒤 "회신 등록됨"), DEPT_MAIL이면 고객 메일 작성란과 [임시 저장]·[승인](ESCALATED일 때만). 하위 문의가 모두 CS가 아니면 정보 요청·답변·진행 안내 탭 머리와 [이관] 버튼을 숨긴다(근거: FR-033 처리 8·9, AC-033-7, 조장 결정 2026-10-23 기존 레이아웃 유지, 구현 선택 C-164).
- "시스템이 판단한 것" 탭: escalated인 하위 문의 구역의 이관 후보 아래에 "부서 회신" 영역(이관 부서, 사유, 이관 시각, 회신 본문, 작성 상담원, 회신 시각, 없으면 "부서 회신 대기 중")을 둔다(근거: 항목은 FR-030 처리 2 v1.5·§8-2, 영역은 화면 정의서 v2 부록 B-1 SCR-03-C 행). 예외 부서가 보낸 고객 메일도 이 영역에 보인다. 예외 부서에는 [회신 등록]이 없어 회신 칸이 늘 비기 때문이다(근거: FR-033 출력, 구현 선택 C-164).
- 이력 탭은 메시지 이력을 이미 시각순으로 보이므로 부서 회신·부서 메일도 나온다. "부서 회신 입력은 3순위(이관) 기능입니다" 자리 표시를 뗀다(근거: §8-1 timeline, 화면 정의서 v2 부록 B-1 SCR-03-P5 "없앤다").

### 5. 시험 (`tests/acceptance/test_dept_reply.py`)

- AC-033-3: CSV1-000007(정답 이관 QA_CLAIM, RMA_REQUIRED)을 접수 API로 처리 → QA_CLAIM(RMA_REQUIRED)으로 이관 → QA_CLAIM 접수함에 있음 → QA_CLAIM_AGENT_01·QA_CLAIM으로 [회신 등록] → IN_PROGRESS, ESCALATION_NOTE RECEIVED(sender DEPT, sent_by_name QA_CLAIM_AGENT_01), 상세의 dept_replies에 그 회신, 새 run(trigger DEPT_REPLY)의 L4 입력에 회신 본문과 회신 속 번호, 새 답변 초안의 Q11이 회신 속 번호를 허용(근거: AC-033-3, FR-021 처리 5, §2-4).
- AC-033-6·AC-031-6: FIELD_SVC로 이관한 CSV1-000017에서 FIELD_SVC 상담원이 메일 초안을 만들고 승인 → 대조·검증 호출 없이 FINAL_REPLY SENT(sender DEPT), 상태 IN_PROGRESS, 전이 DEPT_MAIL_SENT(근거: AC-033-6, AC-031-6).
- AC-033-7: RND_FW로 이관한 문의를 RND_FW 부서로 열면 writer가 DEPT_REPLY(메일 작성·[임시 저장]·[승인] 없음), 같은 문의를 C/S 부서로 열면 CS(근거: AC-033-7, 구현 선택 C-164). 화면 모양은 Playwright로 확인한다.
- 예외: 빈 본문 "내용을 입력하세요", 다른 부서, ESCALATED가 아님(실행 로그), 예외 부서가 아닌 부서의 메일(근거: FR-033 예외 표 4행, 구현 선택 C-166).

## Risks / Trade-offs

- 회신 뒤 다시 처리는 Q8a·Q9a를 다시 돌리지 않으므로 그 사이 기준 데이터가 바뀌어도 진단·이관 후보는 직전 값이다(구현 선택 C-160). 이후 고객 회신 재처리·상담원 수정은 부서 회신을 L4에 넣지 않는다(§2-3 "DEPT_REPLY 재실행 때만 채움"). 그때도 Q11 허용 목록에는 부서 회신 숫자가 남는다(근거: 에이전트 설계서 v1.1 6-1절 "그 하위 문의에 기록된 부서 회신").
- 예외 부서 메일은 고객에게 가는 글이지만 상담원이 직접 쓴 글이라 검사가 없다. D34 결정 전 진행 방식이다(근거: D34, FR-031 처리 9).
