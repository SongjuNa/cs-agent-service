# Design: 근거 없을 때 상담원이 직접 쓰는 초안

## Context

시스템이 초안을 만들지 못하는 경우는 근거 없음(FR-021 처리 2), 막는 정보 요청 중(FR-030 처리 3), 처리 실패(FR-001 예외)다(근거: 명세서 v1.5 해당 절, `frontend/src/TicketDetailPage.tsx` noDraftText). DB의 ticket_message는 sender AGENT인 INFO_REQUEST·FINAL_REPLY DRAFT를 이미 허용한다(근거: `docs/database/schema.sql` ticket_message_kind_combo). 지금 코드는 sender SYSTEM과 예외 부서 DEPT 초안만 읽는다(근거: `backend/app/db/store.py` load_draft).

## Goals / Non-Goals

- 목표: 초안이 없는 하위 문의에서 상담원이 정보 요청·답변을 직접 써서 임시 저장하고, 기존 승인 API로 보낸다(근거: FR-030 처리 3, FR-031).
- 목표 아님: 직접 쓴 글의 대역·검증 자동 실행, 진행 안내 직접 작성(근거: proposal 범위 밖).

## Decisions

### 1. API (`POST /sub-tickets/{sub_ticket_id}/drafts`)

| 항목 | 정한 것 | 근거 |
|---|---|---|
| 요청 | message_type(INFO_REQUEST 또는 FINAL_REPLY), body(1~5000자, 비면 "내용을 입력하세요") | schema.sql body CHECK, FR-033 예외 표 4행과 같은 문구(구현 선택) |
| 머리 | X-Agent-Id 필수, sent_by_name에 넣는다 | 기술 명세서 v1.4 §8-1 머리말 |
| 만들 수 있는 때 | 그 하위 문의에 같은 종류의 안 보낸 초안(시스템 또는 직접 쓴 것, superseded_at 없음)이 없을 때. 있으면 409 "이미 초안이 있습니다". 직접 쓴 초안을 고칠 때는 `PUT /messages/{id}`를 쓴다 | FR-030 처리 3 "초안이 없는 종류는", 구현 선택 |
| 상태 | 보냈을 때 전이가 있는 상태에서만 만든다: INFO_REQUEST는 NEW·IN_PROGRESS, FINAL_REPLY는 IN_PROGRESS·ESCALATED. 그 밖이면 409 | schema.sql status_transition(INFO_REQUEST_SENT, FINAL_REPLY_SENT), FR-031 예외 3행, 구현 선택 |
| 동시 수정 | expected_version(하위 문의 version)을 받아 다르면 409 | FR-025 예외 2행, FR-030 예외 4행 |
| 응답 | sub_ticket_id, message_id (201) | 구현 선택 |
| 언어 | 티켓 language | FR-021 기능 설명 "고객 언어로", openspec/config.yaml 설계 원칙 1 |
| mask_count | 만들 때 mask_text로 센다. 기존 행을 고치지 않으므로 schema.sql guard_ticket_message(DRAFT는 body·message_status·superseded_at만 바꿈)와 부딪히지 않는다 | FR-038, schema.sql guard_ticket_message |

### 2. 읽기와 발송

| 항목 | 정한 것 | 근거 |
|---|---|---|
| load_draft | sender AGENT인 INFO_REQUEST·FINAL_REPLY DRAFT도 읽는다 | 구현 선택 |
| 상세 drafts | 하위 문의의 drafts에 AGENT 초안을 넣고, 화면이 구분하도록 sender를 내보낸다 | FR-030 처리 3, 구현 선택 |
| 발송 | sender AGENT 초안도 SYSTEM 초안과 같은 `_send_issues`를 거친다: 인용·숫자 대조, 정보 요청의 빠진 항목, 막는 항목이 남은 답변. 걸리면 409 + 확인 필요, override_check로 발송 | FR-031 처리 2·예외 5행·AC-031-3, 에이전트 설계서 v1.1 6-1절, 화면 정의서 v2 R-06 |
| 상태 전이·1차 응답 | INFO_REQUEST → WAITING_CUSTOMER, FINAL_REPLY → RESOLVED, 첫 발송이면 1차 응답 시각 기록 (지금 send_draft 그대로) | FR-031 처리 4·5 |
| 수정 여부(edited_yn) | 직접 쓴 초안은 원본이 상담원 글이므로 발송 행 edited_yn은 "임시 저장 본문과 발송 본문이 다르면 Y" (지금 규칙 그대로) | FR-031 처리 3, 구현 선택 |

### 3. 대역·검증

| 항목 | 정한 것 | 근거 |
|---|---|---|
| 대역(L7) | 만들 때와 임시 저장 때 다른 초안과 같이 만든다. FR-039 기능 설명("시스템이 만든 초안")과 달라 조장 확인 | 화면 정의서 v2 R-05, 기술 명세서 v1.4 §8-1 PUT 행, FR-039 처리 4 |
| 검증(L8) | 자동으로 부르지 않는다. ⑤는 검증 행이 없을 때의 지금 표시("⑤ 검증 전")를 그대로 쓴다. 새 상태값은 만들지 않는다 | FR-049 처리 8, 기술 명세서 v1.4 §5-7, `backend/app/db/detail.py` |
| ①~④ | ①(인용·숫자 대조)은 임시 저장 때 코드로 다시 계산한다. ②③④는 지금과 같이 하위 문의 값으로 | FR-024 처리 6, `messages.py` put_message의 check_body |

### 4. 화면

| 항목 | 정한 것 | 근거 |
|---|---|---|
| 빈 편집기 | 초안이 없는 종류는 이유 문구 아래 빈 편집기와 [임시 저장]을 바로 보인다. "처리 중"일 때는 편집기를 잠근다 | 화면 정의서 v2 R-06, 구현 선택(잠금) |
| 저장 | 첫 저장 때 `POST …/drafts`, 그 뒤는 `PUT /messages/{id}` | 구현 선택 |
| 표시 | 직접 쓴 초안에는 "상담원 작성" 칩 | 구현 선택 |

### 5. 시험 (`backend/tests/acceptance/test_manual_draft.py`)

명세서에 이 동작의 AC가 없다(근거: FR-030 AC-030-1~5). 아래 시나리오는 "제안 AC"이며, 명세서에 AC-030-6·7로 넣을지 조장이 정한다(근거: CLAUDE.md 규칙 7, 문서가 정하지 않은 것은 사람에게 묻는다).

| 시험 | 확인하는 것 | 근거 |
|---|---|---|
| 제안 AC-030-6 | CSV1-000004(막는 항목 없음)를 근거 없음으로 만든 상태(시험에서 검색 결과를 비움)에서 숫자 없는 FINAL_REPLY를 직접 써서 승인하면 FINAL_REPLY SENT(sender AGENT) 1행, 상태 RESOLVED | FR-030 처리 3, FR-031 처리 4, AC-030-4(막는 항목 없음) |
| 제안 AC-030-7 | 같은 상태에서 조회값(520 USD, 4주)에 없는 숫자 "999 USD"를 쓰면 첫 승인은 409 확인 필요, override_check로 발송되고 기록된다 | FR-031 처리 2·AC-031-3, AC-030-4 조회값 |
| 막는 항목이 남은 답변 | 막는 항목이 있는 CSV1-000017에서 직접 쓴 FINAL_REPLY 승인 → 409 확인 필요 | FR-031 예외 5행 |
| 상태 밖 거부 | WAITING_CUSTOMER 하위 문의에 INFO_REQUEST 만들기 → 409 | 구현 선택(결정 1) |
| 시스템 초안이 있으면 거부 | 같은 종류의 시스템 초안이 있는 하위 문의에서 만들기 → 409 | 구현 선택(결정 1) |
| 빈 본문 거부 | body 공백 → 400 "내용을 입력하세요" | 구현 선택(결정 1) |
| 검증 안 함 | 만든 뒤 L8 단계가 없고 ⑤는 "검증 전" | 구현 선택(결정 3) |

## Risks / Trade-offs

- 근거 후보가 없는 문의라 직접 쓴 답변의 인용은 늘 근거 밖이고, 숫자도 조회값에 없으면 걸린다. 확인 창이 자주 뜨지만, "AI는 근거 없이 쓰지 않고, 사람은 확인한 뒤 보낼 수 있다"는 원칙과 맞다(근거: FR-021 처리 5).
- 상담원이 읽지 못하는 고객 언어로 직접 쓰는 경우의 도움(번역 입력 등)은 FR에 없다(근거: FR-030·FR-039에 해당 처리 없음). 필요하면 FR 초안으로 따로 묻는다(구현 선택).
- 예외 부서 메일 임시 저장(`backend/app/status/dept_reply.py` save_mail_draft)은 기존 DRAFT 행의 mask_count도 UPDATE한다. schema.sql guard_ticket_message는 DRAFT에서 body·message_status·superseded_at만 바꾸게 하므로, 가린 개수가 달라지는 본문이면 거부될 수 있다(근거: 두 파일 대조). 이 변경은 그 방식을 쓰지 않고, 기존 코드의 차이는 조장에게 따로 알린다(구현 선택).
