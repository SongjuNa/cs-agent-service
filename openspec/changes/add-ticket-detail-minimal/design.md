# Design: 티켓 상세 최소판

## Context

동기는 proposal.md의 Why를 본다. 따를 기준은 다음과 같다.

- 명세서 v1.5: FR-024(처리 1~6, 예외, AC-024-1~4), FR-031(처리 1~9, 예외, AC-031-1~6), FR-039 AC-039-2·4, FR-049 AC-049-2~4, FR-015 AC-015-4, FR-038 AC-038-1.
- 화면 정의서 v2: 0-1~0-7절, SCR-03M, 팝업 P1·P2·P7·P8, 부록 A.
- 기술 명세서 v1.4: §2-4(실행 시작), §5-7(검토 표시 5개), §6-2·§6-3(서비스 표, 지우지 않는 기록), §7(가리기), §8-1(API).
- 테이블 정의서 v1.3(schema.sql): svc.ticket, sub_ticket, ticket_message, message_gloss, inquiry_field, ticket_status_history, agent_run, agent_step, eval.self_check, svc.transition().
- 에이전트 설계서 v1.1 4-10절(다시 검증, STALE), 6-3절(⑤ 상태 4값).

## Goals / Non-Goals

**Goals**
- `jobs/run_tickets.py`로 넣은 문의를 `/tickets/{ticket_id}` 화면에서 열어 근거를 보고, 초안을 고쳐 승인·발송할 수 있다(근거: 화면 정의서 v2 0-2절, SCR-03M ①).

**Non-Goals**
- 상태 전이·SLA 계산, 2순위 화면(proposal "범위 밖").

## Decisions

### 1. 접수 저장 (`app/db/store.py` `create_ticket`)

| 항목 | 정한 것 | 근거 |
|---|---|---|
| 입력 | channel, customer_id, product_code, language, inquiry_body, received_at_utc, 선택: inquiry_subject, source(SIMULATOR/LOAD), source_ticket_id | §8-1 POST /tickets, gold.v_inputs 6열, svc.ticket 열 |
| 검사 | 본문 1~2,000자, 고객이 ref.customer에 없으면 400 "등록되지 않은 고객" | schema.sql ticket.inquiry_body CHECK, 명세서 FR-001 D25·AC-001-2, 기술 명세서 §8-1 "미등록 고객 거부". 문구는 기준 문서에 없어 구현 선택(C-47) |
| 번호 | 새 번호 `CSV1-` + svc.ticket_new_no 6자리(CSV1-004001부터). 불러온 문의는 source = LOAD, source_ticket_id = 원본 번호 | schema.sql 4-2 주석 |
| 한 트랜잭션 | ticket(customer_tier = 접수 당시 ref.customer.tier), sub_ticket(seq 1, NEW), INQUIRY 메시지(CUSTOMER, RECEIVED, sent_at_utc = 접수 시각, 원문 body, mask_count = 가린 곳 수, sent_by_name = CUSTOMER), `svc.transition(id, 'NEW', 'INTAKE', 접수 시각, 'SYSTEM')` | §2-4 실행 시작, §7, schema.sql transition 주석 "접수 이력도 이 함수로" |
| 처리 | 응답 뒤 백그라운드 작업이 새 연결로 처리 흐름을 돌린다. 시작할 때 agent_run(trigger INTAKE, status NULL = 처리 중)을 넣고, 끝나면 결과를 저장하고 finished_at_utc·status·last_step을 채운다 | §2-4, schema.sql agent_run 주석·보호 장치 |

### 2. 결과 저장 (`save_outcome`)

| 표 | 쓰는 값 | 근거 |
|---|---|---|
| ticket | body_language, body_language_uncertain만 UPDATE | §6-2 ticket |
| sub_ticket | category_code, evidence_sentences, urgency_flag, product_code, error_code_reported, fw_version_reported, priority(= priority_final), priority_rule_id, routing_rule_id, assigned_dept, return_kind, sla_id, required_info, provided_info, missing_info, missing_blocking_info, 두 SLA 목표, evidence_json(`[{doc_id, section, quote, score, chunk_id}]`, quote = 절 본문 첫 문장 200자까지), reference_doc_id·reference_section(1위 후보), no_evidence_flag, pipeline_error | §6-2 sub_ticket, 테이블 정의서 evidence_json `[{doc_id, section, quote, score}]`, 화면 정의서 M-C-02 "인용문". chunk_id 키를 더하는 것은 구현 선택(절 본문을 /chunks로 열려고, C-42) |
| inquiry_field | 제공 항목마다 field, value_raw, value_norm, source = INQUIRY, source_message_id = INQUIRY 행. span은 가린 본문 기준이라 비운다 | §6-2 inquiry_field. span을 비우면 FR-024·화면 정의서 C-07의 "본문 위치" 표시를 못 한다. 구현 선택(C-43) |
| ticket_message | 초안마다 SYSTEM·DRAFT 행(message_type, language, body, mask_count, sent_at_utc = 만든 시각, sent_by_name = SYSTEM) | §6-2, CLAUDE.md 규칙 3 |
| message_gloss | 대역이 있으면 (message_id, ko, body, numbers_match, made_at_utc) | schema.sql 4-5 |
| eval.self_check | 초안마다 DRAFT_CHECK 1행(답변은 인용·숫자 대조, 정보 요청은 막는 항목 라벨 누락 검사), 확인 표시 1개마다 1행(아래 표), 초안마다 VERIFY 1행. passed_yn, detail | §5-7, 에이전트 설계서 4-10 저장, 6-1 3번 "누락 검사: L3는 막는 항목 라벨" |
| agent_step | 단계마다 1행(T2, Q1, Q2~Q6, Q7 또는 Q8·Q9, 답변이면 Q10, Q11, Q13, Q14). output_json은 그 단계 결과를 가린 글로(규칙 판정 과정, 조회값 포함). 시각은 실행 끝 시각, latency는 비움 | §6-2 agent_step "output_json이 … '왜?' 화면이 읽는다", §7 실행 로그 가리기. 저장 자체는 구조 문서 4장 "1순위는 서버 로그로 충분"과 달라 C-38, 시각·latency는 구현 선택(C-50) |

**확인 표시 → check_type** (테이블 정의서 v1.3 self_check 주석의 9값만 쓴다. 맞는 값이 없는 표시 "자동 번역 실패", "초안 생성 실패. 다시 시도", "접수 시점 최신 없음", "검색문 없음", "색인 없음", "표에 없음"은 agent_step flags에만 남기고 화면 "기타 표시"로 보인다. 그래서 ③에 잡히지 않는다. 기술 명세서 §5-7 ③ "상태 객체 flags와 같은 내용"과 다르므로 C-41. 새 check_type 값은 CLAUDE.md 규칙 4에 따라 만들지 않았다)

| check_type | 표시 |
|---|---|
| LOW_CONFIDENCE | 확신 낮음, 분류 실패, 긴급도 판정 실패 |
| LANG_UNCERTAIN | 언어 판정 불확실 |
| EXTRACT_FAILED | 추출 실패, 형식 확인(…), 값 충돌(…) |
| PRODUCT_UNKNOWN | 제품 미확정, 제품 확인 필요, 펌웨어 없는 제품 — 분류 재검토 |
| RULE_FAILED | 우선순위 미정, 배정 규칙 없음 — 분류 재검토, SLA 미정, SLA 정책 없음 — 데이터 확인, …뒤 계산됨 |
| RETURN_REASON | 반품 사유 확인 필요 |
| NO_EVIDENCE | 근거 없음, 근거 없음 — 상담원 작성 필요, 제품 문서 미검색, 검색 실패 |

- DRAFT_CHECK·VERIFY의 detail에는 검사한 본문의 SHA-256(`body_sha256`)을 더 넣는다. ⑤ STALE은 최신 VERIFY의 body_sha256이 지금 초안 본문과 다를 때다(근거: 에이전트 설계서 6-3 STALE "임시 저장한 뒤 다시 검증하지 않았으면". 판정 방법은 구현 선택).
- 처리가 실패하면(run FAILED) agent_run.status = FAILED, last_step, sub_ticket.pipeline_error = "오류 종류: 메시지"(근거: §2-4, 화면 정의서 H-04).

### 3. 상세 묶음 (`GET /tickets/{id}`, `app/db/detail.py`)

- 돌려주는 것: ticket(머리, 원본 번호, 채점용 문의 여부 = eval.gold_set에 source_ticket_id가 있음, 고객사·등급·국가), run(status, last_step, processing), sub_tickets[0](판단값, 근거 줄, flags), drafts(현재 DRAFT·APPROVED, 대체되지 않은 것, 최신 대역, review_marks), sent(SENT 행)(근거: §8-1 GET /tickets/{id}, 화면 정의서 SCR-03M ④ H·C·R).
- 근거 줄 C-01~M-C-02는 저장된 값과 agent_step.output_json에서 만든다. 비어 있으면 "없음({사유})": 분류 실패 → "없음(분류 실패)", 정보 요청 분기라 검색을 안 했으면 "없음(정보 요청 중)", 근거 후보가 비면 "없음(근거 없음)"(근거: FR-024 처리 2·5·예외 1행, AC-024-3, 기술 명세서 §2-5 분기③ "막는 정보가 있으면 Q7, 검색 안 함"). 명세서 AC-024-1·화면 정의서 ⑦은 CSV1-000017에 "TG-ACB-AS-2000 후보 절"을 보이라고 해서 처리 흐름과 다르다. 흐름(§2-5)을 따르고 C-39로 올린다. "정보 요청 중" 문구는 구현 선택.
- 규칙 행 원문(P1 "왜?")은 ref.priority_rule, ref.routing_rule, ref.sla_policy에서 읽고, 필수정보 라벨은 Q5 결과(ref.required_info_rule·ref.required_info_field에서 만든 것)를 읽는다(근거: 화면 정의서 P1 출처).

### 4. 검토 표시 5개 (`review_marks`)

| 표시 | 계산 | 근거 |
|---|---|---|
| ① | 그 초안의 최신 DRAFT_CHECK가 통과(답변: 인용·숫자, 정보 요청: 막는 항목 라벨) | §5-7, 에이전트 설계서 6-1 3번 |
| ② | FINAL_REPLY면 missing_blocking_info = [] (걸리면 라벨). 정보 요청은 통과 | §5-7, 화면 정의서 0-6 |
| ③ | 그 하위 문의의 최신 INTAKE 실행의 self_check 중 passed_yn = N이 없음(VERIFY 제외) | §5-7 ③, 화면 정의서 0-6 |
| ④ | urgency_flag ∉ {SAFETY, SITE_DOWN}. 해당하면 state = CHECK, "④ 확인 필요: 안전 문의" | §5-7, 명세서 FR-024 처리 6·AC-024-4. 화면 정의서 0-6·에이전트 설계서 6-3은 "안전 문의 — 확인 필요"라 명세서 문구를 따름(C-40) |
| ⑤ | 최신 VERIFY: PASSED / FOUND / FAILED, body_sha256이 다르면 STALE. 대역 없음 꼬리말 | §5-7, 에이전트 설계서 6-3, 8번 변경 VerifyResult |

모양: `[{no, passed, state?, text, findings?}]`, 모두 통과면 summary = "검사 5개 통과"(근거: 화면 정의서 0-6 "검사 5개 통과"). §5-7은 `{no, passed, reason}`이고 ⑤만 state·findings다. 이름 reason→text, ④의 state, summary는 구현 선택(C-48).

### 5. 초안 API (`app/api/messages.py`)

| API | 하는 일 | 근거 |
|---|---|---|
| `PUT /messages/{id}` {body} | DRAFT만. body 저장 → 새 agent_run(AGENT_EDIT)에서 자체 대조(DRAFT_CHECK 새 행)와 대역(L7, message_gloss 새 행). L8은 부르지 않음. DB 오류면 500 "저장하지 못함. 다시 시도" | §8-1, FR-031 처리 7, 추가 결정 가3, schema.sql agent_run.trigger, 화면 정의서 P8. 임시 저장 때 자체 대조를 다시 도는 것은 구현 선택(①을 최신으로) |
| `POST /messages/{id}/gloss` | 새 agent_run(RETRY, 구현 선택: §6-5는 [다시 검증]만 RETRY로 정함)에서 L7 1회 → message_gloss 새 행. 실패면 502 "대역을 만들지 못함" | §8-1, 화면 정의서 P8 |
| `POST /messages/{id}/verify` | 새 agent_run(RETRY)에서 L8 1회 → VERIFY 새 행(실패도 행으로). 실패면 ⑤가 "검증 못 함(실패)"이고 화면은 P8 "검증을 하지 못함"을 띄운다 | §8-1, 4-10 "다시 도는 때", §6-5, 화면 정의서 P8 |
| `POST /messages/{id}/send` {final_body, override_check} | 아래 표 | FR-031 |

**send 순서** (근거: 명세서 FR-031 처리 1·2·3·5, 예외 표, §8-1 send, 화면 정의서 P7)

1. `X-Agent-Id`가 없으면 400 "상담원 ID를 입력하세요". 본문이 비면 400 "내용을 입력하세요".
2. 이미 SENT 행이 있거나 초안이 DRAFT가 아니면 409 "이미 발송된 초안".
3. 검사: 최종 본문 자체 대조(답변은 인용·숫자, 근거 후보·조회값은 그 실행의 저장값. 정보 요청은 막는 항목 라벨), ⑤ 지적(FOUND), 답변인데 막는 항목 남음(FR-031 예외 5행). 하나라도 있고 override_check가 아니면 409 + 목록. ⑤ FAILED·STALE은 목록에 줄로만 넣고 확인을 요구하지 않는다(근거: 에이전트 설계서 7-1, 화면 정의서 P7 "⑤ 실패·고친 뒤").
4. 한 트랜잭션: SENT 행(sender AGENT, sent_by_name = 상담원 ID, source_draft_id, edited_yn = 본문이 초안과 다름, override_check, language = 초안 언어, mask_count), 초안 → APPROVED, 정보 요청이면 info_request_sent = true(근거: 명세서 FR-013 데이터 주의 "요청 발송 여부는 … FR-015·031에서 상담원이 정한다"), first_response_at_utc가 비었으면 발송 시각. 같은 초안의 두 번째 SENT는 유일 색인이 막는다.
5. 대역은 넣지 않는다(FR-031 처리 8, AC-039-2).

화면 P7은 승인을 누르면 먼저 지금 본문을 임시 저장하고 상세를 다시 읽어 검토 표시 5개를 최신값으로 보이고(모두 통과면 "검사 5개 통과 — 발송할까요?"), 409면 걸린 목록과 notes를 보인 뒤 확인을 받는다(근거: FR-031 처리 2, 화면 정의서 P7).

### 6. 의존성 주입 (`app/api/deps.py`)

DB 연결, Transport, Embedder를 FastAPI 의존성으로 두어 시험에서 대역 Transport·임베딩과 롤백되는 연결로 바꾼다(구현 선택).

### 7. 화면 (`frontend/`)

- Vite + React + TypeScript. 페이지 하나(`/tickets/:id`)와 부품: 사이드바, 머리 막대(상담원 ID 입력·문의 번호 입력, localStorage), 요약 머리, 탭 4개(보낼 것·시스템이 판단한 것만 켬), 검토 표시 줄, 초안+대역 편집기(인용 링크, 대조 불일치 Red 밑줄, ⑤ 지적 Red 점선 밑줄), 팝업 P1·P2·P7·P8(근거: 화면 정의서 v2 0-4·0-5·0-7절, SCR-03M).
- 처리 중이면 2초마다 다시 읽는다(근거: §2-4 화면 갱신).
- 색은 0-5절 값만 쓰고 늘 글자·기호를 함께 쓴다(근거: 화면 정의서 0-5절).
- 그 밖의 화면 요구: 인용·숫자를 누르면 P2(절 본문, 숫자는 조회값 출처. 본문을 못 열면 인용 문자열과 "본문 열기 실패"), 검토 표시를 누르면 해당 위치로 옮겨 감(①③→C-10, ②→C-07, ④→C-02, ⑤→지적 문장), 검증 중 표시(M-R-01), 고친 뒤 새 대역이 오기 전에는 이전 대역에 "이전 내용", 대역이 없으면 "대역 없음(번역 실패)" + [다시 만들기], 발송 뒤 "발송됨 {시각} · {상담원 ID}" 읽기 전용 카드와 "상담원 수정" 칩(근거: FR-024 처리 3·예외 2행, FR-039 처리 4·예외, FR-031 출력, 화면 정의서 0-7, R-03, M-R-01·02, CP-8, P2).
- 타입은 OpenAPI에서 생성하지 않고 손으로 적는다. 기술 명세서 §8-1·구조 2장 "OpenAPI에서 만든 타입"과 다르다(구현 선택. 화면 하나라 생성 도구를 들이지 않음, C-45).
- API 주소는 개발 서버 프록시(`/api` → 8000)로 붙인다(구현 선택).

### 8. 문의 넣기 (`jobs/run_tickets.py`)

`python -m jobs.run_tickets CSV1-000017 CSV1-000004 …`: gold.v_inputs에서 입력 6열을 읽어 `POST /tickets`(source LOAD)로 보내고 새 번호와 화면 주소를 출력한다(근거: 프로젝트 구조 1순위 판 2장, CLAUDE.md 규칙 6).

### 9. 시험

- API 시험(대역 Transport, 롤백 연결): AC-024-1·2(절 본문, 못 열면 "본문 열기 실패")·3·4, 정보 요청 라벨 누락, AC-031-1·2·3·5(상태 부분 제외), AC-015-4, AC-038-1(저장·실행 기록 부분), AC-039-2·4, AC-049-2·3·4, STALE·[다시 검증], 미등록 고객.
- 화면: `npm run build`(타입 검사)와 Playwright 화면 확인 1회(구현 선택. 화면 AC는 API 시험으로 대신, C-46).

## Risks / Trade-offs

- 백그라운드 작업은 서버가 꺼지면 사라진다. 처리 중으로 남은 실행은 다시 처리(2순위) 때 정리한다(근거: §2-4, 다시 처리는 2순위, C-49).
- 시험 DB에 svc 행이 남으면 기준정보 다시 넣기가 막힌다. 시험은 연결 하나를 롤백해 남기지 않는다(근거: jobs/load_reference.py 주석. 방법은 구현 선택).
