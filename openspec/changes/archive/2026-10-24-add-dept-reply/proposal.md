# Proposal: 부서 회신과 예외 부서 메일 (add-dept-reply)

## Why

이관받은 부서 상담원은 우리 시스템에서 C/S 팀에 직접 회신하고, 예외 부서(FIELD_SVC, SALES_OPS)는 고객에게 직접 메일을 보낸다(근거: 명세서 v1.5 FR-033 v1.5 머리말 "가-3, 2026-10-22 조장 결정"). 변경 24가 이관 확정(처리 1~7)까지 만들었으므로, 이 변경은 FR-033 처리 8·9와 예외 부서 메일(FR-031 처리 9)을 만들어 3순위의 마지막 변경이 된다(근거: openspec/config.yaml "예외 부서 메일(FR-031 처리 9)은 FR-033과 함께 만든다", 변경 24 proposal 범위 밖, 조장 승인 2026-10-24 "네 승인합니다", 기록: 개발 결정 기록(/mnt/project-files/bootcamp/openspec/개발_결정_기록.md) 3순위 진행 행). 처리 10(시연용 상담원 ID)은 변경 21이 이미 만들었다(근거: `backend/app/roster/agent_roster.json`, `test_agent_roster.py` AC-033-8).

## What Changes

- **이관 부서 [회신 등록] (FR-033 처리 8)**: `POST /sub-tickets/{sub_ticket_id}/dept-reply`(body). X-Agent-Dept가 그 하위 문의의 escalated_to와 같아야 한다. ESCALATION_NOTE RECEIVED(sender DEPT, sent_by_name = X-Agent-Id)를 쓰고 전이 DEPT_REPLY로 ESCALATED → IN_PROGRESS로 바꾼다. 메일이 아니고 임시 저장도 없다(근거: FR-033 처리 8, 기술 명세서 v1.4 §8-1 dept-reply 행, §6-4 전이표, schema.sql ticket_message_kind_combo).
  - 등록 뒤 그 하위 문의를 다시 처리해 회신을 반영한 답변 초안을 새로 만든다(새 run, trigger = DEPT_REPLY). 회신 본문은 L4 입력에 넣고 회신 속 숫자는 Q11 허용 목록에 넣으며, L8 검증에도 넣는다(근거: §2-4 "이관 부서 회신" 행, §2-2 Q10·Q14 입력 칸, §3-4 2번, 에이전트 설계서 v1.1 6-1절, FR-021 처리 5 가-6).
  - 다시 처리는 Q8부터 언어 모델을 부른다. 그 앞 단계는 부르지 않고, 규칙 단계(Q2~Q6)만 저장값으로 다시 계산해 새 run에 남기며 Q8a·Q9a는 직전 결과를 옮겨 적는다(근거: §2-4·§8-1 dept-reply 행·에이전트 설계서 v1.1 9-1 표·화면 정의서 v2 부록 B-1·schema.sql status_transition 설명은 모두 "Q8부터", 구현 선택 C-160. 문서와 다른 점이라 조장 확인을 받는다).
- **예외 부서 고객 메일 (FR-033 처리 9, FR-031 처리 9)**: `POST /sub-tickets/{sub_ticket_id}/dept-mail`(body)로 FINAL_REPLY DRAFT(sender DEPT)를 만들고, [임시 저장]은 `PUT /messages/{id}`, [승인]은 `POST /messages/{id}/send`를 C/S와 같이 쓴다. sender DEPT인 초안의 발송은 자체 대조(Q11)·검증 에이전트(L8) 없이 FINAL_REPLY SENT(sender DEPT)를 쓰고 전이 DEPT_MAIL_SENT로 IN_PROGRESS가 된다. X-Agent-Dept는 FIELD_SVC 또는 SALES_OPS이고 escalated_to와 같아야 하며, 초안을 만들 때와 보낼 때 모두 본다(근거: FR-033 처리 9, FR-031 처리 9, D34, §8-1 dept-mail 행, §6-4 "v1.4(가-3, D34)" 문단).
- **본문 비어 있음**: 회신·메일 모두 "내용을 입력하세요"로 거부한다(근거: FR-033 예외 표 4행).
- **티켓 상세 화면 (기존 레이아웃 유지)**: "보낼 것" 탭의 작성 영역만 고른 부서에 따라 바뀐다. 담당 부서(C/S)는 지금과 같고, 이관받은 부서는 회신 작성란과 [회신 등록]만, 예외 부서는 고객 메일 작성란과 [임시 저장]·[승인]이 있다(근거: 기술 명세서 v1.4 §8-2 "v1.4(가-3): 티켓 상세의 오른쪽 칸은 고른 부서에 따라 다르다", FR-033 처리 9, AC-033-7, 조장 결정 2026-10-23 "메일·회신 쓰는 영역만 바꿈", openspec/config.yaml).
  - C/S 상담원이 보는 "시스템이 판단한 것" 탭의 이관된 하위 문의 구역에 "부서 회신" 영역(이관 부서, 사유, 이관 시각, 회신 본문, 작성 상담원, 회신 시각, 없으면 "부서 회신 대기 중")을 둔다(근거: 항목은 FR-030 처리 2 v1.5·기술 명세서 v1.4 §8-2, 영역이 있다는 것은 화면 정의서 v2 부록 B-1 SCR-03-C 행). 예외 부서가 고객에게 보낸 메일도 이 영역에 함께 보인다(근거: FR-033 출력 "예외 부서가 보낸 FINAL_REPLY 행", 구현 선택 C-164).
  - 이력 탭의 "부서 회신 입력은 3순위(이관) 기능입니다" 자리 표시를 뗀다. C/S 대리 입력(P5)은 없앴다(근거: 화면 정의서 v2 부록 B-1 SCR-03-P5 행 "없앤다").

## Capabilities

### New Capabilities
- `dept-reply`: 이관 부서 회신 등록과 그 뒤 다시 처리, 예외 부서 고객 메일, 부서별 작성 영역과 "부서 회신" 영역.

## 범위 밖

- **고객 이관 안내 초안**: 여유 시 FR-048 ②(근거: FR-033 처리 5).
- **예외 부서 메일의 숫자 검사·검증 에이전트**: 지금은 거치지 않는다(근거: FR-031 처리 9 "지금은", D34).
- **시연 데이터 W5 ⓔ(이관 부서 회신 1건) 스크립트**: 시연 준비 작업 W5에서 한다(근거: 기술 명세서 v1.4 §9 W5 행, 구현 선택).

## Impact

- 새 파일: `backend/app/status/dept_reply.py`(회신 등록·예외 부서 메일 검사), `prompts/l4_draft_v3.md`(부서 회신 칸이 있는 L4 지시문), 시험 `backend/tests/acceptance/test_dept_reply.py`(근거: design 결정 1~5).
- 고치는 파일: `app/api/sub_tickets.py`·`messages.py`·`tickets.py`(API·다시 처리), `app/db/store.py`(발송·허용 목록·저장), `app/db/runs.py`(처리 흐름 실행에 DEPT_REPLY), `app/pipeline/reprocess.py`·`graph.py`(첫 노드, 답변 경로), `app/llm/drafts.py`(L4 부서 회신), `app/db/detail.py`(상세 응답), 화면 `TicketDetailPage.tsx`·`DetailTabs.tsx`·`api.ts`·`App.tsx`(근거: design 결정 1~4).
- DB 구조는 고치지 않는다. 쓰는 행 모양, 전이 DEPT_REPLY·DEPT_MAIL_SENT, trigger DEPT_REPLY는 테이블 정의서 v1.3에 이미 있다(근거: CLAUDE.md 규칙 4, schema.sql status_transition·ticket_message_kind_combo·agent_run.trigger CHECK).
