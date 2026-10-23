# Design: 처리 실행 로그

## Context

동기는 proposal.md의 Why를 본다. 따를 기준은 다음과 같다(근거: 아래 문서들).
- 명세서 v1.5 FR-036(처리 1~7, 예외 3행, AC-036-1~5), FR-001 예외(LLM 실패 → 실행 로그), AC-001-3.
- 기술 명세서 v1.4 §6-5(실행 로그), §3-5(비용 기록), §1-5(환경 변수 `LOG_FULL_LLM_IO`), §8-1(`GET /tickets/{id}/runs`, `GET /runs/{run_id}/steps`).
- 에이전트 설계서 v1.1 8-3(실행 기록), 7-2(보관 90일), 4-2 6번(넣은 항목 이름 목록).
- schema.sql: agent_run(trigger 5개, 끝날 때 finished_at_utc·status·last_step만 바꿈), agent_step(열, 끝날 때 결과 열만 바꿈, run 삭제 때 함께 삭제), eval.self_check·eval.agent_feedback의 run_id 외래 키(삭제 연쇄 없음).

## Goals / Non-Goals

**Goals**
- 단계 행에 시간·소요·사용량을 채우고, 실패·중단·보존·조회를 FR-036대로 한다(근거: FR-036 처리 1~7, 예외 3행).

**Non-Goals**
- 복합 문의 run, 다시 처리 API, 처리 기록 화면, 주기 점검 run(proposal "범위 밖") (근거: proposal 범위 밖).

## Decisions

### 1. 노드 감싸기와 호출 기록 (`app/pipeline/runlog.py`)

| 정한 것 | 내용 | 근거 |
|---|---|---|
| 모델 이름 | 단계 행에 모델 이름 열이 없어 실행 행의 llm_model(설정 LLM_MODEL_SMALL)로 대신한다 | FR-036 처리 2·§3-5는 단계에 "모델 이름"을 두라고 하지만 schema.sql agent_step에는 그 열이 없고 agent_run.llm_model만 있다(C-86, CLAUDE.md 규칙 4) |
| 감싸는 함수 | `RunLog.timed(node, fn)`: 노드 시작·끝 시각과 그 사이의 언어 모델 호출을 모은다. `build_graph`가 노드를 등록할 때 감싼다 | 기술 명세서 §6-5 "LangGraph 노드마다 감싸는 함수(데코레이터) 하나", "노드 코드에는 로그 코드를 넣지 않는다". 이름은 구현 선택 |
| 호출 알림 | `generate_json`이 시도마다 Transport의 `on_call`(있을 때만)에 호출 이름·지시문 버전·가린 지시문을 알린다. 언어 모델 호출 계층(`app/llm/client.py`)의 `RecordingTransport`가 받아 응답·토큰과 함께 RunLog에 남긴다 | §3-5 "모든 호출의 모델 이름, 입력·출력 토큰을 agent_step에", CLAUDE.md 규칙 2(부르는 곳은 generate_json 한 곳 그대로). 알림 방식은 구현 선택 |
| 토큰 | GeminiTransport가 응답의 사용량(prompt_token_count, candidates_token_count)을 `last_usage`로 둔다. 대역 Transport는 없으므로 비운다 | §3-5, 에이전트 설계서 11장 머리말 "실제 값은 실행 기록(agent_step의 input_tokens·output_tokens)으로 바로잡는다". 속성 이름은 구현 선택 |
| 호출 → 단계 | L1→T2, L2→Q1, L3→Q7, L4→Q10, L7→Q13, L8→Q14. 그 단계 행의 llm_calls = 시도 수, 토큰 = 합, prompt_version = 마지막 시도의 지시문 파일 이름 | 기술 명세서 §2-2 단계 표(단계별 LLM 호출), FR-036 처리 2 "호출 수". 시도마다 세는 것은 구현 선택(재시도도 비용) |
| 노드 → 단계 시간 | understand→T2·Q1, rules→Q2~Q6, info_request→Q7, evidence→Q8·Q9, reply→Q10·Q11, gloss→Q13, verify→Q14. 한 노드가 낸 단계들은 그 노드의 시작·끝·소요를 같이 쓴다 | 구현 선택(C-81). schema.sql 주석은 agent_step = "노드 실행 1회"인데, 1순위가 노드 하나의 결과를 단계 여러 행으로 나눠 "왜?"가 읽으므로 행 나눔은 그대로 둔다 |
| 쓰는 때 | 실행 끝에 결과와 함께 한 번에 쓴다(1순위 방식 유지). 노드 시작 때 행을 먼저 쓰지 않는다 | 구현 선택(C-81). 처리 흐름은 읽기 트랜잭션 안에서 돌고 결과 저장이 한 트랜잭션이라서다(이 변경 전 `api/tickets.py` process_ticket) |
| 전문 | 설정 `log_full_llm_io`(환경 변수 `LOG_FULL_LLM_IO`, 기본 false)가 켜지면 단계 output_json에 `full_io`(호출·시도·지시문·응답)를 넣는다. 저장 때 가린다 | FR-036 처리 4, §6-5, §1-5. 열 이름 output_json은 C-84 |

- `runlog.py`는 언어 모델 호출 계층을 import하지 않는다. Transport 감싸개는 호출 계층 안에 두어 송신 경로가 그 계층 밖으로 나가지 않게 한다(근거: CLAUDE.md 규칙 2, 구현 선택).

### 2. 단계 저장 (`app/db/store.py`)

- `add_step`이 시간·사용량 열을 받는다. 시간이 없으면 지금 시각(이전과 같음)(근거: FR-036 처리 2, schema.sql agent_step).
- `add_step`은 한 행을 저장점(savepoint) 안에서 쓰고, 실패하면 서버 로그에 남기고 넘어간다. 결과 저장은 계속한다(근거: FR-036 예외 1행 "처리 흐름은 멈추지 않고 계속, 실패를 앱 로그에", §6-5).
- 고객 회신 재처리가 실패하면 실패 단계는 Q1이다(재처리는 Q1부터)(근거: 기술 명세서 §2-4 "고객 회신 재처리").
- 실패 실행(`_save_failure`)의 단계 행도 그 노드의 시간과 호출 수를 쓴다. 분류 단계가 두 번 시간 초과면 T2 FAILED, error_kind LLM_TIMEOUT, llm_calls 2(근거: FR-036 처리 2, AC-036-3, 기술 명세서 §3-2 1회 재시도).
- 분류 단계(T2) 입력 요약의 field_names는 1순위 그대로 둔다(AC-036-2 확인 방법)(근거: FR-036 처리 6, 이 변경 전 `_save_sub`).

### 3. 실행 열기·닫기·지우기 (`app/db/runs.py`)

| 함수 | 내용 | 근거 |
|---|---|---|
| `close_stale_runs(conn, now)` | status가 비어 있는 실행을 FAILED, finished_at_utc = now로 닫는다. 시점은 기술 명세서의 "다음 서버 시작 때"를 따른다(FR-036은 "다음 실행 시작 때", C-88). 그 실행이 그 티켓의 마지막 처리 흐름 실행이면 그 하위 문의의 pipeline_error에 "UNKNOWN: 처리 중단(서버 재시작)"을 쓴다. `main.py` 시작 때 한 번 | FR-036 예외 2행, §6-5 "다음 서버 시작 때 FAILED / UNKNOWN으로 닫는다". 단계 행은 끝에 한 번에 쓰므로 반쯤 쓴 단계가 없어 오류 종류를 pipeline_error에 둔다(C-82) |
| `purge_runs(conn, as_of, days=90)` | finished_at_utc < as_of − 90일인 실행을 지운다(단계는 함께 지워짐). eval.self_check나 eval.agent_feedback이 가리키는 실행은 지우지 않는다 | FR-036 예외 3행, §6-5 보존 90일, schema.sql 외래 키(삭제 연쇄 없음). 남기는 것은 구현 선택(C-83) |
| `ticket_runs(conn, ticket_id)` | 실행 목록: run_id, sub_ticket_id, trigger, 시작·끝, 소요(ms), status, last_step, 단계 수, 실패 단계 수, 호출 수·토큰 합, current(같은 티켓·하위 문의의 마지막 처리 흐름 실행) | FR-036 처리 1·5·7, 출력 "사용자 표시", `bootcamp/openspec/2순위_시작_전후비교.md` 15번 "오류 집계". current 계산과 실패 단계 수는 구현 선택 |
| `run_steps(conn, run_id)` | 실행 한 줄 + 단계 목록(모든 열, step_order 순) | FR-036 처리 2·7 |

- 소요(ms)는 열이 없어 시작·끝 시각으로 계산한다(근거: FR-036 처리 1 "소요(ms)", schema.sql agent_run, CLAUDE.md 규칙 4).
- 이 모듈은 언어 모델 호출 계층을 import하지 않는다(근거: 구현 선택, 주기 점검 모듈이 쓰므로 11번 시험과 같은 기준).

### 4. API와 "왜?"

- `GET /tickets/{id}/runs` → `{"ticket_id", "runs": [...]}`, 티켓이 없으면 404. `GET /runs/{run_id}/steps` → `{"run", "steps"}`, 없으면 404(근거: §8-1 표, FR-036 처리 7. 응답 모양은 구현 선택).
- 티켓 상세 근거 줄의 why에 `step`(run_id, step_id, step_name)을 넣는다. ① 유형·② 긴급도 → T2, ③ 고객·제품 → Q2, ④ 우선순위 → Q3, ⑤ 부서 → Q4, ⑥ 필수정보 → Q5, ⑦ SLA → Q6, ⑧ 근거 → Q9(정보 요청이면 Q7, Q9가 없으면 Q8)(근거: FR-036 처리 7, AC-036-5, 기술 명세서 §2-2 단계 표, 화면 정의서 v2 SCR-03M M-C-02 "agent_step(Q9)").
- 처리 함수 `process_ticket(..., trigger="INTAKE")`가 시작 사유를 받는다. RETRY도 새 run이고 이전 run은 그대로다(근거: FR-036 처리 5, §6-5 trigger 5개).
- 대역 다시 만들기·다시 검증 API의 단계 행(Q13·Q14)도 같은 기록으로 시간·사용량을 남긴다. §6-5가 예로 든 동작 중 회신은 처리 흐름 run(CUSTOMER_REPLY)으로 이미 남고, 이관은 3순위(FR-033), 리마인드는 C-80이라 이 변경에서 남기지 않는다(근거: §6-5 "노드가 아닌 동작도 같은 함수로 step을 남긴다", config.yaml 범위).

### 5. 보존 작업 (`app/scheduler.py`)

- 5분 주기 점검과 따로 하루 한 번 `purge_runs`를 돈다. 서버가 켜질 때 한 번 돌고 그 뒤 하루마다 돈다. 오류는 서버 로그에 남긴다(근거: §6-5 "매일 1회 스케줄러가 지난 run을 지운다". 작업 이름은 구현 선택).

### 6. 시험 (`tests/acceptance/test_run_log.py`)

- AC-036-1: CSV1-000004 접수(대역 Transport) → run 1개, T2부터 Q14·T6까지 순서대로 모두 SUCCESS, Q9 출력에 list_price_usd 520과 std_lead_time_weeks 4(근거: AC-036-1, product_master.csv).
- AC-036-2: T2 입력 요약의 field_names에 inquiry_subject가 없다(근거: AC-036-2).
- AC-036-3: L1 시간 초과 두 번 → run FAILED, last_step T2, T2 error_kind LLM_TIMEOUT. RETRY로 다시 처리하면 새 run이 생기고 이전 run은 남는다(근거: AC-036-3, C-85).
- AC-036-5: 우선순위 줄의 why.step으로 `GET /runs/{run_id}/steps`에서 Q3 출력(priority_rule_id, priority_trace)을 찾는다(근거: AC-036-5).
- 그 밖: 단계 시간·소요·호출 수·토큰(토큰을 내는 대역 Transport), 전문 저장 꺼짐/켜짐, 단계 저장 실패 견딤, 끝나지 않은 실행 닫기, 보존 삭제(참조된 실행은 남김), 조회 API 404, runs 모듈 언어 모델 import 금지(근거: FR-036 처리 2·4, 예외 1~3행, design 결정 3).

## Risks / Trade-offs

- C-81: 한 노드가 낸 단계(Q2~Q6 등)는 같은 소요를 보여 단계별 합이 실행 소요보다 커 보일 수 있다(근거: design 결정 1).
- C-87: 다시 처리(RETRY) run은 단계가 쓰이기 전까지 처리 흐름 실행으로 잡히지 않아, 도는 동안 상세가 이전 run을 보여 준다. 다시 처리 API를 붙이는 19번에서 정한다(근거: design 결정 3 pipeline_run, C-81).
- C-83: 자체 검사 행이 있는 실행(대부분의 접수 실행)은 90일이 지나도 남는다(근거: schema.sql eval.self_check.run_id).
