# Design: 회신 요청 리마인드

## Context

동기는 proposal.md의 Why를 본다. 따를 기준은 다음과 같다(근거: 아래 문서들).
- 명세서 v1.5 FR-023(처리 1~5, 예외 3행, AC-023-5~8), FR-035 처리 2(REMINDER), AC-035-6, D29·D32.
- 기술 명세서 v1.4 §6-4 주기 점검 1~4, §3-1("회신 리마인드(FR-023)는 LLM을 쓰지 않는다").
- 에이전트 설계서 v1.1 부록 A-1(영어 원문), T40.
- schema.sql: ticket_message 조합 CHECK(SENT + SYSTEM은 notice_transition REMINDER만), notice_kind CHECK, ticket_message_one_reminder 부분 유일 색인.

## Goals / Non-Goals

**Goals**
- 126시간 조건의 문의에 고정 문안 리마인드를 한 번 자동 발송하고 대역을 붙인다(근거: FR-023 처리 1~4, §6-4 주기 점검 2).

**Non-Goals**
- 14개 언어 문안, 화면 표시(proposal "범위 밖") (근거: proposal 범위 밖).

## Decisions

### 1. 리마인드 함수 (`app/status/reminder.py`)

`send_reminders(conn, as_of) -> list[dict]` (구현 선택. 이름은 기술 명세서에 없음).

| 단계 | 정한 것 | 근거 |
|---|---|---|
| 대상 | status = WAITING_CUSTOMER, 마지막 INFO_REQUEST SENT 시각 + 126h ≤ as_of, 그 뒤 그 문의의 CUSTOMER_REPLY 없음, REMINDER 행 없음 | FR-023 처리 1, §6-4 주기 점검 2 |
| 126시간 | 168시간 × 0.75. 상수 하나로 둔다 | FR-023 기능 설명 "126시간(무응답 종료 168시간의 75%)" |
| 발송 시각 | sent_at_utc = 마지막 INFO_REQUEST SENT + 126h(점검 시각이 아님) | 구현 선택(C-76). §6-4 주기 점검 2는 발송 시각을 정하지 않았다. 무응답 종료가 "발송 시각 + 168h"로 쓰는 것(§6-4 주기 점검 3)과 같은 방식이라 시계를 돌려도 같은 결과 |
| 언어 | ticket.language의 템플릿 파일이 있으면 그 언어, 없으면 en + "영어로 발송" | FR-023 입력 "고객 언어별 템플릿", 예외 1행 |
| 문안 | 템플릿의 {ticket_id}, {missing_labels}(아래 항목의 ref.info_field 라벨, 한 줄에 "- {label}")를 채운다. {support_signature}는 팀이 정하지 않아 빈 줄로 둔다 | 에이전트 설계서 부록 A-1, FR-023 처리 2. 서명 비움은 구현 선택(C-74) |
| 항목 | 마지막으로 발송한 정보 요청 초안을 만든 실행의 Q7 요청 항목(실행 기록). 없으면 sub_ticket.missing_info | FR-023 입력 "정보 요청에 쓴 빠진 항목 이름". 부록 A-1 "막는 항목"과 다름(C-77). 실행 기록에서 읽는 것은 C-73과 같은 구현 선택 |
| 저장 | PROGRESS_NOTICE, SENT, sender SYSTEM, sent_by_name SYSTEM, notice_transition REMINDER, sub_ticket_id, mask_count. 상태·first_response_at_utc는 그대로 | FR-023 처리 3·4, §6-4 주기 점검 2, schema.sql CHECK. 초안 행 없음(C-75) |
| 한 번만 | INSERT … ON CONFLICT DO NOTHING(부분 유일 색인)으로 두 번 보내지 않는다 | FR-023 처리 4, 예외 3행 "발송 여부를 먼저 확인" |
| 돌려주는 값 | message_id, sub_ticket_id, sent_at_utc, language, notes("영어로 발송") | 구현 선택. "영어로 발송"은 담을 열이 없어 저장하지 않는다. 화면은 message.language와 ticket.language가 다른 것으로 알 수 있다(C-78) |

- 이 모듈은 언어 모델 호출 계층을 import하지 않는다(근거: FR-023 수행 주체 "LLM을 쓰지 않음").

### 2. 템플릿 (`app/templates/reminder/en.txt`)

- 에이전트 설계서 부록 A-1의 영어 원문을 그대로 둔다. 다른 언어 파일은 T40 절차 뒤에 같은 폴더에 `{language}.txt`로 더한다(근거: 부록 A-1, T40 "`templates/`에 파일로 고정". 폴더 위치는 구현 선택).

### 3. 주기 점검 (`app/scheduler.py`)

- 순서: alerts → cleared → reminders → glossed → closed(근거: §6-4 "한 주기에 네 가지를 차례로", 1 경고(조건이 풀린 경고의 cleared_at 포함) → 2 리마인드 → 3·4 종료).
- `periodic_check(conn, as_of, gloss=None)`: 리마인드 단계 뒤, gloss 함수가 있으면 새 리마인드마다 한국어 대역을 붙인다. 대역 함수 `gloss_reminders(transport_factory)`는 `app/db/store.py`에 두고 `write_gloss`(L7)로 만들어 message_gloss에 넣는다. 실패하면 대역 없이 둔다(근거: §6-4 주기 점검 2 "대역(L7)은 만든다", FR-039 예외 1행 "대역 없음". 함수를 넘기는 방식은 구현 선택: 11번 시험이 주기 점검 모듈의 언어 모델 import 금지를 확인한다).
- 서버(main.py)는 기본 언어 모델 연결로 만든 대역 함수를 넘긴다. 키가 없으면 경고 로그를 남기고 대역만 빠진다(근거: 같은 곳, 구현 선택).

### 4. 시험 (`tests/acceptance/test_reminder.py`)

- AC-023-5: CSV1-000017을 svc에 만들고(막는 항목 serial_no, 언어 en) 정보 요청 SENT, 126시간 뒤 점검 → 영어 리마인드 SENT(sender SYSTEM), 상태 WAITING_CUSTOMER, 1차 응답 시각 그대로(근거: AC-023-5).
- AC-023-6: 같은 문의를 168시간에 점검 → CLOSED_NO_RESPONSE(근거: AC-023-6).
- AC-023-7: 120시간에 고객 회신 입력(13번 record_reply) → 126시간 점검에 리마인드 없음(근거: AC-023-7).
- AC-023-8: 리마인드 본문에 SLA 목표 시간(sla_*_target_h 값 + "hour"), 날짜·시각 꼴이 없다(근거: AC-023-8).
- AC-035-6(앞부분): 리마인드 SENT 행의 보낸 쪽은 SYSTEM, 그 밖의 SENT 행은 상담원(AGENT, 예외 부서 메일은 DEPT)(근거: AC-035-6, schema.sql 조합 CHECK(D34). 초안 행은 C-75).
- 두 번 점검해도 한 번, 템플릿 없는 언어(fr)는 영어 + "영어로 발송", 대역(대역 Transport), 정보 요청 실행의 항목 사용, 언어 모델 import 금지(근거: FR-023 처리 4, 입력, 예외 1·3행, §6-4, FR-023 수행 주체 "LLM을 쓰지 않음").

## Risks / Trade-offs

- C-74: 영어 외 고객도 영어 리마인드를 받는다. 데이터에서 정보 요청을 보낸 887건 중 366건(약 41%)이 영어가 아니므로 T40 번역 전까지 그만큼 "영어로 발송"이다(근거: FR-023 예외 1행, tickets.csv language·info_request_sent).
- 대역은 5분 점검 안에서 언어 모델을 부르므로 키가 없는 환경에서는 리마인드가 생길 때마다 경고 로그가 남는다(근거: §6-4 주기 점검 2, 구현 선택).
- 점검이 168시간을 넘겨서야 처음 돌면 한 주기 안에서 리마인드를 쓰고 바로 무응답 종료한다. 기록상 시각은 126시간·168시간이다(구현 선택, C-76).
