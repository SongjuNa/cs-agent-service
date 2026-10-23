# Design: 상태 관리와 SLA 두 시계

## Context

동기는 proposal.md의 Why를 본다. 따를 기준은 다음과 같다.
- 명세서 v1.5: FR-025(처리 1~5, 전이표, 예외, AC-025-1·3·4), FR-026(처리 1~6, 예외, AC-026-1~6), FR-031 처리 4·6, FR-001 처리 4, D19·D20·D21·D22.
- 기술 명세서 v1.4: §2-2 T6 행, §6-4(전이표, inquiry_sla, 티켓 대표값, 주기 점검 3·4, 시계 돌리기), §10-1(재생 채점).
- 테이블 정의서 v1.3(schema.sql): svc.status_transition 13행, svc.transition(), svc.inquiry_sla(), svc.v_ticket_summary, sub_ticket.version, scoring 스키마의 같은 함수.

## Goals / Non-Goals

**Goals**
- 상태는 전이표대로만 바뀌고 이력이 사건 시각으로 남는다. 상세 API가 두 시계를 보인다(근거: FR-025·026 출력).

**Non-Goals**
- 회신 입력, 스케줄러, 경고, 화면 표시(proposal "범위 밖").

## Decisions

### 1. 전이 함수 (`app/status/transitions.py`)

| 항목 | 정한 것 | 근거 |
|---|---|---|
| 부르는 법 | `transition(conn, sub_ticket_id, to_status, event_kind, at, actor, reason=None, final_action=None, expected_version=None)` → `svc.transition()`을 부른다 | 기술 명세서 §6-4 "상태를 바꾸는 함수는 하나", schema.sql svc.transition 주석 |
| 거부 | DB가 "허용되지 않은 전이"로 거부하면 `TransitionRefused(현재 상태)`. API 문구 "현재 상태(○○)에서는 할 수 없는 작업"(409) | 명세서 FR-025 처리 1, 예외 1행 |
| 동시 수정 | `expected_version`을 받으면 `SELECT … FOR UPDATE`로 version을 읽어 다르면 `ConcurrentChange`. API 문구 "다른 사용자가 먼저 변경함. 새로고침"(409) | 명세서 FR-025 예외 2행, schema.sql sub_ticket.version 주석 "동시 수정" |
| 시각 | 사건 시각을 넘긴다(저장 시각 아님) | 기술 명세서 §6-4 "상태 이력은 앱이 사건 시각으로 쓴다"(T34) |
| 언어 모델 | 이 폴더는 `app.llm`을 import하지 않는다 | 명세서 그룹 4 머리 "LLM은 쓰지 않는다", config.yaml 설계 원칙 2 |

### 2. 전이를 일으키는 곳

| 사건 | 전이 | 시각·주체 | 근거 |
|---|---|---|---|
| 처리 흐름 종료(결과 저장) | NEW인 하위 문의만 NEW → IN_PROGRESS, PIPELINE_DONE. 이미 NEW가 아니면(다시 처리 등) 그대로 | 결과 저장 시각, SYSTEM. 결과 저장과 같은 트랜잭션. 실행 기록 T6 단계 1행 | 기술 명세서 §2-2 T6 "NEW→IN_PROGRESS 이력 1행(PIPELINE_DONE)", 명세서 FR-001 처리 4 "흐름이 끝나면", 전이표 PIPELINE_DONE은 NEW에서만 |
| T6 전이 실패 | NEW로 두고 run PARTIAL, T6 단계 FAILED | — | §2-2 T6 실패 칸 "전이 실패 → NEW 유지, run PARTIAL" |
| 처리 흐름 실패(run FAILED) | 없음(NEW 그대로) | — | §2-2 T2 행 "티켓 NEW 유지, run FAILED", 명세서 FR-001 예외 표 |
| 정보 요청 발송 | → WAITING_CUSTOMER, INFO_REQUEST_SENT | 발송 시각, 상담원 ID. SENT 행과 같은 트랜잭션 | 명세서 FR-031 처리 3·4, FR-025 전이표 |
| 최종 답변 발송 | → RESOLVED, FINAL_REPLY_SENT. resolved_at_utc는 transition()이 쓴다 | 위와 같음 | 같은 근거, schema.sql transition 주석 "RESOLVED가 되면 resolved_at_utc" (근거: 명세서 FR-031 처리 4) |
| 발송 때 전이표에 없는 전이 | 발송 기록(SENT, APPROVED, 1차 응답 시각)은 남기고 상태는 그대로. 응답 notes에 "종료된 문의입니다. 메시지만 기록됨"(CLOSED일 때) 또는 "현재 상태(○○)에서는 할 수 없는 작업 — 메시지만 기록됨", 실행 기록(trigger AGENT_EDIT, T6 FAILED, run PARTIAL) | 발송 시각 | FR-031 예외 3행. 문구 둘째와 실행 기록 모양은 구현 선택 |
| 발송 때 version이 다름 | 409 "다른 사용자가 먼저 변경함. 새로고침", 아무것도 쓰지 않는다 | — | FR-025 예외 2행 |

- **AC-025-1의 "NEW → WAITING_CUSTOMER"**: T6이 처리 끝에 IN_PROGRESS로 바꾸므로, 정보 요청을 보낼 때는 IN_PROGRESS → WAITING_CUSTOMER가 된다. 전이표는 두 경우를 모두 허용한다. 기술 명세서 T6과 명세서 FR-001 처리 4를 따르고 시험은 IN_PROGRESS → WAITING_CUSTOMER로 확인한다(개발_결정_기록 C-51, 조장 확인 필요). (근거: 개발_결정_기록 C-51)
- **AC-015-4 "티켓 상태는 바뀌지 않는다"**: 초안을 만든다고 상태가 바뀌지 않는다는 뜻으로 읽는다. 처리 끝 T6 전이는 초안 생성이 아니라 처리 흐름 종료 사건이다(근거: FR-025 전이표 "NEW → IN_PROGRESS 처리 흐름 종료"). 끝난 ticket-detail spec의 해당 문장을 MODIFIED 델타로 고치고 1순위 시험의 기대값을 IN_PROGRESS로 고친다(C-51).
- **send 요청의 `expected_version`**: 선택 입력. 화면이 상세를 읽을 때의 version을 넘긴다. 보내지 않아도 행 잠금(FOR UPDATE)과 전이표가 상태 충돌을 막는다(svc.transition()에 version 인자가 없어 앱에서 검사하는 것은 구현 선택).

### 3. 자동 종료 점검 (`app/status/closing.py`)

`close_due(conn, as_of) -> list[(sub_ticket_id, event_kind, at)]`가 두 가지를 차례로 한다(근거: 기술 명세서 §6-4 주기 점검 3·4).

| 점검 | 대상 | 전이 시각 | 근거 |
|---|---|---|---|
| 무응답 종료 | status = WAITING_CUSTOMER이고 마지막 INFO_REQUEST SENT 시각 + 168h ≤ as_of이며 그 뒤 CUSTOMER_REPLY가 없음 | 그 SENT 시각 + 168h, SYSTEM, NO_REPLY_168H, final_action = CLOSED_NO_RESPONSE | §6-4 3, FR-025 처리 4, D22 |
| 해결 뒤 종료 | status = RESOLVED이고 마지막 FINAL_REPLY SENT 시각 + 168h ≤ as_of이며 그 뒤 CUSTOMER_REPLY가 없음 | 그 SENT 시각 + 168h, SYSTEM, NO_REPLY_168H_AFTER_RESOLVED | §6-4 4, FR-025 처리 4-1, D20 |

- 상태 조건은 전이표가 허용하는 출발 상태로 거르는 것이다(구현 선택).
- 해결 시각(resolved_at_utc)은 schema.sql transition()대로 RESOLVED일 때만 쓴다. 명세서 FR-025 출력 "RESOLVED 또는 CLOSED로 바뀐 첫 시각"과 §6-4 "다시 RESOLVED면 마지막 시각"이 서로 다르다(C-56). 무응답 종료 문의는 해결 시각이 비어 있다. (근거: schema.sql transition 주석, 명세서 FR-025 출력, 기술 명세서 §6-4, C-56)

### 4. SLA 두 시계 (`app/sla/clock.py`)

| 항목 | 정한 것 | 근거 |
|---|---|---|
| 계산 | `svc.inquiry_sla(as_of)`를 하위 문의 번호로 걸러 읽는다. 화면은 as_of = 지금 | 기술 명세서 §6-4, schema.sql inquiry_sla 주석 |
| 돌려주는 값 | fr_elapsed_h, fr_status, fr_target_h, res_elapsed_h, res_status, res_target_h, remaining_h, wait_h, notes | 명세서 FR-026 출력 |
| 목표 없음 | fr·res 상태 None, notes에 "SLA 미정" | FR-026 예외 1행 |
| 음수 경과 | 0으로 바꾸고 notes에 "시간 기록 확인 필요" | FR-026 예외 3행, 기술 명세서 §6-4 |
| 대기 구간 역전 | inquiry_sla는 이력을 시각순으로 이어 구간을 만들므로 나온 시각이 들어간 시각보다 빠른 구간이 생기지 않는다. 따로 다루지 않는다 | FR-026 예외 2행, schema.sql inquiry_sla(lead … ORDER BY changed_at_utc) |
| 표시 | 화면 문구는 FR-030(19번 변경)에서. API는 숫자(소수 둘째 자리, inquiry_sla 그대로) | FR-026 처리 5. 소수 자리는 schema.sql numeric(8,2) |

- FR-025 예외 1행·FR-026 예외 3행의 "실행 로그에 기록"은 화면이 SLA를 읽을 때마다 로그를 쓰게 되어 여기서는 하지 않는다. 처리 실행 로그(FR-036, 15번 변경)에서 정한다(C-57). (근거: 명세서 FR-036, C-57)

### 5. 상세 API 추가 값 (`GET /tickets/{id}`)

- 티켓: `summary` = svc.v_ticket_summary의 status(대표 상태), rep_sub_ticket_id, rep_res_status, rep_remaining_h, open_count, inquiry_count(근거: 기술 명세서 §6-4 티켓 대표값, FR-025 처리 5).
- 하위 문의마다: `state`(status, version, resolved_at_utc, final_action), `sla`(결정 4), `history`(ticket_status_history 시각순: from_status, to_status, event_kind, changed_at_utc, changed_by, reason — 열 이름 그대로), `wait_intervals`(WAITING_CUSTOMER에 들어간 시각·나온 시각, 아직이면 나온 시각 없음)(근거: FR-025 출력 "현재 상태, 상태 변경 이력, 대기 구간 목록, 해결 시각"). 상세 API에 넣는 것은 구현 선택이다(§8-1 `/timeline`은 19번 변경).

### 6. 정답지 재생 채점 (`jobs/replay_gold.py`)

채점 코드다. gold 정답 열을 읽고 scoring 스키마와 eval 표에만 쓴다(근거: 기술 명세서 §10-1 2·3·4번, CLAUDE.md 규칙 6 예외).

문의 1건을 이렇게 재생한다(근거: §10-1 3번 "received_at, first_response_at_utc, resolved_at_utc, customer_wait_hours를 대기 구간 하나로 넣고", 테이블 정의서 scoring 주석). 사건 순서는 전이표가 허용하는 순서로 정했다(구현 선택).

1. scoring.ticket·sub_ticket(seq 1)을 넣는다. 목표는 정답 유형·등급·우선순위(조정 건은 조정값)로 `find_sla_target`을 불러 다시 조회한다(근거: §10-1 3번 "목표 시간은 정답 우선순위로 조회", §10-2 SLA 목표 행).
2. INTAKE(접수 시각). 정답 status가 NEW가 아니면 PIPELINE_DONE(접수 시각).
3. info_request_sent = Y면 INFO_REQUEST_SENT(1차 응답 시각).
   - 정답 final_action = CLOSED_NO_RESPONSE면 1차 응답 + 168h에 NO_REPLY_168H로 닫는다(D22). (근거: 명세서 D22)
   - 정답 status = WAITING_CUSTOMER면 그대로 둔다(대기 중. D19 음수 대기 3건도 여기에 든다). (근거: 정답지 status 열, D19)
   - 그 밖이면 1차 응답 + customer_wait_hours에 CUSTOMER_REPLY. (근거: 기술 명세서 §10-1 3번 customer_wait_hours)
4. 정답 escalated = Y면 ESCALATE. 데이터에 이관 시각이 없어 바로 앞 사건 시각에 넣는다. 전이표가 IN_PROGRESS → ESCALATED만 허용하므로 정보 요청·회신 뒤에 둔다. 이관은 해결 시계를 멈추지 않아 SLA 값에는 영향이 없다(근거: schema.sql inquiry_sla 주석 "ESCALATED는 멈추지 않는다". 시각은 구현 선택, C-58).
5. resolved_at_utc가 있으면 FINAL_REPLY_SENT(해결 시각). 정답 status = CLOSED면 해결 + 168h에 NO_REPLY_168H_AFTER_RESOLVED(D20).
6. sub_ticket.first_response_at_utc = 정답 first_response_at_utc.

- 비교: `scoring.inquiry_sla('2026-09-30 23:59+00')`와 정답 SLA 목표 두 열, sla_first_response_status, sla_resolution_status(일치), sla_elapsed_hours(오차 0.1h). 경과 제외는 eval.exclusion을 읽고, 아직 적재 전이면(W8) D19 정의대로 데이터에서 10건을 뽑는다(근거: §10-3, D19).
- 출력: eval_run(ALL_4000) 1행, eval_case(행 × 항목), eval_summary(항목별), `scoring/scoring_ALL_4000_{날짜}.csv`(근거: §10-1 4번. csv 이름의 정답지 버전 자리는 ALL_4000으로 채움, 구현 선택). 시험은 롤백해 남기지 않는다.
- 상태 재생은 §10-3 "정답 없음: 상태 전이 재생 → 일치율 대신 생성·존재 기록"을 따라 이력이 생긴 건수만 기록한다. 재생 입력에 정답 status를 쓰므로 일치율은 뜻이 없다. §10-2 "상태 재생: 참고 지표"와 다르다(C-55). (근거: 기술 명세서 §10-3, §10-2, C-55)
- AC-026-6은 "팀 정답지"를 말하지만 기술 명세서 §10-1 1·3번은 SLA 계산식을 운영진 4,000건으로 채점한다. 팀 정답지 적재(W9)는 정하지 않았다(C-55). (근거: 명세서 AC-026-6, 기술 명세서 §10-1, C-55)
- 실행 결과(개발 DB): 목표 4,000/4,000, 해결 상태 4,000/4,000, 1차 응답 상태 3,998/4,000, 경과 3,831/3,990(제외 10). (근거: 시험 test_ac_026_6_replay_4000 실행 결과)
  - 1차 응답 상태 2건(CSV1-003890, 003951)은 1차 응답 시각이 스냅샷 뒤인 D19 행이다. 정답은 그 시각으로 BREACHED를 냈고, 스냅샷 기준 계산은 아직 응답 전이라 ON_TRACK이다(C-53). (근거: tickets.csv CSV1-003890·003951의 first_response_at_utc, C-53)
  - 경과 159건은 무응답 종료 전부다. 정답은 대기 0h, 경과 = 종료 − 접수인데, FR-026 처리 3은 WAITING_CUSTOMER 구간을 뺀다(C-54). (근거: tickets.csv customer_wait_hours, 명세서 FR-026 처리 3, C-54)

### 7. 시험

- `tests/acceptance/test_status_sla.py`: AC-025-1(발송 뒤 WAITING_CUSTOMER와 이력), AC-025-3(시계 돌리기 종료), AC-025-4(NEW → RESOLVED 거부), FR-025 처리 4-1(해결 뒤 종료), 예외 2행(동시 수정), FR-031 예외 3행(전이 거부 시 메시지만 기록), AC-026-1~5(재생한 문의의 두 시계), FR-026 예외 1·3행, AC-026-6(4,000건 재생, 위 열린 항목은 이름으로 확인), AC-025-5(이력 생성 기록), 상세 API 값, 상태·SLA 코드의 언어 모델 import 금지. (근거: CLAUDE.md 규칙 7)
- 경과 비교는 모두 0.1h 오차로 한다. AC-026-3 "323.0h"는 계산값 322.94h다(근거: §10-2 "오차 0.1h").
- 1순위 시험 고침: AC-015-4 기대값 IN_PROGRESS, AC-031-1 상태 WAITING_CUSTOMER, AC-031-2 상태 RESOLVED(근거: 명세서 AC-031-1·2 원문).

## Risks / Trade-offs

- 4,000건 재생 시험은 약 15초 걸린다. 연결 하나를 롤백해 scoring·eval에 남기지 않는다(구현 선택, 1순위 시험과 같은 방식).
- v_ticket_summary는 모두 끝난 티켓의 상태를 대표 문의 상태로 낸다. 명세서 FR-025 처리 5 "모두 끝났으면 RESOLVED(모두 CLOSED면 CLOSED)"와 RESOLVED·CLOSED가 섞인 복합 문의에서 다를 수 있다. 복합 문의(16번 변경) 전에는 하위 문의가 1개라 차이가 없다(C-52). (근거: schema.sql svc.v_ticket_summary, 명세서 FR-025 처리 5, C-52)
- 정답지에서 해결 뒤 168h가 스냅샷 전에 지났는데 RESOLVED인 행이 479건이다. D20 규칙만으로는 정답 status가 나오지 않는다. 재생은 정답 status를 따라 닫으므로 SLA 값에는 영향이 없다(C-55에 함께 적음). (근거: tickets.csv status·resolved_at_utc, 명세서 D20, C-55)
