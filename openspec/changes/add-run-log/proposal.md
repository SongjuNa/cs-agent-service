# Proposal: 처리 실행 로그 (add-run-log)

## Why

문의 한 건의 처리 흐름(실행, run)과 그 안의 단계(step)마다 입력·출력·소요 시간·오류·언어 모델 사용량을 남겨야 한다(근거: 명세서 v1.5 FR-036 기능 설명). 1순위는 단계 결과만 남겼고 시작·끝 시각이 같으며 소요 시간과 사용량이 비어 있다(근거: 이 변경 전 `app/db/store.py` add_step, schema.sql agent_step 열). 조회 API(`GET /tickets/{id}/runs`, `GET /runs/{run_id}/steps`)도 없다(근거: 기술 명세서 v1.4 §8-1 표 "처리 기록 036").

## What Changes

- **노드 감싸기 (`app/pipeline/runlog.py`)**: 처리 흐름의 노드마다 감싸는 함수 하나가 시작·끝 시각, 소요, 그 노드 안의 언어 모델 호출(호출 이름, 지시문 버전, 입력·출력 토큰, 호출 수)을 모은다. 노드 코드에는 로그 코드를 넣지 않는다(근거: 기술 명세서 §6-5 1번째 줄, 에이전트 설계서 8-3).
  - 언어 모델 호출 계층은 호출마다 이 기록에 알리기만 한다. 부르는 곳은 그대로 한 곳이다(근거: CLAUDE.md 규칙 2, 기술 명세서 §3-5 "비용 기록").
  - 모은 값은 결과를 저장할 때 단계 행의 started_at_utc·finished_at_utc·latency_ms·prompt_version·input_tokens·output_tokens·llm_calls에 들어간다(근거: FR-036 처리 2, schema.sql agent_step).
- **전문 저장 설정**: `LOG_FULL_LLM_IO=true`일 때만 지시문·응답 전문을 가린 뒤 단계 출력에 넣는다. 기본은 꺼짐(근거: FR-036 처리 4, 기술 명세서 §1-5 환경 변수, §6-5). 저장 열 이름은 C-84.
- **로그 저장 실패**: 단계 한 행 저장이 실패해도 처리 결과 저장은 계속하고 서버 로그에 남긴다(근거: FR-036 예외 1행, §6-5).
- **끝나지 않은 실행 닫기**: 서버가 켜질 때 결과가 비어 있는 실행을 FAILED로 닫고 오류 UNKNOWN을 남긴다(근거: FR-036 예외 2행, §6-5 "다음 서버 시작 때"). 남기는 곳은 C-82.
- **보존 기간**: 매일 한 번 90일이 지난 실행을 지운다. 메시지 이력은 지우지 않는다(근거: FR-036 예외 3행, §6-5, 에이전트 설계서 7-2 시작값 "실행 기록 보관 90일"). 지울 수 없는 실행은 C-83.
- **조회 API**: `GET /tickets/{id}/runs`(실행 목록), `GET /runs/{run_id}/steps`(단계 목록)(근거: FR-036 처리 7, §8-1).
- **"왜?"에서 단계로**: 티켓 상세 근거 줄의 "왜?"에 그 줄을 만든 단계(run_id, step_id, step_name)를 붙인다(근거: FR-036 처리 7 "티켓 상세 '왜?'에서 해당 단계로 바로 간다", AC-036-5).
- **다시 처리 실행**: 처리 함수가 시작 사유를 받아 RETRY 실행도 새 run으로 남긴다. 이전 run은 그대로다(근거: FR-036 처리 5, §6-5 trigger 5개).

## Capabilities

### New Capabilities
- `run-log`: 실행·단계 기록의 시간·사용량, 실패 처리, 보존, 조회.

## 범위 밖

- **복합 문의의 문의별 run과 T5 티켓 run(AC-036-4)**: 복합 문의 분리(FR-006)와 답변 구성(FR-022)은 16번 변경이다(근거: `bootcamp/openspec/2순위_시작_전후비교.md` 결정 2의 변경 순서 16번, C-85).
- **"다시 처리" API(`POST /tickets/{id}/reprocess`)**: 티켓 상세(FR-030) 19번 변경에서 붙인다. 이 변경은 처리 함수가 RETRY 실행을 남기는 것까지 한다(근거: 화면 정의서 v1 SCR-03 "다시 처리", 변경 순서 19번, C-85).
- **처리 기록 탭 화면(C-11 "실행 기록 보기")**: 19번 변경(근거: 화면 정의서 v1 C-11, 변경 순서 19번).
- **주기 점검(리마인드·경고)의 실행 기록**: agent_run은 ticket_id가 필수이고 trigger가 5개 값뿐이라 주기 점검 실행을 담을 수 없다. 표를 고치지 않고 묻는다(근거: FR-036 입력 "주기 점검 실행으로 따로 기록", schema.sql agent_run, CLAUDE.md 규칙 4, C-80).
- **초안 단계 입력의 "넣은 항목 이름 목록"(AC-018-4)**: 고장 진단(FR-018)이 3순위라 이 변경에서 확인하지 않는다(근거: 기술 명세서 §6-5 3번째 줄, config.yaml 3순위).
- **LLM 사용량 집계 화면·주간 보고**: 여유 시 기능(평가·대시보드) 쪽이다. 이 변경은 단계 행에 숫자를 남기는 것까지 한다(근거: 에이전트 설계서 11-4 "실행 기록으로 사용량을 집계해 주 1회 팀에 보고"는 운영 절차, 기술 명세서 §3-5).

## Impact

- 새 파일: `backend/app/pipeline/runlog.py`, `backend/app/db/runs.py`, `backend/app/api/runs.py`, 시험 파일(근거: design 결정 1~5).
- 고치는 파일: `app/llm/client.py`(호출 알림·토큰), `app/pipeline/graph.py`(노드 감싸기), `app/db/store.py`(단계 열·실패 견딤), `app/api/tickets.py`(시작 사유), `app/api/messages.py`(대역·검증 사용량), `app/db/detail.py`("왜?" 단계), `app/scheduler.py`(매일 보존), `app/main.py`(시작 때 닫기), `app/config.py`(설정)(근거: design 결정 1~5).
- DB 구조는 고치지 않는다(근거: CLAUDE.md 규칙 4).
