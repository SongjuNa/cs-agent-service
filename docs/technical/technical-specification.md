# 기술 명세서 — 해외고객향 C/S 대응 AI Agent

| 항목 | 내용 |
|---|---|
| 작성일 / 버전 | 2026-10-15 / v1.2. v1.1(2026-10-14, 조장 승인 2026-10-15)에 조장 결정(답변 근거 = sub_ticket.evidence_json)과 DB 설계 이유서 v1.1(bootcamp/erd/DB_설계_이유서_v1.1.md)의 판단을 반영했다. v1.0→v1.1 변경 49건과 v1.1→v1.2 변경은 기술_명세서_v1.1_변경_목록.md에 전·후로 적었다 |
| 함께 보는 문서 | 프로젝트 기획서 v1.4(무엇을, 왜), 기능 요구사항 명세서 v1.3(bootcamp/기획서/기능_요구사항_명세서_v1.3.md: MVP 기능 36개 + 추가 개발 6개, 기능별 입력·처리·출력·완료 기준), 테이블 정의서 v1.1(표·열·제약), ticket/sub_ticket 컬럼 분리안(2026-10-14), DB 설계 이유서 v1.1(bootcamp/erd/: 표·열의 이유, 평가 표 7개, §6-2 추가 제안 판단) |
| 이 문서가 정하는 것 | 구현 방식: 시스템 구성, 처리 흐름, LLM 호출, 검색·진단, 규칙 엔진, 저장 구조, 마스킹, API·화면, 기능이 아닌 작업, 채점 배치 |
| 근거 데이터 | 학습 데이터 v1: README.html, tickets.csv 4,000건(train 2,800 / valid 603 / test 597), resolution_cases.csv 800건, ref/ CSV 12개, docs/ 107개(doc_index.csv) |
| 팀 문서 인용 | "팀 정리 §n" = 팀공유_데이터분석_정리.md, "추적표 §n" = 추적표_9건 1.md |

이 문서의 뼈대는 기획서 검토(STEP 6 §2)가 "기술 설계서 대상"으로 넘긴 여덟 묶음이다: LLM 호출, 검색, 규칙, 흐름, 저장, 마스킹, 화면, 작업. 각 절은 관련 FR 번호를 달아 기능 명세서와 연결하고, 끝의 §12 추적표에서 FR마다 어느 기술 요소가 맡는지 한 번에 볼 수 있다.

**확정과 가정의 구분.** 기술 스택은 기획서 v1.4 7-4에서 확정됐다(FastAPI + LangGraph + PostgreSQL 16 + pgvector + React, 언어 모델·임베딩은 Gemini, 실행은 Docker Compose). 아직 정하지 않은 것은 Gemini 안의 모델 이름과 임베딩 차원처럼 더 작은 항목이다.

**결정 번호 읽는 법.** "D8"처럼 번호만 쓴 것은 기획서 v1.4 부록 A와 기능 요구사항 명세서 v1.3의 결정(D1~D29)이다. 이 문서의 결정은 **T번호**로 쓴다(T24~T42). v1.0에서는 이 문서의 결정도 D24~D37로 썼는데, 명세서 v1.1 이후 D24~D29가 새로 생겨 번호가 겹치므로 바꿨다. 번호는 그대로 두고 앞글자만 바꿨으니 v1.0의 "D25"는 이 문서의 "T25"다(테이블 정의서 v1.1의 "기술 명세서 D25"도 같은 것). 결정 전에는 각 항목의 "결정 전 진행 방식"으로 만든다. 표에 "(제안)"이 붙은 수치는 팀이 바꿀 수 있는 시작값이다.

---

## 0. 용어 (개발 경험이 없는 팀원용)

| 용어 | 뜻 |
|---|---|
| API | 화면(React)이 서버(FastAPI)에 일을 시키는 창구. "주소 + 보내는 값 + 돌려받는 값"의 약속이다. 예: `POST /tickets`는 "티켓을 새로 만들어 줘" |
| 파이프라인 | 문의 한 건이 접수부터 초안까지 거치는 단계의 묶음. 이 프로젝트는 하위 문의(복합이면 나눈 문의)마다 하나씩 돈다 |
| 노드 | 파이프라인의 한 단계. 예: "우선순위 계산 노드" |
| 상태 객체(TicketState / SubTicketState) | 파이프라인의 노드들이 돌려 쓰는 공용 메모지. 앞 노드가 적은 값(유형, 우선순위 …)을 뒤 노드가 읽는다 |
| 티켓(ticket) / 하위 문의(sub_ticket) | 티켓은 고객이 한 번 보낸 접수 1건. 하위 문의는 그 안의 요청 1개로, 단일 문의도 하위 문의 1개짜리 티켓이다. 유형·우선순위·부서·기한·상태는 하위 문의마다 따로 있다(D16·D17, 분리안) |
| LangGraph | 노드와 노드 사이의 화살표(분기 포함)를 그림처럼 정의해 실행해 주는 Python 라이브러리 |
| 구조화 출력 | LLM이 자유 문장 대신 정해진 칸(JSON)에 정해진 코드값만 채워 답하게 하는 방식 |
| 임베딩 / 벡터 검색 | 글을 "뜻이 비슷하면 가까운 숫자 묶음"(벡터)으로 바꿔 두고, 질문과 가장 가까운 글을 찾는 방식 |
| pgvector | PostgreSQL 안에 벡터를 저장하고 검색하게 해 주는 확장 기능 |
| 청크(chunk) | 검색 단위로 자른 문서 조각. 이 프로젝트에서는 문서의 절(`##`, `###`) 하나 |
| 뷰(view) / SQL 함수 | 값을 저장하지 않고 볼 때마다 다시 계산하는 가상의 표 / 계산식 |
| 스케줄러(주기 작업) | 정해진 간격(5분)마다 자동으로 도는 작업. SLA 경고, 회신 리마인드, 무응답 종료에 쓴다 |
| 스키마(schema) | DB 안의 칸막이 공간. 같은 DB 안에서 표 묶음을 서로 섞이지 않게 나눈다 |
| 1차 응답 | 접수 뒤 고객에게 처음 보내는 답변 또는 추가정보 요청(README 용어). 접수 확인 안내는 포함하지 않고(D21), 시스템이 자동 발송한 것은 포함한다 |
| 자동 발송 | 사양(TECH_SPEC)·매뉴얼(MANUAL)·인증(COMPLIANCE) 문의의 정보 요청·답변 초안이 합격 조건 4개를 모두 통과하면 사람 승인 없이 발송하는 것(FR-041, D24). 규칙으로만 판정하고 LLM은 쓰지 않는다 |
| 대역(gloss) | 고객 언어 초안 옆에 나란히 보여 주는 한국어(또는 영어) 번역(FR-039). 참고용이며 발송 본문이 아니다 |
| 이관 | 상담원이 하위 문의를 전문 부서로 넘기는 것(FR-033). 상태가 ESCALATED가 되고 이관 부서 접수함에도 보인다 |
| 스냅샷 | 정답지의 "지금" = 2026-09-30 23:59 UTC. 정답지와 비교할 때만 이 시각으로 고정한다 |

---

## 1. 시스템 구성

### 1-1. 전체 구조

```
[React 화면 4개]  접수 시뮬레이터 / 접수함 / 티켓 상세 / 운영 대시보드
        │  HTTP API (JSON, OpenAPI 문서 자동 생성)
[FastAPI 서버 (Python 한 프로세스)]
   ├─ 처리 흐름 실행기 (LangGraph): 티켓 그래프 1개 + 하위 문의 그래프 n개(병렬, 상한 없음)
   ├─ LLM 호출 계층: 호출 7종(§3), 재시도·시간 상한·마스킹·사용량 기록을 한곳에서
   ├─ 규칙 엔진: 표 조회만, LLM 없음(§5) — 우선순위·부서·필수정보·SLA 목표·이관 후보·자동 발송 판정
   ├─ 검색·진단: 문서 절 검색(§4-4), 숫자 표 조회(§5-5), 고장 사전 조회·증상 검색(§4-6)
   ├─ 저장 계층: 모든 쓰기가 마스킹 검사를 거친다(§7). 상태 전이 함수 하나로만 상태를 바꾼다(§6-4)
   └─ 스케줄러(5분): SLA 경고 · 126시간 회신 리마인드 · 168시간 무응답 종료 · 해결 뒤 168시간 종료(§6-4)
[PostgreSQL 16 + pgvector]
   ref 스키마     기준정보·규칙표 23개(ref/ CSV 12개 적재) + 문서 목록(document) + 문서 청크(doc_chunk)
   svc 스키마     ticket · sub_ticket · 이력 표 5개(메시지·상태 이력·우선순위 조정·경고·근거) · 실행 로그 (ERD_ticket_sub_ticket_v1; + agent_feedback, 추가 개발)
   gold 스키마    tickets.csv 4,000건 · resolution_cases.csv 800건 원본(읽기 전용, 채점·불러오기용)
   scoring 스키마 채점 배치 전용(svc와 같은 모양, 실행마다 비움)
   eval 스키마    평가 결과(채점 제외 목록·실행·점수·행별 결과, 추가 개발 FR-042·044)
[외부] Gemini 언어 모델 API, Gemini 임베딩 API (D8). 그 밖의 외부 연동 없음
```

읽는 법(범례): 위 상자 중 LLM을 부르는 것은 "LLM 호출 계층"뿐이다. 규칙 엔진·검색·진단·저장·스케줄러는 코드와 SQL만 쓴다. 사람이 개입하는 곳은 화면 4개(승인·발송, 우선순위 조정, 이관 확정, 고객·부서 회신 대리 입력)다. 기획서 v1.4 7-5의 그림과 같은 구조이며, 그 그림의 "규칙 엔진"에 자동 발송 판정과 이관 후보가, "검색"에 고장 사전이, "언어 모델 호출 계층"에 대역 번역이 들어 있다.

- 화면은 서버 API만 부르고, 서버만 DB와 외부 API에 접근한다.
- 정답지(gold)는 서비스가 읽지 않는다. 시연용 불러오기(train 행 입력 열만)와 채점만 쓴다.
- 복합 문의는 하위 문의 n개로 나누고 하위 문의 그래프 n개를 동시에 돌린다. 하위 문의마다 상태·기한·담당 부서를 따로 가지며, 준비된 하위 문의부터 발송한다(기획서 5-3, D15·D16).

### 1-2. 기술 스택 (기획서 v1.4 7-4에서 확정)

| 층 | 선택 | 이 프로젝트에서 쓰는 이유 | 남은 결정 |
|---|---|---|---|
| 서버 | Python 3.11 + FastAPI + Pydantic v2 | 상태 객체를 Pydantic 모델로 두면 파이프라인 입출력·API 응답·로그가 같은 모양이 된다. OpenAPI 문서가 자동으로 나와 화면 쪽 타입을 생성할 수 있다 | — |
| 처리 흐름 | LangGraph | 분기 8개와 하위 문의별 병렬 실행을 그래프로 표현하고, 노드마다 실행 로그를 남기기 쉽다 | — |
| DB | PostgreSQL 16 + pgvector | 규칙표, 티켓, SLA 계산, 벡터 검색을 한 DB에서 조인한다. SLA 판정식은 이 DB에서 정답지 4,000건과 상태 4,000/4,000, 경과 3,997/4,000 일치를 확인했다(3건은 고객 대기 시간 음수, D19). 테이블 정의서 v1.1은 상태 전이·자동 발송·리마인드·이관·168시간 종료를 DB 제약으로 막는 것까지 확인했다 | — |
| 화면 | React + Vite + TypeScript, TanStack Query·Table | 티켓 상세의 세 칸 + 이력 띠(FR-030)와 대시보드 집계(FR-034)를 자유롭게 배치 | — |
| 언어 모델·임베딩 | Gemini (D8 확정) | 15개 언어 품질과 비용 기준으로 선택(기획서 7-4). 호출부는 LLM 호출 계층 한 곳에 둔다 | T38: 소형·상위 모델 이름, 임베딩 모델 이름과 차원 |
| 실행 환경 | Docker Compose: db(postgres+pgvector), api, web | 4명이 같은 명령으로 실행 | — |

### 1-3. 설계 원칙 (팀 정리 §3의 8개를 기술 규칙으로)

| 팀 정리 §3 원칙 | 이 문서에서 지키는 방법 |
|---|---|
| 1 고객 언어로 답변 | 초안·정보 요청·진행 안내 호출(L3~L6)의 출력 언어 = language. 본문 해석은 body_language(§3). 상담원용 대역(L7)은 별도 값으로 두고 발송 본문에 넣지 않는다 |
| 2 우선순위·라우팅·SLA는 규칙표, LLM은 읽기·쓰기만 | 규칙 노드(§5)는 LLM 호출 계층을 import하지 않는다. 자동 발송 판정(§5-7)과 이관 후보(§5-6)도 규칙이다. 코드 리뷰 체크 항목으로 둔다 |
| 3 답변은 문서 근거만 | 초안은 근거 후보 절과 조회값만 입력으로 받고, 생성 뒤 자체 대조(§3-4)로 인용·숫자를 검사. 고장 진단 후보(§4-6)와 유사 사례는 초안 입력에 넣지 않는다(FR-018 처리 5번) |
| 4 펌웨어는 release_date ≤ 접수일 | 숫자 조회의 SQL 조건으로 고정(§5-5) |
| 5 결함 진단 없으면 유사 사례 검색 생략 | 고장 진단(FR-018)은 MVP이며 DEFECT·INSTALL·WARRANTY 하위 문의에서만 돈다(§4-6). 유사 사례 검색(FR-019)은 추가 개발이며 진단 유형 5종에서만 켠다(§4-7) |
| 6 상담원 우선순위 조정(사유 필수) | `priority_adjustment` 표 + 조정 API(§6, §8) |
| 7 사람 승인·발송 | 고객에게 나가는 글은 `message_status = DRAFT`로만 생성한다. SENT 행은 승인 API(상담원)와 자동 발송 판정기(시스템, FR-041·D24)만 쓴다. 회신 리마인드(D29)는 고정 문안이라 판정 없이 스케줄러가 보낸다(§6-4) |
| 8 가격·납기는 제품 마스터 조회 | 숫자 조회(§5-5)와 숫자 자체 대조(§3-4). 견적 초안에는 "정확한 견적은 영업 담당이 별도 안내" 문장을 넣는다(D14) |

### 1-4. 비기능 요구사항과 구조의 대응 (기획서 v1.4 5-5)

| 기획서 5-5 | 어디서 지키나 |
|---|---|
| 성능: 호출 1회 30초, 하위 문의 120초, 티켓 180초 | LLM 호출 계층의 시간 상한과 그래프 실행기의 상한(§2-4, T30) |
| 성능: 점검 주기 5분 | 스케줄러(§6-4) |
| 안정성: 1회 재시도 뒤 사람에게, 한 하위 문의 실패해도 나머지 계속 | LLM 호출 계층의 재시도, T3 병렬 실행의 실패 격리(§2-2) |
| 안정성: 다시 처리는 새 실행, 발송한 글은 지우지 않음 | agent_run 새 행(§6-5), SENT 행 수정 금지 트리거(§6-3) |
| 개인정보: 저장 전·LLM 호출 전 가림 | 저장 계층의 `mask_text` 한 함수(§7) |
| 기록: 단계별 입력·출력 요약, 오류, 시간, 사용량 | 노드 감싸기 함수 → agent_step(§6-5) |
| 품질: 인용·숫자 코드 대조, 확신도 0.6 미만 표시 | 자체 대조(§3-4), 확신도 기준(§3-6, T26) |
| 데이터 분리: valid·test는 서비스 DB·색인에 넣지 않음, 제목은 입력에서 뺌 | gold 격리와 `v_train_inputs` 뷰(§6-1), TicketState에 제목 없음(§2-3) |

### 1-5. 실행·배포 구성 (작업 W7)

| 항목 | 내용 |
|---|---|
| 컨테이너 | `db`(postgres:16 + pgvector), `api`(FastAPI, 스케줄러 포함), `web`(React 정적 파일) 3개 |
| 포트(제안) | web 5173(개발) / 80(빌드본), api 8000(`/docs`에 OpenAPI), db 5432 |
| 환경 변수(`.env.example`) | `GEMINI_API_KEY`, `LLM_MODEL_SMALL`, `LLM_MODEL_LARGE`, `EMBEDDING_MODEL`(T38), `DATABASE_URL`, `LOG_FULL_LLM_IO`(기본 false), `LLM_MAX_CONCURRENCY`(기본 4), `SCHEDULER_INTERVAL_SEC`(기본 300) |
| 초기화 순서(명령 하나로) | DB 생성 SQL 00→07(테이블 정의서 v1.1 §1-1) → W1 기준정보 적재 → W3 정답지 적재 → W2 문서 색인 → W5·W6 시연 데이터 |
| 완료 확인 | 새 노트북에서 README 순서대로 실행해 화면 4개가 뜨고 추적표 9건 재현 스크립트가 통과(기획서 10-3) |

---

## 2. 처리 흐름 (FR-001, 004~008, 010~018, 020~023, 036, 039, 041)

### 2-1. 두 겹 그래프

복합 문의(FR-006)를 하위 문의별로 병렬 처리하기 위해 그래프를 둘로 나눈다.

```
[티켓 그래프]  (티켓 1건에 1번)
  T1 마스킹·입력 고정 → T2 문의 이해(L1: 언어·분리·유형·긴급도) → T3 하위 문의 그래프 n개 병렬 실행(상한 없음)
  → T4 결과 모으기 → T6 상태 NEW→IN_PROGRESS + 진행 안내 초안(FR-023 ①)
  (T5 답변 구성은 하위 문의 그래프가 초안을 낼 때마다 따로 돈다. 아래 §2-5 참고)

[하위 문의 그래프]  (나눈 문의 1개에 1번, seq = 1..n)
  Q1 제공 항목 추출(L2, FR-008) → Q2 고객·제품 조회(FR-010)
  → Q3 우선순위(FR-011) → Q4 부서(FR-012) → Q5 필수정보(FR-013) → Q6 SLA 목표(FR-014)
  → Q8a 고장 진단(FR-018, DEFECT·INSTALL·WARRANTY만) → Q9a 이관 후보(FR-020)
  → 분기③ 막는 정보 있음? ─ 예 → Q7 정보 요청 문안(L3, FR-015) → Q12 자동 발송 판정(FR-041) → Q13 대역(L7, FR-039) → 끝
                          └ 아니오 → Q8 문서 절 검색(FR-016) → Q9 숫자 표 조회(FR-017)
                                     → 분기④ 근거 있음? ─ 아니오 → "근거 없음" 표시 → 끝
                                                       └ 예 → Q10 답변 초안(L4, FR-021) → Q11 자체 대조
                                                              → T5 답변 메일 구성(FR-022) → Q12 자동 발송 판정 → Q13 대역 → 끝
```

- 긴급도(FR-007)는 FR-005와 같은 호출(L1)에서 하위 문의마다 받는다. 그래서 하위 문의 그래프에는 긴급도 노드가 따로 없다(FR-005·006·007이 "같은 호출로 묶어도 된다"고 허용, T24).
- 단일 문의는 n = 1인 경우일 뿐 같은 그래프를 탄다. 따로 분기하지 않는다. 하위 문의 행(sub_ticket)도 1개 만든다(분리안 K4).
- 고장 진단(Q8a)과 이관 후보(Q9a)는 정보 요청 여부와 상관없이 규칙 단계 바로 뒤에 돈다. 진단 후보는 상담원 참고용이고 초안 입력에 들어가지 않으므로(FR-018 처리 5번) 분기③ 앞에 두어도 초안에 영향이 없다.
- 단계 순서는 고정한다. LLM이 다음 도구를 고르는 방식(에이전트가 도구를 스스로 선택)은 쓰지 않는다. 이유: 규칙 순서(고객→제품→종류/긴급도→우선순위→부서→필수정보→답변근거→SLA→결과)가 규칙표의 열쇠 때문에 강제되고(추적표 §1), 실행 로그와 채점이 단계 단위로 비교되어야 한다.

### 2-2. 노드 목록

| 노드 | FR | 종류 | 입력(상태 객체에서 읽음) | 출력(상태 객체에 씀) | 실패 시 |
|---|---|---|---|---|---|
| T1 입력 고정 | 001, 038 | 코드 | 접수 입력 | 마스킹된 본문, 마스킹 수 | 저장 거부(§7) |
| T2 문의 이해 | 004~007 | LLM L1 | 본문, language, channel, product_family | body_language, sub_tickets[] (seq, category_code, 확신도, 근거 문장, urgency_flag, 영어 검색문) | 1회 재시도 → 티켓 NEW 유지, run FAILED, "다시 시도" |
| T3 병렬 실행 | 006 | 실행기 | sub_tickets[] | 하위 문의별 결과 | 실패한 하위 문의만 표시(pipeline_error), 나머지 계속 |
| Q1 추출 | 008 | LLM L2 | 그 하위 문의의 근거 문장 + 원문, 필수 항목 목록 | provided_fields[], product_code 보완, error_code, current_fw, return_reason(영어 정규화) | 빈 목록 + "추출 실패", 계속 |
| Q2 고객·제품 | 010 | 표 조회 | customer_id, product_code | tier, segment, country, family, 제품 값 | 고객 없음 → 접수 거부(D25) / 제품 없음 → Q4·Q5 "제품 확인 필요" |
| Q3 우선순위 | 011 | 규칙 | category_code, urgency_flag | priority_rule, rule_id, 판정 과정 | 행 없음 → 비움 |
| Q4 부서 | 012 | 규칙 | family, category_code, return_reason | assigned_dept, routing_rule_id, 이관 조건, 반품 구분 | 행 없음 → 비움 + GCS_L1 표시 |
| Q5 필수정보 | 013 | 규칙 | family, category_code, provided_fields | missing_info, missing_blocking_info | 제품·유형 없음 → 실행 안 함 |
| Q6 SLA 목표 | 014 | 규칙 | category_code, tier, priority(최종) | sla_id, 두 목표 시간 | 비움, "SLA 미정" |
| Q8a 고장 진단 | 018 | 표 조회 + 증상 검색 | family, error_code, 근거 문장 | fault_candidates[] (원인, 조치, 현장 출동·교체 필요, 출처, 찾은 방법, 점수) | 진단 없음 + "진단 실패", 계속 |
| Q9a 이관 후보 | 020 | 규칙 | urgency_flag, fault_candidates[0], 이관 조건 | escalation_candidates[] (rule_id, 부서, 이유) | 후보 없음 + 이관 조건 문구만 |
| Q7 정보 요청 | 015 | LLM L3 | 막는·빠진 항목 + 라벨, language, channel | INFO_REQUEST DRAFT 1건 | 영어 고정 문구 |
| Q8 문서 검색 | 016 | 검색 | 영어 검색문, 원문 문장, 유형, product_code, family, error_code, current_fw | 근거 후보 ≤ k개 | 1회 재시도 → "검색 실패", 근거 없음 |
| Q9 숫자 조회 | 017 | 표 조회 | product_code, 유형, received_at, quantity, current_fw | 조회값 묶음 + 출처 | 값 비움 + "표에 없음" |
| Q10 초안 | 021 | LLM L4 | 근거 후보, 조회값, language, 유형 뼈대 | 초안 단락, 인용 | 1회 재시도 → 초안 없음 |
| Q11 자체 대조 | 021 | 코드 | 초안, 근거 후보, 조회값 | 대조 결과, 불일치 위치 | 1회 재생성 → 불일치 강조 |
| T5 답변 메일 구성 | 022 | 코드 + LLM L5 | 준비된 하위 문의의 단락, 모든 하위 문의 상태 | FINAL_REPLY DRAFT 1건(단락 + 문의 상태 목록, seq 포함) | 템플릿 인사말로 대체, 상태 목록 줄 수 검사 |
| Q12 자동 발송 판정 | 041 | 규칙 | 초안 종류, category_code, urgency_flag, 막는 항목, 대조 결과, 표시 목록 | 자동 발송(SENT, SYSTEM) 또는 auto_send_hold 사유 | 판정 오류 → 보류 + 상담원 승인 |
| Q13 대역 | 039 | LLM L7 | 초안 본문, language, 대역 언어 | message_gloss 행(language, body, made_at) | 대역 없음 + [다시 만들기], 승인은 막지 않음 |
| T6 진행 안내 | 023, 025 | 코드 + LLM L6 | 전이 사건 ①~④ | PROGRESS_NOTICE DRAFT (+ 대역) | 영어 고정 문구 |

리마인드(FR-023 ⑤)는 노드가 아니라 스케줄러가 만든다(§6-4). 이관(FR-033)과 고객·부서 회신(FR-032·033)은 API가 상태를 바꾸고 필요한 노드부터 다시 돌린다(§2-4 부분 재실행).

### 2-3. 상태 객체 (T32: TicketState 필드 확정)

LangGraph 노드끼리 넘기는 값이다. DB 표(§6)와 이름을 맞춘다. 아래는 결정 전 진행 방식의 필드 목록이다.

```python
class SubTicketState(BaseModel):        # 하위 문의 그래프 1개의 메모지 (DB: svc.sub_ticket)
    sub_ticket_id: str                   # f"{ticket_id}-{seq}" (분리안 K1)
    ticket_id: str
    seq: int                             # 1..n, 본문에 나온 순서. 상한 없음(D18)
    category_code: str | None            # 10종 또는 None(분류 실패)
    category_confidence: float | None
    evidence_sentences: list[str]        # 이 하위 문의의 근거 문장(본문 발췌)
    query_en: str | None                 # 검색용 영어 요약(§4-3)
    urgency_flag: str                    # 6값, 실패 시 NONE
    urgency_evidence: str | None
    provided_fields: list[ProvidedField] # {field, value_raw, value_norm, span}
    product_code: str | None; product_family: str | None
    customer_tier: str
    error_code: str | None; current_fw: str | None; return_reason: str | None
    return_kind: Literal["DEFECT", "NON_DEFECT", "UNKNOWN"] | None
    priority_rule: str | None; priority_rule_id: str | None; priority_trace: list[RuleCheck]
    priority_final: str | None           # 조정값이 있으면 조정값
    assigned_dept: str | None; routing_rule_id: str | None; escalation_condition: str | None
    missing_info: list[str]; missing_blocking_info: list[str]
    sla_id: str | None; fr_target_h: int | None; res_target_h: int | None
    fault_candidates: list[FaultCandidate]       # {fault_id, cause, action, onsite_required, replace_required, method, score}
    escalation_candidates: list[EscalationHint]  # {rule_id, dept, reason}
    doc_candidates: list[DocCandidate]   # {chunk_id, doc_id, section_no, title, score}. 저장은 sub_ticket.evidence_json(§4-4 4번)
    lookups: list[LookupValue]           # {item, value, unit, source_table, source_key}
    draft_id: int | None; draft_check: DraftCheck | None
    auto_send: AutoSendResult | None     # {eligible, passed, hold_reasons[]}
    flags: list[str]                     # "확신 낮음", "반품 사유 확인 필요", "근거 없음", "제품 미확정" … 그래프 안에서만 쓰고, 저장은 self_check 행으로(§6-2)
    pipeline_error: str | None

class TicketState(BaseModel):            # 티켓 그래프의 메모지 (DB: svc.ticket)
    ticket_id: str; channel: str; customer_id: str; language: str
    body_language: str | None; body_language_uncertain: bool
    body_masked: str; received_at: datetime
    sub_tickets: list[SubTicketState]    # n ≥ 1, 상한 없음(D18)
    multi_yn: bool                       # n ≥ 2
    run_id: int
```

제목(inquiry_subject)은 TicketState에 넣지 않는다. 그래서 어떤 노드도 제목을 읽을 수 없다(팀 정리 §6 제목 누설, AC-001-3). v1.0의 `split_check_needed`(4개 이상 표시)는 상한이 없어져 뺐다(D18).

### 2-4. 실행 방식, 시간 상한, 동시 실행 (T30)

| 항목 | 결정 전 진행 방식 (제안) | 근거 |
|---|---|---|
| 실행 시작 | `POST /tickets`가 티켓·하위 문의(이해 전에는 seq 1 하나)·INQUIRY 메시지·상태 이력을 한 트랜잭션으로 저장하고 즉시 ticket_id를 돌려준다. 파이프라인은 서버 안의 백그라운드 작업으로 돈다 | 화면이 "처리 중"을 보여 주고(FR-001 6번) 결과를 다시 읽는다 |
| 화면 갱신 | 티켓 상세가 처리 중이면 2초마다 `GET /tickets/{id}`를 다시 읽는다. 끝나면 멈춘다 | 별도 실시간 연결(WebSocket) 없이 단순하게 |
| LLM 호출 1회 시간 상한 | 30초 | 기획서 5-5. 넘으면 LLM_TIMEOUT, 1회 재시도 |
| 하위 문의 그래프 1개 시간 상한 | 120초 | 기획서 5-5. 넘으면 그 하위 문의만 실패, 상태 목록에는 "담당자 확인 중"(FR-022 예외) |
| 티켓 전체 시간 상한 | 180초 | 기획서 5-5. 넘으면 run FAILED, 티켓 NEW 유지 |
| 한 티켓 안 병렬 수 | 상한 없음(D18). 실제 동시 실행은 아래 서버 전체 동시 호출 수로 제한된다 | 데이터에서는 한 문의에 최대 2개 |
| 서버 전체 LLM 동시 호출 수 | 4 | Gemini 요금 한도·속도 제한 보호. 채점 배치는 별도 설정 |
| 대역(L7) 호출 | 초안 1건당 1회가 더 든다. 시간 상한에는 넣지 않는다(초안이 끝난 뒤 뒤따라 돌고, 없어도 승인 가능) | FR-039 |
| 재처리 | "다시 시도/다시 처리"는 새 run을 만든다. 이미 SENT인 메시지는 지우지 않고, 이전 DRAFT는 `superseded_at`으로 표시한다. 횟수 제한 없음 | FR-036 5번 |
| 부분 재실행 | 상담원이 유형·긴급도·제품을 고치면 그 하위 문의의 Q2부터, 제공 항목을 고치면 Q5부터, 반품 구분을 고르면 Q4부터 다시 돈다 | FR-010 AC-010-3, FR-013 5번, FR-030 6번, §5-3 |
| 고객 회신 재처리 | 대상 하위 문의의 Q1(원문 + 모든 회신)부터 다시 돈다. 제공 항목은 이전 값과 합집합. 회신으로 막는 항목이 없어지면 Q8부터 초안까지 간다 | FR-032 3·4번 |
| 전문 부서 회신 | 상태만 ESCALATED → IN_PROGRESS로 바꾸고 그래프는 다시 돌리지 않는다. 회신 본문은 티켓 상세에 상담원 참고로 보인다 | FR-033 처리 8번 |

### 2-5. 분기 8개의 구현 위치

| 분기 | 조건 | 구현 |
|---|---|---|
| ① 문의 나누기 | sub_tickets 수 ≥ 2 | T3이 하위 문의 그래프를 n개 띄움. 상한 없음(D18) |
| ② 반품 사유 | category = RETURN이고 return_kind = NON_DEFECT | Q4의 규칙 조회 키를 RT-ALL-RETURN-NON_DEFECT로 바꿈(§5-3) |
| ③ 막는 정보 | missing_blocking_info ≠ [] | Q9a 뒤 조건 화살표 → Q7 |
| ④ 근거 유무 | doc_candidates = [] 또는 모두 기준 점수 미만(T27) | Q9 뒤 조건 화살표 → 끝("근거 없음") |
| ⑤ 유형별 뼈대 | category_code 10종 | Q8의 우선 문서 종류표(§4-4), Q10의 뼈대 템플릿(§3-3) |
| ⑥ 고객 회신 | 회신 뒤 막는 항목이 남음 / 없음 | FR-032 재처리가 같은 하위 문의 그래프를 다시 태우므로 ③이 그대로 판단 |
| ⑦ 고장 계열 | category ∈ {DEFECT, INSTALL, WARRANTY} | Q8a 실행 여부(§4-6). 아니면 건너뜀(AC-018-3) |
| ⑧ 자동 발송 | 초안 종류 ∈ {INFO_REQUEST, FINAL_REPLY}이고 category ∈ {TECH_SPEC, MANUAL, COMPLIANCE} | Q12(§5-7). 대상이 아니거나 조건 하나라도 어긋나면 DRAFT로 두고 보류 사유 기록 |

**복합 문의의 답변 구성(FR-022, D15).** 하위 문의의 초안(Q11까지)이 준비되는 즉시 T5가 그 하위 문의의 답변 메일 초안을 만든다. 다른 하위 문의를 기다리지 않는다. 같은 때에 둘 이상이 준비되고 담당 부서가 같으면 한 메일에 묶을 수 있다. 메일 끝에는 모든 하위 문의의 현재 상태를 고객 언어로 적은 "문의 상태 목록"을 붙인다(상태 문구는 15개 언어 고정 문안 템플릿, T40). 정보 요청으로 간 하위 문의는 자기 정보 요청을 따로 보낸다. 발송되면 그 메일이 답한 하위 문의만 RESOLVED가 된다.

---

## 3. LLM 호출 (FR-004~008, 015, 021~023, 039)

### 3-1. 호출 목록

| 호출 | FR | 한 티켓에서 | 입력 | 출력 언어 | 모델 등급 (Gemini, 이름은 T38) |
|---|---|---|---|---|---|
| L1 문의 이해 | 004·005·006·007 | 1회 | 마스킹된 본문, channel, language, product_family(있으면), 유형 10종 정의(README §6), 긴급도 6값 설명(urgency_codebook.csv) | 코드값 + 원문 발췌 + 영어 검색문 | 소형 |
| L2 제공 항목 추출 | 008 | 하위 문의마다 1회 | 원문 + 그 하위 문의 근거 문장, 항목 코드북 32개(info_field_codebook.csv), 그 제품군×유형의 필수 항목(required_info.csv) | 값(원문 그대로) + 정규화 값 | 소형 |
| L3 정보 요청 문안 | 015 | 막는 정보가 있는 하위 문의마다 1회 | 항목 이름 + 라벨, 제품명, 유형, channel, language | language | 상위 |
| L4 답변 초안 | 021 | 근거가 있는 하위 문의마다 1회 | 근거 절 본문, 조회값, 유형 뼈대, 제공 항목, language, 모드(완성문/단락) | language | 상위 |
| L5 메일 인사말·맺음말 | 022 | 복합 문의의 답변 메일마다 1회 | 티켓 요약, language | language | 소형 |
| L6 진행 안내 | 023 | 전이 ①②③④마다 1회 | 전이 종류, 부서 이름, 다음 단계, language | language | 소형 |
| L7 대역 번역 | 039 | DRAFT 초안마다 1회(정보 요청·답변·진행 안내), 임시 저장 뒤 다시 1회 | 초안 본문, language, 대역 언어(기본 ko, 화면에서 en) | ko 또는 en | 소형 |

회신 리마인드(FR-023 ⑤)는 LLM을 쓰지 않는다. 고객 언어 고정 문안 템플릿 + 빠진 항목 라벨로 스케줄러가 만든다(§6-4).

T24(호출 묶음): FR-004~007을 L1 한 번으로 묶는 것을 결정 전 진행 방식으로 한다. 이유는 비용(티켓당 1회)과 일관성(유형과 긴급도를 같은 읽기에서 판단)이다. valid 603건에서 유형 일치율이 95%(D9)에 못 미치면 긴급도를 별도 호출로 떼어 비교한다.

### 3-2. 구조화 출력 스키마

모든 호출은 JSON 스키마를 강제한다(구조화 출력). 코드값 칸은 열거형(enum)으로 막아 10종·6값·15개 언어 밖의 값이 나오지 않게 한다. 스키마 검증에 실패하면 LLM_INVALID_OUTPUT으로 1회 재요청한다.

**L1 문의 이해 출력** (T35: 분류 출력 스키마 확정)

```json
{
  "body_language": "ar",
  "body_language_confidence": 0.97,
  "sub_tickets": [
    {
      "seq": 1,
      "category_code": "FW_UPDATE",
      "category_confidence": 0.93,
      "evidence_sentences": ["… 3.50 으로 업데이트 …"],
      "urgency_flag": "NONE",
      "urgency_evidence": null,
      "query_en": "Customer on BMS firmware 3.40 asks how to update to 3.50"
    },
    { "seq": 2, "category_code": "MANUAL", "...": "..." }
  ]
}
```

- `category_code` 열거: TECH_SPEC, INSTALL, DEFECT, FW_UPDATE, MANUAL, COMPLIANCE, QUOTE, ORDER_LEAD, RETURN, WARRANTY. `urgency_flag` 열거: urgency_codebook.csv 6값. `body_language` 열거: 15개 언어 코드.
- 같은 유형이 두 번 나오면 코드에서 하나로 합치고 근거 문장을 이어 붙인다(FR-006 처리 2번).
- 유형은 `sub_ticket.category_code`(하위 문의마다 1개)에만 저장한다. 티켓에 ';'로 이은 문자열은 두지 않는다(분리안 K3, 2026-10-14 확정). 정답지의 `category_code;secondary_category`와 비교할 때(AC-006-4)는 조회 시 `string_agg`로 이어 붙인다. secondary_category 칸은 두지 않는다.
- 긴급도가 둘 이상 해당하면 SAFETY > SITE_DOWN > PROD_IMPACT > COMMISSION > DEADLINE 순으로 고르라고 지시하고, 코드에서도 같은 순서로 한 번 더 확인한다(FR-007 처리 3번).

**L2 추출 출력**

```json
{
  "fields": [
    {"field": "product_model", "value_raw": "HMI-XGT-eXP60", "value_norm": "HMI-XGT-eXP60", "span": [41, 54]},
    {"field": "current_fw", "value_raw": "v3.40", "value_norm": "3.40", "span": [88, 93]},
    {"field": "return_reason", "value_raw": "Nous avons reçu un autre modèle", "value_norm": "received a different model from what was ordered", "span": [120, 152]}
  ]
}
```

- `field`는 코드북 32개 열거. 밖이면 그 항목만 버린다.
- `value_norm` 규칙(코드에서 다시 적용): 펌웨어 버전은 숫자와 점만(TEXT로 보존, "3.10"을 3.1로 바꾸지 않음), 제품 코드는 product_master.csv와 대조해 표기 통일, 날짜는 YYYY-MM-DD, 수량은 정수. return_reason만 `value_norm`을 영어 문장으로 받는다(반품 단어 규칙이 영어 목록이므로, §5-3).
- `span`은 마스킹된 본문 기준 글자 위치. 화면 강조(FR-030 1번)에 쓴다.
- 주의: 정답지 provided_info 열에는 항목 이름만 있고 값은 없다(예: "purchase_doc;serial_no;return_reason;photos"). 그래서 L2의 채점은 항목 이름 집합으로만 한다(AC-008-5).

**L7 대역 출력**: `{"gloss": "..."}` 한 칸. 인용 표시 `(DOC_ID §n.m)`과 숫자는 원문 그대로 두라고 지시하고, 코드에서 원문의 인용·숫자 집합과 대역의 집합이 같은지 확인한다. 다르면 1회 재요청, 그래도 다르면 대역은 보여 주되 "인용·숫자 확인" 표시를 붙인다.

### 3-3. 프롬프트 구성 원칙

프롬프트 파일은 저장소의 `prompts/` 폴더에 호출별로 두고 파일 이름에 버전을 붙인다(예: `l4_draft_v3.md`). 실행 로그에 프롬프트 버전을 남긴다(§6-5).

| 원칙 | 적용 |
|---|---|
| 규칙표의 정의를 그대로 넣는다 | L1에 README §6 유형 정의와 urgency_codebook.csv 설명 원문을 넣는다. 팀이 지어낸 정의를 쓰지 않는다 |
| 제목·정답 열은 넣지 않는다 | L1~L7 입력 목록에 inquiry_subject, 정답 열이 없다. 실행 로그에 입력 항목 이름 목록을 남겨 확인한다(AC-001-3) |
| few-shot(예시)은 train만 | 예시가 필요하면 train 행에서만 고른다. valid·test 행 문장은 프롬프트에 넣지 않는다. 자동 선택(FR-046, 추가 개발)이 들어와도 출처는 train + 사람이 채택한 상담원 기록뿐이다(D27) |
| 근거 밖 금지 | L4: "아래 절 본문과 조회값만 사실로 쓴다 / 숫자는 조회값만 / 문장 끝에 (DOC_ID §절) 인용 / 승인·거절·납기 확정 문구 금지". 고장 진단 후보는 L4 입력에 넣지 않는다(AC-018-4) |
| 약속 금지 | L6: SLA 목표 시간, 예상 완료 시각을 쓰지 않는다(AC-023-3). L3: 추측한 값·기한 약속 금지. 문의 상태 목록(FR-022)도 같은 원칙 |
| 채널별 모양 | L3: CHAT 3문장 이내, PHONE은 고객 언어 + 영어 병기 체크리스트(FR-015 5번) |
| 대역은 바꾸지 않는다 | L7: 뜻만 옮기고 문장을 더하거나 빼지 않는다. 인용·숫자는 원문 그대로 |

**L4 유형별 뼈대 템플릿** (FR-021 4번을 그대로 템플릿 파일로)

| 유형 | 뼈대 | 필수 조회값 | 우선 인용 |
|---|---|---|---|
| QUOTE | 제품·수량·단가·합계·표준 납기·견적 유효기간 + "정확한 견적(수량 할인 등)은 영업 담당이 별도로 안내" 한 문장(D14) | list_price_usd, 합계, std_lead_time_weeks | POL-ORDER |
| ORDER_LEAD | 표준 납기(확정 출하일 금지) | std_lead_time_weeks, moq | POL-ORDER |
| TECH_SPEC, COMPLIANCE | 묻는 사양값 + 출처 절 + 데이터시트 첨부 안내 | product_spec_facts.csv 행 | DS |
| DEFECT, INSTALL | 원인 후보·점검 순서(TG/IG 절에 있는 것만. 고장 사전 후보는 쓰지 않음) | (없음) | TG, IG |
| FW_UPDATE | 현재 버전·접수 시점 최신·업데이트 또는 이미 최신 | firmware_history.csv 비교 결과 | RN |
| RETURN, WARRANTY | 정책 조항·필요 서류·판정은 사람이 한다는 안내 | warranty_months(WARRANTY) | POL-RETURN, POL-WARRANTY |
| MANUAL | 해당 문서 ID와 절 안내 | (없음) | IG, TG, RN, DS, MG |

견적 유효기간(정답지 final_reply의 "30일")은 POL-ORDER §5 "Quotations are valid for 30 days."에 있다. 그래서 QUOTE 초안은 이 절을 근거 후보에 항상 넣고 인용하며, 숫자 자체 대조는 근거 절 본문의 숫자로 30을 허용한다. 같은 절의 "Volume discounts apply"는 할인율이 표에 없으므로 숫자를 쓰지 않는다(D14). 견적은 이관하지 않는다(ESCALATED를 쓰지 않음, D14 2026-10-13).

### 3-4. 자체 대조 (LLM 아님, 코드)

FR-021 5번, FR-022 처리 5번, FR-031 처리 2번, FR-041 합격 조건 ①이 같은 함수를 쓴다.

1. **인용 검사**: 정규식으로 `(DOC_ID §n.m)` 꼴을 모두 찾는다. 각 (doc_id, 절)이 그 하위 문의의 근거 후보에 있어야 한다. 복합 문의 메일은 단락별로 그 하위 문의의 후보와 대조한다.
2. **숫자 검사**: 초안의 숫자(정수, 소수, 천 단위 구분 포함, 언어별 소수점 표기 정규화)를 모두 뽑는다. 허용 목록 = 조회값 + 제공 항목 값(수량, 고객 버전, 날짜) + 인용 절 번호 + 근거 절 본문에 나오는 숫자 + 문의 상태 목록의 문의 번호. 허용 목록 밖 숫자가 있으면 불일치.
3. **누락 검사**: L3은 막는 항목 라벨이 본문에 있는지, T5는 상태 목록 줄 수 = 하위 문의 수인지 본다.
4. 불일치면 1회 재생성. 다시 불일치면 초안은 두고 위치 목록을 `draft_check`에 저장해 화면이 강조한다. 이 상태의 초안은 자동 발송되지 않는다(§5-7).

### 3-5. 모델 선택과 예산 (D8 확정, T38 결정 필요)

| 항목 | 결정 전 진행 방식 |
|---|---|
| 모델 배분 | Gemini 소형 모델 1개(L1·L2·L5·L6·L7), Gemini 상위 모델 1개(L3·L4). 모델 이름은 T38에서 정하고 환경 변수로 바꾼다 |
| 비교 방법 | valid 603건 중 언어별 층화 표본 150건으로 L1 유형·긴급도 일치율, L4는 검수 30건(15개 언어 각 1건 이상, 기획서 10-2)으로 비교 |
| 비용 기록 | 모든 호출의 모델 이름, 입력·출력 토큰을 `agent_step`에 남겨 티켓당 비용을 계산(§6-5). 대역(L7)이 티켓당 호출을 1~3회 늘리므로 따로 집계한다 |
| 대량 실행 | 채점 배치(valid·test 전량)는 Gemini의 일괄 처리(Batch) 기능이 있으면 쓴다 |
| 예산 상한 | 미정. 결정 전에는 실행 로그로 사용량만 집계해 주 1회 팀에 보고 |

### 3-6. 확신도 기준 (T26)

LLM이 스스로 매기는 확신도는 정확하지 않을 수 있어서 기준값은 데이터로 정한다.

- 결정 전 진행 방식: 언어 판정·유형 분류 모두 0.6 미만이면 "확신 낮음"/"언어 판정 불확실" 표시(기획서 5-5).
- 조정 방법: valid 첫 채점 뒤, 확신도 구간별 실제 일치율을 표로 만들어 "이 값 아래에서는 일치율이 90% 미만"인 지점으로 바꾼다.
- "확신 낮음" 표시가 있는 하위 문의의 초안은 자동 발송되지 않는다(FR-041 합격 조건 ③).

---

## 4. 검색과 진단 (FR-016, 018, 019)

### 4-1. 문서 사실 (doc_index.csv와 docs/ 확인 결과)

| 종류 | 문서 수 | 범위 | 비고 |
|---|---|---|---|
| DS 데이터시트 | 23 | 제품별 | 사양 근거 |
| IG 설치·시운전 안내 | 23 | 제품별 | |
| TG 트러블슈팅 | 23 | 제품별 | 고장 근거 |
| RN 릴리스노트 | 13 | 펌웨어 있는 제품만 | |
| MG 정비 안내 | 10 | 일부 제품 | 명세서에는 언급 없음(§13 확인 사항 F-01) |
| POL 정책 | 4 | 전체 | POL-ORDER, POL-RETURN, POL-WARRANTY, POL-SERVICE |
| FAQ | 11 | 제품군별 | 절이 "## Q1." 꼴 |
| 합계 | 107 | | 모두 영어 마크다운. 문서 길이 680~7,221자, 문서당 절 2~22개, 가장 긴 절 1,092자 |

정답지의 근거 문서 종류(tickets.csv reference_doc_id, 4,000건 중 값이 있는 행): TECH_SPEC·COMPLIANCE → DS, DEFECT → TG, INSTALL → IG 302 / TG 148, FW_UPDATE → RN, MANUAL → IG 110 / TG 85 / RN 45 / DS 44 / MG 41, QUOTE·ORDER_LEAD·RETURN·WARRANTY → POL. reference_doc_id에 문서가 둘 이상인 행은 없다.

그 밖의 검색 자료: 고장 사전(fault_catalog.csv 97종, §4-6), 해결 사례(resolution_cases.csv 800건, 추가 개발 §4-7).

### 4-2. 청크(절) 분할 (T35의 일부: 청크 단위)

- 단위: `##` 또는 `###` 머리글 하나 = 청크 하나. 가장 긴 절이 1,092자라 더 자르지 않는다. `##` 아래에 `###`가 있으면 `##` 머리글 바로 아래 글만 `##` 청크로 두고, 각 `###`는 따로 청크로 둔다.
- 청크 ID: `{doc_id}§{절 번호}` (예: `TG-ACB-AS-2000§3.1`, FAQ는 `FAQ-DRIVE§Q3`). 절 번호는 TEXT로 저장한다("2.10"이 2.1로 바뀌지 않게).
- 청크 앞에 문서 제목과 절 제목을 붙여 임베딩한다(예: "ACB 2000A Troubleshooting Guide > 3.1 Terminal overheating / discoloration\n본문 …"). 짧은 절도 무엇에 관한 절인지 드러나게 하기 위해서다.
- 꼬리표(메타데이터): doc_id, doc_type, product_code(정책·FAQ는 비움), family(정책은 비움), section_no, section_title. 문서 개정(revision)은 `ref.document`에서 찾는다(테이블 정의서 v1.1 §8).
- 정답 절 일치 채점(AC-016-4)을 위해 reference_section 값(예: "3.1")과 청크의 section_no가 같은 표기여야 한다. 적재 때 train 정답의 (reference_doc_id, reference_section) 쌍이 모두 청크 ID로 존재하는지 검사한다(작업 W2).

### 4-3. 다국어 검색 방식 (T25, 결정 필요)

문서는 모두 영어이고 질문은 15개 언어다. 두 방식이 있다.

| 방식 | 내용 | 장점 | 단점 |
|---|---|---|---|
| A 영어 검색문 | L1이 하위 문의마다 영어 한두 문장(query_en)을 함께 만든다. 이 문장으로 검색 | 임베딩 모델 선택이 자유롭고, 키워드 검색도 영어로 된다. 추가 호출 없음 | L1이 요약을 잘못 쓰면 검색도 틀린다 |
| B 다국어 임베딩 | 원문 문장을 다국어 임베딩 모델로 바로 검색 | 요약 단계 오류가 없다 | 임베딩 모델이 15개 언어를 고르게 지원해야 한다. 키워드 보조가 영어 문서와 안 맞는다 |

결정 전 진행 방식: **A로 만들고**, 임베딩은 Gemini 임베딩 모델(D8, 다국어 지원)을 쓴다(모델 이름과 차원은 T38). valid에서 근거 문서 적중률(AC-016-4)을 A와 B로 한 번씩 비교해 정한다(기획서 10-4 "영어 검색문으로 시작하고 검증용 데이터에서 다국어 임베딩과 비교").

### 4-4. 검색 절차

1. **범위 좁히기(꼬리표 필터)**: `product_code = 하위 문의의 제품` 인 청크 + `doc_type = POL` 4개 문서 + `doc_type = FAQ AND family = 하위 문의의 제품군`. 제품이 없으면 POL + (제품군이 있으면) FAQ만, "제품 문서 미검색" 표시.
2. **우선 문서 종류**: 위 4-1의 유형별 종류를 먼저 검색. 결과가 없거나 모두 기준 미만이면 범위 전체로 넓힌다.

   | 유형 | 우선 종류 |
   |---|---|
   | TECH_SPEC, COMPLIANCE | DS |
   | DEFECT | TG |
   | INSTALL | IG, TG |
   | FW_UPDATE | RN |
   | MANUAL | IG, TG, RN, DS, MG |
   | QUOTE, ORDER_LEAD | POL(POL-ORDER 우선) |
   | RETURN | POL(POL-RETURN 우선) |
   | WARRANTY | POL(POL-WARRANTY 우선) |

3. **점수 계산**: 벡터 유사도(코사인) + 정확 문자열 가점. 에러 코드(error_code)나 펌웨어 버전(current_fw)이 있으면 그 문자열이 든 청크에 가점을 준다(FR-016 처리 3번). 최종 점수 = 벡터 유사도 + 0.2 × 정확 문자열 포함(제안).
4. **상위 k개**: k = 5(제안, T27). 후보 목록을 `sub_ticket.evidence_json`(jsonb, `[{doc_id, section, quote, score}, …]`)에 통째로 저장하고, 1위 후보를 `reference_doc_id`·`reference_section`에 둔다(정답지 tickets.csv의 같은 이름 열과 비교하는 대표 1건). 별도 근거 표는 두지 않는다(T42, 조장 결정 2026-10-14).
5. **근거 없음**: 후보가 비었거나 모두 기준 점수 미만이면 "근거 없음". 기준 점수는 T27(결정 전에는 기준 없이 빈 결과만 근거 없음으로 처리하고, valid에서 정답 문서가 잡히는 최저 점수 분포를 본 뒤 정함).

### 4-5. 색인 저장

`ref.doc_chunk` 표(테이블 정의서 v1.1 §2-5)에 청크 본문과 벡터를 함께 둔다. v1.0의 svc.doc_chunk를 ref로 옮긴 이유는 서비스와 채점이 같은 색인을 읽는 읽기 전용 표이기 때문이다. 107개 문서, 절 2~22개라 청크는 1천 개 안팎이다. 이 규모에서는 근사 색인 없이 전수 비교로도 충분히 빠르다. 색인은 문서가 바뀔 때만 다시 만든다(작업 W2). 벡터 차원은 임베딩 모델(T38)이 정해지면 고정한다.

### 4-6. 고장 진단 (FR-018, MVP)

Q8a 노드. category ∈ {DEFECT, INSTALL, WARRANTY}인 하위 문의에서만 돈다. 결과는 상담원 참고용(FR-024·030)과 이관 후보(§5-6)의 입력이며 답변 초안(L4)의 입력에는 넣지 않는다.

1. **정확 조회**: error_code가 있으면 `ref.fault`(fault_catalog.csv 97종, `ref.fault_product`로 제품군 연결)에서 같은 제품군·같은 에러 코드 행을 찾는다. 찾으면 찾은 방법 = EXACT, 점수 1.0, 1순위.
2. **증상 검색**: 정확 조회가 없거나 에러 코드가 없으면 같은 제품군의 fault 행 중 증상 문장(symptom)과 가까운 것을 찾는다. 증상 문장은 색인 작업(W1)에서 문서 청크와 같은 임베딩 모델로 벡터를 만들어 `ref.fault.symptom_embedding`(제안 열)에 둔다. 질문 벡터는 하위 문의의 query_en(§4-3 A 방식) + error_code 문자열. 다른 제품군 행은 필터로 제외한다. 상위 3건(제안, T39), 찾은 방법 = SYMPTOM.
3. **출력**: 후보마다 fault_id, 원인(cause), 점검·조치(action), 현장 출동 필요(onsite_required), 교체 필요(replace_required), 찾은 방법, 점수. 점수가 모두 기준(T39) 미만이면 후보는 보이되 "관련성 낮음" 표시.
4. **저장**: 후보 목록은 상태 객체 fault_candidates와 실행 로그 `agent_step.output_json`(step 1개)에 남긴다. "왜?" 화면(FR-024)은 이 로그를 읽는다. 문서 근거가 아니므로 evidence_json에는 넣지 않는다(T42).
5. **채점**(AC-018-5): 1순위 후보의 현장 출동·교체 필요 표시를 정답의 escalated·escalation_reason과 비교해 일치율을 보고한다. 참고(명세서 FR-020 AC-020-5): 고장 사전의 교체 필요 Y 176건은 전부 RMA로 끝났고, 현장 출동 표시는 800건 전부 일치했다.

### 4-7. 유사 해결 사례 검색 (FR-019, 추가 개발, 확장 지점만)

MVP에서는 만들지 않는다. 들어올 때의 자리만 적어 둔다.
- 노드: Q8a 뒤 Q8b. category ∈ {DEFECT, INSTALL, WARRANTY, FW_UPDATE, RETURN}에서만.
- 자료: `gold.resolution_case` 800건 중 train 티켓에 연결된 사례만 색인(valid·test 연결 사례 제외). 색인 표는 ref에 두고 문서 청크와 같은 임베딩 모델을 쓴다.
- 출력: 상위 3건(사례 ID, 원인, 조치, 결과)을 `agent_step.output_json`에 저장. 초안 입력에는 넣지 않는다(AC-019-3).

---

## 5. 규칙 엔진과 표 조회 (FR-010~014, 017, 020, 041)

규칙 엔진은 Python 함수 묶음이며 LLM을 부르지 않는다. 모든 함수는 결과와 함께 "어느 표의 어느 행을 썼는지"와 판정 과정을 돌려주고, 이것이 근거 표시(FR-024)의 재료가 된다.

### 5-1. 기준정보 적재 구조 (ref 스키마)

ref/ CSV 12개를 정규화해 표 23개로 적재한다. 적재본만으로 tickets.csv 4,000건의 우선순위 규칙·SLA 목표·필수정보를 100% 재현했고 외래 키 위반은 0건이다. 여기에 문서 목록(document 107행)과 문서 청크(doc_chunk)를 더해 ref는 표 25개다(테이블 정의서 v1.1 §1).

| 묶음 | 표 | 원본 |
|---|---|---|
| 코드 | department, product_family, inquiry_category, priority_level, customer_tier, urgency, info_field | departments.csv, product_master.csv, sla_policy.csv, priority_rules.csv, customers.csv, urgency_codebook.csv, info_field_codebook.csv |
| 마스터 | customer, product, product_standard, product_certification, product_spec, firmware_release | customers.csv, product_master.csv, product_spec_facts.csv, firmware_history.csv |
| 진단 | fault, fault_product | fault_catalog.csv (MVP, §4-6) |
| 규칙 | priority_rule, priority_rule_urgency, priority_rule_category, routing_rule, required_info_rule, required_info_field, sla_policy, sla_setting | priority_rules.csv, routing_rules.csv, required_info.csv, sla_policy.csv |
| 문서 | document, doc_chunk | doc_index.csv, docs/ 107개 (W2) |

적재 주의: 모든 CSV가 UTF-8 BOM으로 시작하므로 `utf-8-sig`로 읽는다. fw_version, section, fw_fix_version은 문자열로 읽는다. routing_rules.csv의 family = 'ALL'과 primary_dept = '(제품군 기술지원)'은 NULL로 바꾸고 각각 "모든 제품군", "제품군의 기술지원 부서(product_family.tech_support_dept)"로 해석한다. routing_rules.csv의 rule_source = ESCALATION 3행은 1차 배정에 쓰지 않고 이관 후보(§5-6)에만 쓴다.

### 5-2. 우선순위 (FR-011, T33: 조건 표현 방식)

조건 문장(priority_rules.csv condition)을 코드에 옮겨 적지 않는다. 문장 속 집합을 두 조건 표에 행으로 적재해 두고 엔진은 표만 읽는다.

```
for rule in priority_rule order by rule_order:
    urg_ok = (rule에 priority_rule_urgency 행이 없음) or (urgency_flag ∈ 그 행들)
    cat_ok = (rule에 priority_rule_category 행이 없음) or (category_code ∈ 그 행들)
    trace.append(rule_id, urg_ok and cat_ok)
    if urg_ok and cat_ok: return rule.priority, rule.rule_id, trace
return None, None, trace          # "우선순위 미정"
```

PR-06·PR-07의 "정보성 Category"는 TECH_SPEC, MANUAL, COMPLIANCE, QUOTE로 명시해 적재한다. 원문 condition은 화면 표시용으로 그대로 둔다(AC-030-2).

### 5-3. 부서 (FR-012)와 반품 단어 규칙 (T29)

1. 기본 키: `RT-{family}-{category}` (rule_source = CATEGORY_DEFAULT 또는 FAMILY_OVERRIDE). ESCALATION 3행은 1차 배정에 쓰지 않는다.
2. RETURN이면 return_kind를 먼저 정한다. L2가 준 return_reason의 영어 정규화 값에 대해 아래 단어 목록을 소문자로 찾는다. 비불량 단어가 있으면 NON_DEFECT, 불량 단어가 있으면 DEFECT, 둘 다 없거나 둘 다 있으면 UNKNOWN.

   | 구분 | 단어 목록 (결정 전 진행 방식) |
   |---|---|
   | 비불량(NON_DEFECT → RT-ALL-RETURN-NON_DEFECT, SCM) | different model, wrong model, wrong item, wrong product, ordered by mistake, order error, ordering mistake, surplus, excess, overstock, no longer needed, not needed, project cancel, changed mind, change of mind |
   | 불량(DEFECT → 기본 행, WARRANTY_DESK) | defect, defective, quality problem, quality issue, dead on arrival, doa, damaged, crack, broken, does not power, not working, fault |

3. UNKNOWN이면 기본 행 + "반품 사유 확인 필요" 표시. 상담원이 화면에서 불량/비불량을 고르면 Q4부터 다시 돈다.
4. 단어 목록은 코드가 아니라 설정 파일(`config/return_reason_words.yaml`)에 둔다.
5. 점검: train 반품 행(tickets.csv category_code = RETURN)에서 L2 → 단어 규칙 결과를 정답 routing_rule_id(RT-ALL-RETURN-NON_DEFECT 176건 / 그 밖 174건, 전체 4,000건 기준)와 비교해 목록을 고친다. 정답지 본문은 "We received a different model from what we ordered", "The unit was dead on arrival" 같은 문장이 반복되므로 단어 규칙으로 충분할 가능성이 높다. valid 일치율이 낮으면 D13에 따라 확장 FR-009(LLM 판별)로 바꾼다.
6. 이관 조건: 기본 행의 escalation_dept·escalation_condition 문구를 그대로 `escalation_condition`에 담아 화면에 보여 준다(FR-020 처리 4번).

### 5-4. 필수정보 (FR-013)와 SLA 목표 (FR-014)

- 필수정보: `required_info_field`에서 (family, category) 행을 field_order 순으로 읽어 `missing_info = 필수 − 제공`, `missing_blocking_info = (is_blocking = true) − 제공`. 순서를 유지한다(정보 요청 문안의 항목 순서). 라벨은 info_field.label.
- SLA 목표: `sla_policy`에서 (category, customer_tier, priority_final) 1행. 목표 시간은 하위 문의 행(`sub_ticket`)에 **복사해 저장**한다. 정책표가 나중에 바뀌어도 그때 약속한 목표로 판정하기 위해서다(의도적 중복 저장). 조정(FR-028) 때는 다시 조회해 덮어쓰고, 이전 값은 `priority_adjustment`에 남긴다.

### 5-5. 숫자 표 조회 (FR-017)

| 유형 | 조회 | 출처 표기 |
|---|---|---|
| QUOTE, ORDER_LEAD | product.list_price_usd, std_lead_time_weeks, moq. 수량이 있으면 합계 = 단가 × 수량 | `product_master.csv:{product_code}` |
| TECH_SPEC, COMPLIANCE | product_spec(product_code, attribute). attribute는 근거 후보 절(product_spec.doc_id·section과 같은 절)에 걸린 행을 먼저, 못 정하면 그 제품의 전체 사양 행 | `product_spec_facts.csv:{product_code}/{attribute}` |
| FW_UPDATE, MANUAL(RN 요청) | 아래 SQL. 고객 버전과 비교해 "업데이트 안내"/"이미 최신" | `firmware_history.csv:{product_code}/{fw_version}` |
| WARRANTY | product.warranty_months | `product_master.csv:{product_code}` |

```sql
-- 접수 시점 최신 펌웨어 (팀 정리 §3 원칙 4)
SELECT fw_version, release_date
  FROM ref.firmware_release
 WHERE product_code = :product_code
   AND release_date <= CAST(:received_at AS date)
 ORDER BY release_date DESC
 LIMIT 1;
```

버전 비교는 문자열이 아니라 점으로 나눈 숫자 묶음으로 한다("3.10" > "3.9"). 할인가·납기 가산은 계산하지 않는다(D14). 요청 납기가 표준 납기보다 빠르면 표시만 하고 초안에 납기 확정 문구를 넣지 않는다.

### 5-6. 이관 후보 (FR-020, MVP)

Q9a 노드. 표시만 하고 상태는 바꾸지 않는다(AC-020-4). 이관 확정은 FR-033 API(§8-1)다.

| 이관 행(routing_rules.csv rule_source = ESCALATION) | 켜지는 조건 | 이유 표시 |
|---|---|---|
| RT-ESC-DEFECT-SAFETY | urgency_flag = SAFETY | SAFETY |
| RT-ESC-DEFECT-RMA | 고장 진단 1순위 후보의 replace_required = Y | 교체 |
| RT-ESC-DEFECT-ONSITE | 고장 진단 1순위 후보의 onsite_required = Y | 현장 출동 |

- 조건 문구는 코드에 박지 않고 §5-2와 같은 조건 표 방식으로 적재한다(명세서 FR-020 처리 1번). 여러 행이 맞으면 모두 후보로 둔다.
- 맞는 행이 없으면 후보 "없음"이고 §5-3 6번의 이관 조건 문구만 보여 준다. 진단이 없으면 SAFETY 판정과 이관 조건 문구만.
- 저장: 상태 객체 escalation_candidates와 `agent_step.output_json`. 화면은 상태 객체 값을 API 응답으로 받는다. 상담원이 [이관]으로 확정하면 기본값이 이 후보의 부서이고, 확정 시각·주체는 `ticket_status_history`의 ESCALATE 전이 행(changed_at_utc, changed_by)에 남는다(sub_ticket에 escalated_at·escalated_by 열을 두지 않음, DB 설계 이유서 §6).
- 채점(AC-020-5): 예상 이관 부서를 정답 escalated_to와 비교해 재현율을 보고한다.

### 5-7. 자동 발송 판정 (FR-041, D24)

Q12 노드. LLM을 쓰지 않는다. 대상이 아닌 초안은 DRAFT로 두고 상담원 승인(FR-031)으로 간다.

1. **대상**: 종류가 INFO_REQUEST 또는 FINAL_REPLY인 DRAFT. 진행 안내(PROGRESS_NOTICE)는 대상이 아니다(D7). 리마인드는 이 판정 없이 스케줄러가 보낸다(D29).
2. **유형 조건**: 초안이 답하는 하위 문의의 category_code ∈ {TECH_SPEC, MANUAL, COMPLIANCE}. 한 메일에 여러 하위 문의의 답이 묶이면 모두 세 유형이어야 한다.
3. **합격 조건 4개(모두 통과)**: ① `draft_check` 통과(인용이 근거 후보 안, 숫자가 허용 목록 안) ② FINAL_REPLY면 missing_blocking_info = [] ③ 이 실행(run_id)의 `self_check` 행 중 passed_yn = N이 없음(검사 종류: 확신 낮음, 판정 실패, 근거 없음, 반품 사유 확인 필요, 제품 미확정, 추출 실패 …; 상태 객체 flags와 같은 내용) ④ urgency_flag ∉ {SAFETY, SITE_DOWN}.
4. **통과**: 초안 행을 APPROVED(승인 주체 SYSTEM)로 바꾸고 SENT 행(sender = SYSTEM)을 새로 쓴다. 상태 전이는 테이블 정의서 v1.1 전이표의 INFO_REQUEST_AUTO_SENT(→ WAITING_CUSTOMER) / FINAL_REPLY_AUTO_SENT(→ RESOLVED) 행으로 한다. 1차 응답 시각 기록, SLA 재계산, 다음 진행 안내 초안은 상담원 발송과 같다.
5. **불통과**: `ticket_message.auto_send_hold`에 어긋난 조건 목록을 남기고 DRAFT 그대로 둔다. 화면은 "자동 발송 보류: {이유}".
6. **기록**: 판정 결과(대상 여부, 조건별 통과·불통과)를 `agent_step` output_summary에 남긴다. AC-041-6(어긋난 초안이 자동 발송된 건수 0)은 이 로그를 집계해 확인한다.
7. **실패**: 판정 중 오류나 SENT 저장 실패는 모두 "보류"로 처리한다(발송하지 않은 것으로 본다).

실시간 자체 검사 경고(FR-045, 추가 개발)가 들어오면 같은 `self_check` 표에 행이 더해져 합격 조건 ③에 자연히 합쳐진다.

---

## 6. 저장 구조 (FR-001, 024~028, 031~033, 035, 036, 039, 041)

표 이름과 열의 기준은 ticket/sub_ticket ERD v1(bootcamp/erd/ERD_ticket_sub_ticket_v1.mmd, 2026-10-14)과 ticket/sub_ticket 컬럼 분리안이다. 제약(전이표, 보호 장치, 함수·뷰)은 테이블 정의서 v1.1(bootcamp/db/v1.1/)을 따르되, 그 문서의 `ticket_inquiry`(PK ticket_id, seq)·`priority_change`는 ERD v1의 `sub_ticket`·`priority_adjustment`로 이름이 바뀌고, `inquiry_evidence`·`doc_candidate`(그리고 ERD v1의 `sub_ticket_evidence`)는 두지 않는다. **답변 근거는 sub_ticket의 JSON 열 1개(evidence_json)에 둔다**(조장 결정 2026-10-14, T42). sub_ticket_id는 처음 안대로 `ticket_id-seq` 문자열이다(조장 결정 2026-10-14; DB 쪽이 한때 정수 대리키로 바꿨다가 되돌림). priority_adjustment 표를 따로 둘지는 아직 조장 확인 전이다(DB 설계 이유서 §7-1). 이 절의 "추가 제안" 칸은 DB 설계 이유서 v1.1 §6의 판단(반영 예정 / 보류 / 제외)을 함께 적는다. "반영 예정" 열은 ERD v1.2에 그려질 때까지 이 문서가 기준이다.

### 6-1. 스키마 나누기와 정답지 격리

| 스키마 | 담는 것 | 누가 쓰나 |
|---|---|---|
| ref | 기준정보·규칙표 23개 + document + doc_chunk | 적재·색인 작업만. 서비스와 채점은 읽기만 |
| gold | tickets.csv 4,000건(58열 그대로), resolution_cases.csv 800건 | 적재 작업만. 서비스는 FR-003 불러오기에서 `gold.v_train_inputs`(data_split = 'train' 행의 입력 열 6개)만 읽는다 |
| svc | 서비스 표(아래) | 서비스 |
| scoring | svc와 같은 표 모양. 채점 배치가 실행마다 비우고 쓴다 | 채점 배치·평가 러너(FR-042)만 |
| eval | DB 설계 이유서 v1.1 §5의 표 7개: `gold_ticket`(tickets.csv 58열 읽기 전용; gold 스키마 적재와 같은 내용을 평가 ERD에서 부르는 이름), `eval_run`(채점 실행 1회: 언제·어떤 프롬프트·규칙·모델로·몇 건), `eval_case`(티켓 × 채점 항목: 기대값·실제값·일치 여부, gold_ticket_id와 sub_ticket_id를 둘 다 가짐), `eval_summary`(실행 × 항목 집계), `agent_feedback`(승인·수정 1항목), `self_check`(실시간 검사 1건, run_id로 실행에 연결), `prompt_example`(교정 사례, 추후). 채점 제외 목록 `exclusion`(§10-3)은 그대로 | §10 채점 배치(eval_run·eval_case·eval_summary·exclusion), 자동 발송 판정(self_check, §5-7), 평가 러너(FR-042), 주간 품질 추이(FR-044), 대시보드 추이 영역(FR-034). self_check·exclusion은 MVP가 쓰고 나머지는 추가 개발이지만 표는 미리 만든다(T41) |

test·valid 행은 svc에 들어가지 않는다. 채점 배치는 같은 파이프라인 코드를 scoring 스키마를 향하게 설정해 돌린다(§9 W4). 서비스 DB 연결 계정은 gold 스키마에서 `v_train_inputs` 뷰에만 권한을 준다.

### 6-2. 서비스 표 목록 (svc 스키마)

| 표 (ERD v1) | 한 행은 | ERD v1의 열 (처리 흐름이 쓰는 것) | 추가 제안 (ERD v1에 없고 이 문서의 흐름에 필요한 열) — DB 설계 이유서 §6 판단 | 관련 FR |
|---|---|---|---|---|
| ticket | 접수 1건 (13열) | ticket_id(PK), received_at_utc, channel, language, body_language, locale, customer_id → customer, customer_tier(접수 당시 스냅샷), contact_email_masked, inquiry_subject(저장만), inquiry_body(마스킹됨), multi_yn, source(시뮬레이터 / 정답지 불러오기 원본 ID) | body_language_uncertain(언어 판정 불확실 표시, FR-004) — 반영 예정 | 001, 003, 004, 006 |
| sub_ticket | 하위 문의 1개 (40열) | sub_ticket_id(PK, `ticket_id-seq`), ticket_id → ticket, seq, category_code(1개), evidence_sentences, urgency_flag, product_code, error_code_reported, fw_version_reported, priority, priority_rule_id, priority_adjusted_by_agent, routing_rule_id, assigned_dept, assignee_masked, escalated, escalated_to, escalation_reason(11값), required_info, provided_info, missing_info, missing_blocking_info, info_request_sent, status, first_response_at_utc, resolved_at_utc, first_response_hours, customer_wait_hours, sla_first_response_target_h, sla_resolution_target_h, sla_elapsed_hours, sla_first_response_status, sla_resolution_status, final_action, rma_no, reference_doc_id, reference_section(정답지 비교용 대표 1건), resolution_case_id, no_evidence_flag, pipeline_error, **evidence_json**(jsonb, 문서 근거 후보 목록 `[{doc_id, section, quote, score}, …]`, 조장 결정 2026-10-14·T42) | 반영 예정: return_kind(반품 구분, §5-3), sla_id(적용 정책 행), version(동시 변경 방지, §6-3). 제외: escalated_at·escalated_by(ticket_status_history의 ESCALATE 행으로 대체), flags(self_check 행으로 대체; 열은 no_evidence_flag·pipeline_error만). 부분 동의: 경과·상태 5열(first_response_hours ~ sla_resolution_status)은 열을 유지하되 §6-4의 함수가 채우는 "파생 열"로 표기하고, 서비스는 이력에서 계산한다 | 005~014, 016, 018, 020, 024, 025, 028, 033 |
| ticket_message | 메시지 1줄 | message_id(PK), ticket_id, sub_ticket_id(티켓 전체면 NULL), sender(CUSTOMER / SYSTEM / AGENT / DEPT), message_type 6개(INQUIRY / INFO_REQUEST / FINAL_REPLY / PROGRESS_NOTICE / CUSTOMER_REPLY / ESCALATION_NOTE), message_status(DRAFT / APPROVED / SENT / RECEIVED), sent_at_utc, language, body, source_draft_id(발송 행의 원본 초안), edited_yn, sent_by_name | message_no(티켓 안 순번, FR-035 4번), mask_count(§7), notice_transition(①~④ / REMINDER, D29), override_check(FR-031 2번), superseded_at(재처리로 밀린 초안), auto_send_hold(보류 사유 목록, FR-041) — 이상 반영 예정. 보류: mask_count·override_check(마스킹·재확인 규칙 확정 뒤). 보류(별도 표 권장): 대역(FR-039)은 언어별로 여러 개일 수 있어 `message_gloss`(message_id, language, body, made_at) 표로 둔다(§7, §8-1 `/messages/{draft_id}/gloss`). 테이블 정의서 v1.1 변경 14·16·17과 같음 | 015, 021~023, 031~033, 035, 039, 041 |
| ticket_status_history | 하위 문의 상태 변경 1건 | history_id(PK), sub_ticket_id, from_status, to_status, changed_at_utc, changed_by, reason | event_kind(전이표의 사건 이름, §6-4) — 반영 예정. 대기 구간은 WAITING_CUSTOMER로 들어간 행과 나온 행의 쌍으로 구한다. ESCALATE 전이 행이 이관 확정 시각·주체의 기록이다(FR-033) | 025, 026, 033 |
| priority_adjustment **(확인 필요: 별도 표 vs ticket_status_history 사건 종류, DB 설계 이유서 §7-1)** | 우선순위 조정 1건 | adjust_id(PK), sub_ticket_id, from_priority, to_priority, reason, adjusted_by, adjusted_at_utc | reason_kind(고객 요청 / 영향 범위 재평가 / 기타, FR-028 6번), from_sla_id·to_sla_id, from_targets·to_targets(바뀐 목표 시간, AC-028-1 "변경 이력에 이전·새 값") — 반영 예정 | 028 |
| sla_alert | 경고 1건 | alert_id(PK), sub_ticket_id, alert_type(FR_AT_RISK / FR_BREACHED / RES_AT_RISK / RES_BREACHED), raised_at_utc, cleared_at_utc, notified_to | elapsed_h·target_h(발생 당시 값, FR-027 2번), UNIQUE(sub_ticket_id, alert_type)로 "같은 종류 한 번만" — 반영 예정 | 027 |
| agent_run | 처리 실행 1회 | run_id(PK), sub_ticket_id, started_at_utc, finished_at_utc, status(SUCCESS / FAILED / PARTIAL), llm_model | ticket_id(티켓 그래프 실행은 sub_ticket_id가 없음), trigger(INTAKE / RETRY / CUSTOMER_REPLY / AGENT_EDIT / DEPT_REPLY), last_step — 반영 예정 | 036 |
| agent_step | 노드 실행 1회 | step_id(PK), run_id, step_name, input_json, output_json, tokens, latency_ms, error | step_order, started_at·finished_at, result, error_kind(6종, §6-5), prompt_version, input_tokens·output_tokens(tokens를 둘로), llm_calls — 반영 예정. retrieved_chunk_ids는 doc_chunk 표가 정해진 뒤. output_json이 진단 후보·이관 후보·유사 사례·자동 발송 조건별 결과의 저장처이며 "왜?" 화면(FR-024)이 읽는다 | 018, 019, 020, 024, 036, 041 |
| (ERD v1에 없음) inquiry_field | 제공 항목 1개 | — | sub_ticket.provided_info가 항목 이름 목록이라 값·본문 위치(span)가 없다. 화면 강조(FR-030 1번)와 회신 합집합(FR-032 3번)에 값이 필요하므로 테이블 정의서 v1.1 §4-5의 inquiry_field(sub_ticket_id, field, value_raw, value_norm, span_start, span_end, source, source_message_id)를 둔다 — 반영 예정 | 008, 013, 032 |
| (평가 ERD) self_check | 실시간 검사 1건 | check_id(PK), run_id → agent_run, sub_ticket_id, check_type, passed_yn, detail, checked_at_utc(DB 설계 이유서 §5) | — . 상태 객체 flags의 저장처이자 자동 발송 합격 조건 ③(§5-7)의 근거. MVP가 쓴다 | 024, 041, 045 |
| (평가 ERD) agent_feedback (추가 개발) | 상담원 수정·승인 기록 1항목 | DB 설계 이유서 §5(에이전트 값 / 최종값 / changed_yn / 사유, message_id는 초안 글을 고친 경우만) | — . MVP는 쓰지 않는다(T41) | 043 |

- v1.0의 `ticket_inquiry` → `sub_ticket`, `priority_change` → `priority_adjustment`, `inquiry_evidence` + `doc_candidate` → 표 없음(문서 근거는 `sub_ticket.evidence_json`, 나머지 근거는 `agent_step.output_json`·`self_check`), `ticket.category_code(';')`·`split_check_needed`·`first_response_at` → 삭제 또는 sub_ticket으로 이동(분리안 K2·K3·K5). `doc_chunk`는 ref로 이동(테이블 정의서 v1.1).
- ERD v1의 기준정보 쪽(customer, product, priority_rule, routing_rule, department, document, resolution_case …)은 ref·gold 스키마의 표를 그린 것이며 §5-1과 같다.
- 리마인드는 notice_transition = REMINDER이며 하위 문의당 1행만 허용하는 부분 유일 색인(`ticket_message_one_reminder`)으로 중복을 막는다.
- 1차 응답 시각은 하위 문의마다 다를 수 있으므로 sub_ticket에 둔다(D21: 그 하위 문의의 INFO_REQUEST 또는 FINAL_REPLY의 첫 SENT 시각, 자동 발송 포함).

### 6-3. 지우지 않는 기록 (FR-035 처리 1번)

- ticket_message, ticket_status_history, priority_adjustment, sla_alert, agent_run, agent_step, self_check, agent_feedback은 INSERT만 한다. sub_ticket.evidence_json은 재처리 때 통째로 바뀌므로 이전 값은 agent_step.output_json에 남는다. 예외는 FR-035가 허용한 것(DRAFT → APPROVED 상태 변경, 임시 저장 때 DRAFT 본문 수정, DRAFT의 대역·보류 사유 갱신)과 superseded_at, cleared_at, agent_feedback의 채택 칸이다.
- DB 수준 보호: SENT·RECEIVED 행의 body를 바꾸는 UPDATE를 막는 트리거, 같은 draft_id로 SENT 행이 두 개 생기지 않게 부분 유일 색인(`UNIQUE (draft_id) WHERE message_status = 'SENT'`), 사유 없는 이관 금지(escalated_to와 escalation_reason은 함께 있거나 함께 비움). 테이블 정의서 v1.1 06_규칙_동작_확인.sql이 보호 장치 9개를 확인한다.
- 같은 하위 문의에 동시 상태 변경 두 건(FR-025 예외): sub_ticket에 `version` 열을 두고 "읽은 version과 같을 때만 바꾸기"로 막는다. 다르면 API가 409(충돌)를 돌려주고 화면이 "다른 사용자가 먼저 변경함. 새로고침"을 띄운다.

### 6-4. 상태 이력과 SLA 계산 (FR-025~027, 033, D16·D20·D21·D22·D29)

**상태 이력은 앱이 사건 시각으로 쓴다.** 트리거가 `now()`로 쓰는 방식은 쓰지 않는다. 시연과 채점에서 과거 시각의 접수·회신(FR-001, FR-032 "재현용 과거 시각")을 넣어야 하는데, 트리거는 사건 시각이 아니라 저장 시각을 남기기 때문이다(T34). 상태를 바꾸는 함수는 하나(`transition(sub_ticket_id, to_status, event_kind, at, actor, reason, final_action)`, 테이블 정의서 v1.1 §4-13)로 두고, 허용 전이표(`status_transition` 14행)에 없는 전이는 이 함수가 거부한다.

허용 전이표(FR-025, 테이블 정의서 v1.1 §4-1)

| 이전 → 새 상태 | 사건(event_kind) | 주체 |
|---|---|---|
| (없음) → NEW | INTAKE | 시스템 |
| NEW → IN_PROGRESS | PIPELINE_DONE | 시스템 |
| NEW / IN_PROGRESS → WAITING_CUSTOMER | INFO_REQUEST_SENT(상담원 승인) / INFO_REQUEST_AUTO_SENT(자동 발송) | 상담원 / 시스템 |
| WAITING_CUSTOMER → IN_PROGRESS | CUSTOMER_REPLY | 상담원(대리 입력) |
| IN_PROGRESS → ESCALATED | ESCALATE(사유 필수) | 상담원 |
| ESCALATED → IN_PROGRESS | DEPT_REPLY | 상담원(대리 입력) |
| IN_PROGRESS / ESCALATED → RESOLVED | FINAL_REPLY_SENT / FINAL_REPLY_AUTO_SENT (답한 하위 문의만) | 상담원 / 시스템 |
| RESOLVED → CLOSED | NO_REPLY_168H_AFTER_RESOLVED | 시스템 |
| RESOLVED → IN_PROGRESS | CUSTOMER_REPLY(168시간 안) | 상담원(대리 입력) |
| WAITING_CUSTOMER → CLOSED | NO_REPLY_168H (final_action = CLOSED_NO_RESPONSE) | 시스템 |

상담원이 닫는 전이(v1.0의 CLOSED_BY_AGENT)는 없다(D20: 종료 버튼 없음).

**SLA는 저장하지 않고 "기준 시각"을 받는 SQL 함수로 계산한다.** 서비스 화면은 기준 시각 = 지금, 채점은 기준 시각 = 스냅샷(2026-09-30 23:59 UTC)으로 같은 함수를 부른다.

```sql
-- svc.inquiry_sla(as_of) : 하위 문의별 두 시계 (FR-026)
-- 1차 응답 시각: 그 하위 문의의 INFO_REQUEST 또는 FINAL_REPLY 중 첫 SENT 시각 (D21, 자동 발송 포함)
-- 대기 합: WAITING_CUSTOMER 구간 합. 아직 대기 중이면 as_of 까지. ESCALATED는 멈추지 않는다 (FR-033 처리 7번)
fr_elapsed  = COALESCE(first_response_at, as_of) - received_at                  -- 멈추지 않음
fr_status   = CASE WHEN first_response_at IS NOT NULL
                   THEN CASE WHEN fr_elapsed <= fr_target THEN 'MET' ELSE 'BREACHED' END
                   WHEN fr_elapsed > fr_target THEN 'BREACHED' ELSE 'ON_TRACK' END
res_elapsed = COALESCE(resolved_at, as_of) - received_at - wait_total            -- 대기 구간 제외
res_status  = CASE WHEN final_action = 'CLOSED_NO_RESPONSE' THEN 'N/A'
                   WHEN resolved_at IS NOT NULL
                   THEN CASE WHEN res_elapsed <= res_target THEN 'MET' ELSE 'BREACHED' END
                   WHEN res_elapsed >  res_target        THEN 'BREACHED'
                   WHEN res_elapsed >= res_target * 0.75 THEN 'AT_RISK'
                   ELSE 'ON_TRACK' END
remaining_h = res_target - res_elapsed
```

- 1차 응답에는 AT_RISK 상태가 없다(정답지 MET 3,531 / BREACHED 457 / ON_TRACK 12). 75% 경고는 sla_alert의 FR_AT_RISK로만 단다.
- 75%(at_risk_threshold)와 대기 제외 규칙(pause_rule)은 ref.sla_setting에서 읽는다. 24x7 달력 시간(clock)이므로 영업시간 계산은 없다.
- 계산은 초 단위, 표시는 소수 첫째 자리. 대기 구간의 나온 시각이 들어간 시각보다 빠르거나 경과가 음수면 0으로 두고 "시간 기록 확인 필요"(FR-026 예외).
- 해결 시각(resolved_at)은 RESOLVED로 처음 바뀐 시각이다. RESOLVED → IN_PROGRESS로 돌아왔다가 다시 RESOLVED가 되면 마지막 시각으로 갱신한다(D20 "기한은 해결 시각 기준").
- 티켓 대표값(D16, FR-025 처리 5번): 끝나지 않은 하위 문의 중 가장 급한 것(경고 있음 → 남은 시간 최소)의 상태·SLA. 모두 끝났으면 RESOLVED(모두 CLOSED면 CLOSED). 뷰 `svc.v_ticket_summary`가 계산해 티켓 상세 머리에 쓴다. 접수함은 하위 문의 1행짜리 뷰 `svc.v_inquiry_inbox`를 읽고, 이관된 하위 문의는 원래 부서함과 이관 부서함 양쪽에 보인다(FR-029·033, 테이블 정의서 v1.1 변경 22).

**주기 점검(스케줄러, 5분, T30)** — APScheduler를 FastAPI 안에서 돌린다. 한 주기에 네 가지를 차례로 한다.
1. **SLA 경고(FR-027)**: 끝나지 않은 하위 문의(NEW, IN_PROGRESS, WAITING_CUSTOMER, ESCALATED)의 `inquiry_sla(now())`를 읽고 조건을 처음 만족한 경고만 INSERT(유일 제약이 중복을 막는다). 발생 시각은 점검 시각이 아니라 조건을 넘은 실제 시각(received_at + 대기 + 목표 × 0.75)으로 계산해 넣는다(FR-027 예외: 주기를 건너뛰어도 정확). WAITING_CUSTOMER는 해결 경고를 새로 달지 않는다. 조정으로 목표가 늘어 조건이 풀린 경고에는 cleared_at을 쓴다.
2. **회신 리마인드(FR-023 ⑤, D29)**: WAITING_CUSTOMER이고 마지막 INFO_REQUEST SENT 시각 + 126시간 ≤ 지금이며 그 뒤 CUSTOMER_REPLY가 없고 REMINDER 행이 아직 없으면, 고객 언어 고정 문안 템플릿 + 빠진 항목 라벨로 PROGRESS_NOTICE(notice_transition = REMINDER)를 만들어 바로 SENT(sender = SYSTEM, 승인 주체 SYSTEM)로 쓴다. 상태와 1차 응답 시각은 바뀌지 않는다. 하위 문의당 1번(부분 유일 색인). 대역(L7)은 만든다.
3. **무응답 종료(D22)**: WAITING_CUSTOMER이고 마지막 INFO_REQUEST SENT 시각 + 168시간 ≤ 지금이며 그 뒤 CUSTOMER_REPLY가 없으면 `transition(→ CLOSED, at = 발송 시각 + 168h, actor = SYSTEM)`, final_action = CLOSED_NO_RESPONSE.
4. **해결 뒤 종료(D20)**: RESOLVED이고 FINAL_REPLY SENT 시각 + 168시간 ≤ 지금이며 그 뒤 CUSTOMER_REPLY가 없으면 `transition(→ CLOSED, at = 발송 시각 + 168h, actor = SYSTEM)`.

시연에서는 "시계 돌리기"가 필요하다(AC-025-3, AC-023-5·6). 점검 함수가 `as_of` 인자를 받게 만들어 스케줄러는 `now()`를, 시연 스크립트(W5)와 채점은 지정 시각을 넘긴다.

### 6-5. 실행 로그 (FR-036, T31)

- LangGraph 노드마다 감싸는 함수(데코레이터) 하나가 agent_step 시작·끝·오류·소요를 쓴다. 노드 코드에는 로그 코드를 넣지 않는다. 노드가 아닌 동작(자동 발송 판정은 노드지만, 이관·회신·리마인드는 API·스케줄러)도 같은 함수로 step을 남긴다.
- 입력·출력 요약에는 FR-024가 보여 주는 값(유형, 규칙 ID, 빠진 항목, 인용 목록, 진단 후보 ID, 이관 후보 rule_id, 자동 발송 조건별 결과 등)만 넣고, 긴 본문은 메시지 ID로 가리킨다.
- 분류 단계 입력 요약에 "넣은 항목 이름 목록"을 남긴다(제목이 없음을 확인, AC-036-2). 초안 단계 입력 요약에도 같은 목록을 남겨 진단 후보가 없음을 확인한다(AC-018-4).
- 오류 종류: LLM_TIMEOUT, LLM_INVALID_OUTPUT, RULE_NOT_FOUND, DB, VALIDATION, UNKNOWN.
- 프롬프트·응답 전문 저장: 기본 꺼짐, 환경 변수 `LOG_FULL_LLM_IO=true`로 켠다. 켜면 마스킹을 거쳐 `agent_step.output_summary.full_io`에 저장.
- 보존 기간: agent_run·agent_step 90일(제안). 매일 1회 스케줄러가 지난 run을 지운다. 메시지 이력은 지우지 않는다.
- 로그 저장이 실패해도 처리 흐름은 계속하고 서버 로그 파일에 남긴다.
- 프로세스가 중간에 죽어 끝나지 않은 step은 다음 서버 시작 때 FAILED / UNKNOWN으로 닫는다.
- 실행 계기(trigger)는 INTAKE / RETRY / CUSTOMER_REPLY / AGENT_EDIT / DEPT_REPLY 5개.

---

## 7. 개인정보 마스킹 (FR-038)

**위치**: 저장 계층의 함수 `mask_text(text) -> (masked_text, count)` 하나. 메시지 저장(초안·발송·고객 회신·부서 회신·리마인드), 티켓 저장, 실행 로그 저장, LLM 호출 직전 입력(L1~L7 모두)이 이 함수를 지난다. 다른 경로로 DB에 글을 쓰는 코드를 두지 않는다.

**검사식 (결정 전 진행 방식, 규칙 기반이며 LLM 아님)**

| 대상 | 패턴(설명) | 바꾸는 값 |
|---|---|---|
| 이메일 | `영문·숫자·._%+-` 1자 이상 + `@` + 도메인 + `.` + 2자 이상 영문. 단, 이미 `@***.masked`로 끝나는 값은 제외 | `user***@***.masked` |
| 전화번호 | (가) `+`로 시작하고 숫자가 8개 이상인 숫자·공백·`-`·`.`·괄호 묶음, 또는 (나) 숫자가 8개 이상이고 숫자 묶음 사이에 구분 기호(공백, `-`, `.`, 괄호)가 하나 이상 있는 묶음 | `***-****` |

**제외 목록(먼저 적용, 가리지 않음)**: 날짜 꼴(YYYY-MM-DD, YYYY/MM/DD), 구분 기호 없는 숫자열(주문 번호 PO 4500123456 같은 값), 영문이 섞인 토큰(제조번호 S/N LVB-2024-00117, 에러 코드 E.OC), 펌웨어 버전 꼴(숫자.숫자), 금액·수량. 데이터에 이미 있는 `**MASKED**`, `COMPANY_…`, `user…@***.masked`, `…_AGENT_nn`은 그대로 둔다.

**확인**: AC-038-1(이메일·국제 전화 2곳 가림), AC-038-2(날짜·PO·S/N 0곳), AC-038-3(train 2,800건 적재 시 0곳), AC-038-5(LLM 입력 기록에 가려지지 않은 도메인 없음)를 단위 테스트로 만든다. 사람 이름은 범위 밖(FR-038 5번).

---

## 8. API와 화면 (FR-001, 003, 024, 028~034, 039, 041)

### 8-1. API 목록

모든 시각은 UTC ISO 8601. 상담원 식별은 로그인 대신 요청 머리에 `X-Agent-Name`, `X-Agent-Dept`를 싣는다(D23). FastAPI가 OpenAPI 문서(`/docs`)를 자동으로 만들고, 화면 쪽 TypeScript 타입은 이 문서에서 생성한다. 하위 문의는 `sub_ticket_id`(`CSV1-000008-1` 꼴)로 가리킨다.

| 메서드·주소 | 하는 일 | FR |
|---|---|---|
| `GET /ref/customers?q=`, `GET /ref/products`, `GET /ref/departments` | 시뮬레이터·상담원 선택 목록 | 001, D23 |
| `GET /gold/train/{source_ticket_id}` | train 행의 입력 열 6개(channel, customer_id, product_code, language, inquiry_body, received_at_utc). valid·test면 422와 "train 행만" 문구 | 003 |
| `POST /tickets` | 접수. 검증(미등록 고객 거부, D25) → 저장 → 파이프라인 시작. 응답: ticket_id, processing=true | 001 |
| `GET /tickets?dept=&status=&priority=&alert=&needs_info=&has_draft=&composite=&channel=&auto_sent=&q=&include_closed=&page=&size=50&sort=` | 접수함 목록(v_inquiry_inbox, 하위 문의 1행). dept는 assigned_dept 또는 escalated_to. 건수 요약 포함 | 029 |
| `GET /tickets/{id}` | 상세 묶음: 티켓, 하위 문의별 결과(진단 후보·이관 후보 포함), 근거, 초안(대역·보류 사유 포함), 처리 중 여부 | 030, 024, 039, 041 |
| `GET /tickets/{id}/timeline` | 메시지·상태 이력·경고·조정·이관을 시각순으로 합친 목록 | 030 |
| `GET /tickets/{id}/runs`, `GET /runs/{run_id}/steps` | 처리 기록 | 036 |
| `GET /chunks/{chunk_id}` | 인용 클릭 시 절 본문 | 024 |
| `PATCH /sub-tickets/{sub_ticket_id}` | 유형·긴급도·제품·반품 구분·제공 항목 수정 → 해당 노드부터 재실행 | 030, 010, 012, 013 |
| `POST /sub-tickets/{sub_ticket_id}/priority` | 우선순위 조정(new_priority, reason_kind, reason_text 필수) | 028 |
| `POST /sub-tickets/{sub_ticket_id}/escalate` | 이관 확정(dept, reason_code 필수, memo). IN_PROGRESS에서만. ESCALATION_NOTE SENT 기록, 전이 ESCALATE, 이관 안내 초안 생성 | 033 |
| `POST /sub-tickets/{sub_ticket_id}/dept-reply` | 전문 부서 회신 대리 입력(body, received_at). ESCALATION_NOTE RECEIVED(sender DEPT), 전이 DEPT_REPLY | 033 |
| `POST /tickets/{id}/reprocess` | 다시 처리(새 run) | 001, 030 |
| `PUT /messages/{draft_id}` | 임시 저장(DRAFT 본문만). 저장 뒤 대역(L7)을 다시 만든다 | 031, 039 |
| `POST /messages/{draft_id}/gloss` | 대역 다시 만들기(번역 실패 시 버튼). 결과는 `message_gloss` 행(message_id, language, body, made_at)으로 저장 | 039 |
| `POST /messages/{draft_id}/send` | 승인·발송(final_body, override_check). 자체 대조 불일치면 409 + 불일치 목록, override_check=true로 다시 보내면 발송. 막는 항목이 남은 FINAL_REPLY도 같은 방식 | 031 |
| `POST /tickets/{id}/replies` | 고객 회신 입력(body, language, received_at, target_sub_ticket_ids) | 032 |
| `GET /dashboard/alerts`, `GET /dashboard/summary` | 위험·위반 목록(전 부서), 부서별 미해결 건수, SLA 상태별 건수(include_closed) | 034 |
| `GET /dashboard/quality-trend` (추가 개발) | 주간 품질 추이(eval_summary)와 파일 내려받기. 결과 없으면 빈 목록 | 034, 044 |

v1.0의 `POST /tickets/{id}/close`는 없앴다(D20: 종료는 스케줄러만). 외부 연계 창구(FR-037)는 범위 밖이다. 다만 `POST /tickets`와 `POST /tickets/{id}/replies`가 OpenAPI로 문서화되어 있으므로, 나중에 고객지원 시스템이 붙을 때 이 두 주소가 연계 지점이 된다(T36, 기획서 6-3).

### 8-2. 화면 4개

| 화면 | 주소 | 구성 | 데이터 |
|---|---|---|---|
| 접수 시뮬레이터 | `/intake` | 채널·고객·제품·언어·제목·본문·접수 시각 입력, [train에서 불러오기] | `GET /ref/*`, `GET /gold/train/{id}`, `POST /tickets` |
| 접수함 | `/inbox` | 상단에서 상담원 이름·부서 선택(D23), 필터 7종, 표(FR-029의 열 순서, 하위 문의 1행, "복합 n건 중 k"), 상태 배지 색(ON_TRACK 초록, AT_RISK 노랑, BREACHED 빨강, WAITING_CUSTOMER 회색), "이관됨"·"자동 발송됨" 표시 | `GET /tickets` |
| 티켓 상세 | `/tickets/:id` | 왼쪽 "고객이 보낸 것", 가운데 "시스템이 판단한 것"(하위 문의별 구역, 값마다 "왜?", 고장 진단 후보·이관 후보 구역, [조정] 버튼), 오른쪽 "보낼 것"(정보 요청·답변·진행 안내 탭, 초안 옆 대역 나란히, "자동 발송됨 {시각}" / "자동 발송 보류: {이유}", [승인·발송], 위에 [이관] 버튼), 아래 "이력" 띠([고객 회신 입력], [부서 회신 입력]) | `GET /tickets/{id}`, `/timeline`, 버튼별 POST |
| 운영 대시보드 | `/dashboard` | 위험·위반 목록(전 부서, 남은 시간 오름차순), 부서별 미해결 건수, SLA 상태별 건수, 주간 품질 추이 영역(추가 개발 전에는 "아직 집계 없음")과 [내려받기] | `GET /dashboard/*` |

- 자동 갱신: 접수함과 대시보드는 진입·새로고침 때와 5분마다(스케줄러 주기와 같게, FR-029 6번·FR-034 5번). 티켓 상세는 처리 중일 때만 2초마다.
- 공통 부품을 먼저 만든다: 상태 배지, SLA 두 시계 표시, "왜?" 근거 팝오버, 인용·숫자 출처 링크, 초안+대역 나란히 편집기, 이관 사유 선택(11값).
- 초안 대역(FR-039)은 만든다. 고객 원문의 한국어 번역 토글은 기능 목록에 없으므로 여유 시 항목이다(FR-030 9번).

---

## 9. 기능이 아닌 작업

| 번호 | 작업 | 내용 | 완료 확인 |
|---|---|---|---|
| W1 | 기준정보 적재 | ref/ CSV 12개 → ref 스키마 23개 표 + document 107행. BOM, 문자열 열, 특수값 처리(§5-1). 고장 사전 증상 벡터(§4-6)도 여기서 만든다. 다시 실행해도 같은 결과(기존 표를 비우고 적재) | 외래 키 위반 0건, 우선순위 규칙·SLA 목표·필수정보를 tickets.csv 4,000건에서 100% 재현 |
| W2 | 문서 색인 | docs/ 107개 → 절 단위 청크 → 임베딩 → ref.doc_chunk | train 정답의 (reference_doc_id, reference_section) 쌍이 모두 청크 ID로 존재 |
| W3 | 정답지 적재 | tickets.csv → gold(4,000건, 58열, 읽기 전용), resolution_cases.csv → gold(800건). train만 보이는 뷰 생성 | split 건수 2,800 / 603 / 597 |
| W4 | 채점 배치 | §10 | valid 1회 이상, test 1회 실행 결과표 |
| W5 | 시연 데이터 | 추적표 9건(CSV1-000004·000007·000008·000017·000031·000039·000085·000097·003578, 모두 train)을 불러오기로 재현하는 스크립트. 기획서 4-2 시나리오 ⓐ~ⓕ용 예시: 고객 회신 2건(ⓒ), 복합 문의 1건(ⓓ, 000008), 전문 부서 회신 1건(ⓔ), 우선순위 조정 1건(ⓕ, 000031). 시계 돌리기(§6-4)로 리마인드·자동 종료 재현 | 9건 분류~SLA 결과가 추적표와 같음. 시나리오 6개가 3회 연속 통과(기획서 8-2 5단계) |
| W6 | 접수함 시연용 미해결 데이터 | train 미해결 243건을 정답지 시각으로 svc에 재생(접수 → 정보 요청 SENT → 대기 구간 → 현재 상태). 05_정답지_재생_검증.sql의 재생 방식을 svc용으로 쓴다 | 스냅샷 기준 SLA 상태가 정답과 같음(AT_RISK 23, BREACHED 92, 부서별 수 FR-029 데이터 사실) |
| W7 | 배포 구성 | §1-5. Docker Compose(db, api, web), `.env.example`, 초기화 명령 하나로 00~07 SQL + W1~W3 실행 | 새 노트북에서 README 순서대로 실행해 화면 4개가 뜸 |
| W8 | 채점 제외 목록 | eval.exclusion 67행(시간 기록 이상 10건 + 펌웨어 시점 모순 57건, D26). 펌웨어 57건의 ticket_id 목록은 데이터 분석에서 다시 뽑는다 | 행 수 67, 10-3 사유와 일치 |

train 정답지의 메시지 적재(FR-035 처리 6번): W6과 W5에서 INQUIRY, INFO_REQUEST SENT(시각 = first_response_at_utc, info_request_sent = Y일 때), FINAL_REPLY SENT(시각 = resolved_at_utc, final_reply가 있을 때)를 만든다. 본문이 없는 1차 응답은 만들지 않는다.

---

## 10. 채점 배치 (W4, 기획서 v1.4 10장)

평가 러너(FR-042)는 추가 개발이다. 그 전까지는 같은 항목을 이 채점 배치로 돌린다(기획서 10-1 "평가 러너가 늦으면 같은 항목을 채점 배치로 돌린다"). 실행·결과는 처음부터 eval 스키마의 `eval_run`(실행 1회)·`eval_case`(티켓 × 항목)·`eval_summary`(항목별 집계)에 쓴다(DB 설계 이유서 §5, stage = 0 정답지). 평가 러너(FR-042)는 같은 표에 stage = 2(운영 확정분)로 쓴다.

### 10-1. 실행 방식

1. 입력: gold에서 `data_split = test`(최종 1회) 또는 `valid`(사전 점검, 반복 가능) 행의 입력 열 6개. 제목·정답 열은 넣지 않는다.
2. 같은 파이프라인 코드를 scoring 스키마로 돌린다. 서비스 DB(svc)에는 아무것도 쓰지 않는다. 자동 발송 판정은 돌리되 SENT는 scoring에만 쓴다.
3. SLA·상태 항목은 파이프라인 결과가 아니라 **정답지의 시각으로 재생**해 계산식만 채점한다(AC-026-6): received_at, first_response_at_utc, resolved_at_utc, customer_wait_hours를 대기 구간 하나로 넣고 `inquiry_sla(스냅샷)`을 부른다. 목표 시간은 정답 우선순위(조정 건은 조정값, AC-028-3)로 조회한다.
4. 출력: `eval_case`(행 × 항목: 기대값·실제값·일치 여부, DRAFT만 채점용 LLM의 score·judge_comment)와 `eval_summary`(항목별 일치율·정밀도·재현율, 제외 건수, 언어별·유형별 분해). 같은 내용을 `scoring_{split}_{날짜}.csv`로도 내보낸다.

### 10-2. 채점 항목

| 항목 | 정답 열 | 비교 단위 | 기준 (기획서 10-2) |
|---|---|---|---|
| 문의 유형(단일) | category_code | 티켓 | ≥ 95% (잠정, D9) |
| 문의 유형(복합) | {category_code, secondary_category} 집합 | 티켓, 순서 무관(string_agg) | ≥ 85% (잠정). test 중 복합 57건 |
| 긴급도 | urgency_flag | 정답 유형과 같은 하위 문의 | ≥ 90%, SAFETY 재현율 100%, SITE_DOWN ≥ 97% (잠정). 전체 4,000건 재현율도 따로 보고 |
| 우선순위 규칙 | priority_rule_id | 정답 유형과 같은 하위 문의 | 100% |
| 우선순위 | priority | 조정되지 않은 행(priority_adjusted_by_agent = N) | 100% |
| 부서 | routing_rule_id, assigned_dept | 유형과 반품 구분이 맞은 하위 문의 | 100% (D13) |
| 제공 항목 | provided_info 항목 이름 집합 | 하위 문의 | ≥ 90% (잠정) |
| 막는 정보 | missing_blocking_info | 하위 문의 | provided_info가 맞은 행 100%, 전체 ≥ 90% |
| SLA 목표 | sla_first_response_target_h, sla_resolution_target_h | 정답 우선순위로 재조회 | 100% |
| SLA 상태·경과 | sla_first_response_status, sla_resolution_status, sla_elapsed_hours | 정답 시각 재생 | 100% / 100% / 오차 0.1h |
| 근거 문서 | reference_doc_id (+ reference_section) | evidence_json의 상위 k개 포함(대표 1건 일치율도 따로) | ≥ 85% (잠정). test 중 값이 있는 행 586건 |
| 숫자 | 초안 숫자 vs 표 값 | 초안 | 100% (D14) |
| 초안 본문 | final_reply | 참고 점수만 | 기준 없음(AC-021-5) |
| 복합 답변 | 하위 문의마다 단락 또는 상태 목록 줄, 인용이 그 하위 문의 후보 안 | 복합 티켓 | 단락·줄 ≥ 95%, 인용 100% (잠정, AC-022-5) |
| 고장 진단·이관 후보 | escalated, escalated_to, escalation_reason | 고장·설치·보증 하위 문의 / 정답에서 이관된 행 | 재현율 보고, 기준은 첫 채점 뒤(AC-018-5, AC-020-5) |
| 자동 발송 | (정답 없음) | 판정 로그 | 조건이 어긋난 초안의 자동 발송 0건(AC-041-6). 검증용 표본 검수로 "막았어야 할 건" 보고 |
| 상태 재생 | status | 스냅샷 시점 | 참고 지표(AC-025-5, 상태 이력이 데이터에 없음) |
| 전체 일치율 | 유형·긴급도·우선순위·부서·누락 정보 | 하위 문의 | 모두 맞은 비율을 함께 보고(기획서 10-2) |

### 10-3. 제외 목록 (eval.exclusion 한 표로 통합, D26)

`eval.exclusion`(ticket_id, item, reason, decided_on). 채점 스크립트는 이 표만 읽는다(파일 `scoring/exclusions.csv`는 적재 원본).

| 사유 | 대상 | 제외 항목 | 출처 |
|---|---|---|---|
| 펌웨어 시점 모순 | 57건 중 해당 split 행 | 펌웨어 답변 숫자 | D3, D26 |
| 고객 대기 시간 음수 | CSV1-003890(train), 003946(train), 003951(valid) | sla_elapsed_hours | D19 |
| NEW인데 대기 시간 있음, 막는 정보가 있는데 요청 미발송 | CSV1-003612(valid), 003913(test), 003950, 003967, 003995, 003999(train), 003984(valid) | sla_elapsed_hours, 정보 요청 관련 상태 재생 | D19, FR-013 데이터 주의 |
| 정답 없음 | 진행 안내, 복합 답변의 두 번째 하위 문의, 상태 전이 재생, 자동 발송 | 일치율 대신 생성·존재 기록 | D2, FR-022·025·041 |

D19의 NEW 7건과 FR-013 "데이터 주의"의 7건(막는 정보가 있는데 info_request_sent = N)은 같은 티켓들이다. test에는 CSV1-003913 한 건만 해당한다. 상태 값(sla_*_status)은 10건 모두 채점에 넣는다(D19).

---

## 11. 결정 필요 사항 (T24부터)

기획서·명세서의 D1~D29는 그대로이며, 이 문서와 관련 있는 것은 D8(Gemini), D9(기준 수치), D13(반품 구분), D14(견적), D15~D18(복합 문의), D20~D22(해결·종료·1차 응답), D23(로그인), D24(자동 발송), D25(미등록 고객), D26(채점 제외), D27(few-shot 출처), D29(리마인드)다. 시스템구성 문서가 "먼저 정해야 하는 것"으로 꼽은 6개 중 임베딩 모델·LLM 배분은 D8로 공급사가 정해졌고 모델 이름만 T38로 남았다. 나머지는 T32(TicketState), T35(청크 단위·분류 스키마), T36(외부 연계)이다.

| 번호 | 항목 | 어디에 영향 | 누가 답하나 | 상태 / 결정 전 진행 방식 |
|---|---|---|---|---|
| T24 | FR-004~007을 LLM 호출 한 번(L1)으로 묶을지 | 비용, 분류 정확도 | 팀(AI) | 묶는다. valid 유형 일치율이 95% 미만이면 긴급도를 떼어 비교 |
| T25 | 다국어 검색 방식(영어 검색문 vs 다국어 임베딩) | 근거 문서 적중률 | 팀(AI) | 영어 검색문(L1의 query_en). valid에서 두 방식 비교 |
| T26 | 확신도 기준값 | "확신 낮음" 표시 빈도, 자동 발송 보류 빈도 | 팀 | 0.6(기획서 5-5 제안). valid 첫 채점 뒤 구간별 일치율로 조정 |
| T27 | 검색 k와 근거 없음 점수 기준 | 근거 적중률, 엉뚱한 근거 | 팀(AI) | k = 5, 점수 기준 없음(빈 결과만 근거 없음). valid 점수 분포로 정함 |
| T28 | 복합 답변 메일의 인사말·맺음말을 LLM으로 할지 템플릿으로 할지 | 단락 보존, 비용 | 팀 | 템플릿 결합 + 인사말·맺음말만 L5. 단락은 글자 그대로 |
| T29 | 반품 비불량·불량 단어 목록 | 부서 일치율(반품) | 팀 | §5-3 목록. train 반품 행으로 점검 |
| T30 | 시간 상한, 동시 호출 수, 점검 주기 | 안정성, 비용 | 팀(BE) | 호출 30초 / 하위 문의 120초 / 티켓 180초(기획서 5-5 제안), 전체 동시 호출 4, 점검 5분. 티켓 내 병렬 수는 D18로 상한 없음 |
| T31 | 실행 로그 보존 기간, 전문 저장 | 저장 용량, 디버깅 | 팀(DB) | 90일, 전문 저장 꺼짐 |
| T32 | TicketState / SubTicketState 필드 | 모든 노드의 계약 | 팀 전원(공통 인터페이스 합의) | §2-3 목록 |
| T33 | 우선순위·이관 후보 조건 표현 방식 | 규칙 변경 용이성 | 팀(BE·DB) | 조건 표(priority_rule_urgency, priority_rule_category, 이관 행 조건 표) |
| T34 | 상태 이력 기록 방식(앱 vs DB 트리거) | 과거 시각 재현 | 팀(DB) | 앱의 전이 함수가 사건 시각으로 기록(테이블 정의서 v1.1 함수와 같음) |
| T35 | 청크 단위와 분류 출력 스키마 | 검색, 분류 | 팀(AI) | 절(`##`/`###`) 단위, §3-2 L1 스키마 |
| T36 | 외부 연계 인터페이스 | 확장 | 팀 | 별도 어댑터 없이 OpenAPI의 접수·회신 주소를 연계 지점으로 둠(FR-037 범위 밖, 기획서 6-3) |
| T37 | 접수함 시연 데이터를 train 미해결 243건으로 | 시연, 정답지 격리 | — | **확정**(명세서 v1.2 AC-029-1·034-1·2, 2026-10-12). W6 |
| T38 | Gemini 모델 이름(소형·상위)과 임베딩 모델 이름·차원 | 비용, 품질, doc_chunk·fault 벡터 열 차원 | 팀(AI), 2026-10-15 공통 인터페이스 합의까지 | 환경 변수로 두고 값만 바꾼다. 정해지기 전에는 색인(W2)을 시작할 수 없다(기획서 9-4) |
| T39 | 고장 증상 검색의 후보 수와 "관련성 낮음" 점수 기준 | 진단 후보 품질 | 팀(DB·AI) | 후보 3, 점수 기준 없음(빈 결과만 진단 없음). train 고장 행으로 분포를 본 뒤 정함 |
| T40 | 문의 상태 목록(FR-022)과 리마인드(D29)의 15개 언어 고정 문안을 누가 쓰나 | 복합 답변·리마인드 | 팀(AI, 다국어 검수) | 영어 원문을 팀이 쓰고 14개 언어는 LLM으로 한 번 번역해 파일(`templates/`)로 고정. 사람이 검수한 뒤 바꾸지 않는다 |
| T41 | 추가 개발 표(agent_feedback, eval_run·eval_case·eval_summary, prompt_example)를 지금 만들지, 추가 개발 시작 때 만들지 | DB 생성 SQL | 팀(DB) | 지금 만든다(DB 설계 이유서 §5의 평가 ERD, 테이블 정의서 v1.1 07_eval_schema.sql). MVP 코드는 self_check·exclusion만 쓴다 |
| T42 | 답변 근거 저장 방식 | 근거 탭, "왜?", 채점 | 조장 | **확정**(2026-10-14): 별도 표 없이 `sub_ticket.evidence_json` 1열. reference_doc_id·reference_section은 대표 1건. 규칙·추출·진단·이관 근거는 agent_step.output_json, 자체 검사는 self_check |

---

## 12. 추적표 (FR → 기술 요소)

| FR | 이름 | 노드·호출 | 표 | API·화면 |
|---|---|---|---|---|
| 001 | 문의 접수 | T1 | ticket, sub_ticket(seq 1), ticket_message, ticket_status_history | POST /tickets, /intake |
| 003 | 시연용 불러오기 | — | gold.v_train_inputs | GET /gold/train/{id} |
| 004 | 언어 식별 | T2(L1) | ticket.body_language | 상세 왼쪽 |
| 005 | 유형 분류 | T2(L1) | sub_ticket.category_code, evidence_sentences, agent_step | 상세 가운데 |
| 006 | 문의 분리 | T2(L1), T3 | sub_ticket(seq), ticket.multi_yn | 상세 하위 문의별 구역, 접수함 "복합 n건 중 k" |
| 007 | 긴급도 | T2(L1) | sub_ticket.urgency_flag | 상세 가운데 |
| 008 | 제공 항목 추출 | Q1(L2) | inquiry_field | 상세 왼쪽 강조 |
| 010 | 고객·제품 조회 | Q2 | ref.customer, ref.product | 상세 머리 |
| 011 | 우선순위 | Q3 | ref.priority_rule(+조건 표) | "왜?" |
| 012 | 부서 배정 | Q4 | ref.routing_rule, config/return_reason_words.yaml | "왜?" |
| 013 | 필수정보 | Q5 | ref.required_info_field | 체크리스트 |
| 014 | SLA 목표 | Q6 | ref.sla_policy → sub_ticket | 상세 SLA |
| 015 | 정보 요청 문안 | Q7(L3) | ticket_message(INFO_REQUEST, DRAFT) | 정보 요청 탭 |
| 016 | 문서 검색 | Q8 | ref.doc_chunk, sub_ticket.evidence_json(+ reference_doc_id·reference_section) | 근거 탭 |
| 017 | 숫자 조회 | Q9 | ref.product, product_spec, firmware_release | "표에서 읽은 값" |
| 018 | 고장 진단 | Q8a | ref.fault, fault_product, agent_step.output_json | 상세 "고장 진단 후보" |
| 020 | 이관 후보 표시 | Q9a | ref.routing_rule(ESCALATION 3행), agent_step.output_json | 상세 "이관 후보: {부서} — {rule_id}" |
| 021 | 답변 초안 | Q10(L4), Q11 | ticket_message(FINAL_REPLY, DRAFT), self_check(DRAFT_CHECK) | 답변 탭 |
| 022 | 복합 문의 답변 구성 | T5(L5) + 상태 목록 템플릿 | ticket_message(FINAL_REPLY, sub_ticket_id 포함) | 답변 탭(하위 문의별 메일) |
| 023 | 진행 안내 | T6(L6), 스케줄러(리마인드) | ticket_message(PROGRESS_NOTICE, notice_transition) | 진행 안내 탭 |
| 024 | 근거 표시 | — | sub_ticket.evidence_json, agent_step.output_json, self_check | "왜?" 팝오버 |
| 025 | 상태·이력 | transition() | sub_ticket.status, ticket_status_history, status_transition | 이력 띠 |
| 026 | SLA 계산 | SQL 함수 inquiry_sla(as_of) | (계산) | 두 시계 |
| 027 | SLA 경고 | 스케줄러 1 | sla_alert | 접수함 정렬·아이콘, 대시보드 |
| 028 | 우선순위 조정 | Q6 재실행 | priority_adjustment(별도 표 여부 확인 필요) | POST /sub-tickets/{id}/priority |
| 029 | 접수함 | — | v_inquiry_inbox | GET /tickets, /inbox |
| 030 | 티켓 상세 | — | v_ticket_summary(머리), 읽기 | GET /tickets/{id}, /tickets/:id |
| 031 | 승인·발송 | 자체 대조 | ticket_message(SENT), transition | POST /messages/{id}/send |
| 032 | 고객 회신 | Q1부터 재실행 | ticket_message(CUSTOMER_REPLY), inquiry_field | POST …/replies |
| 033 | 이관 처리 | API(그래프 없음), T6 ② | sub_ticket.escalated·escalated_to·escalation_reason, ticket_message(ESCALATION_NOTE), ticket_status_history(ESCALATE 행 = 시각·주체) | POST /sub-tickets/{id}/escalate, /dept-reply, [이관] 버튼 |
| 034 | 운영 대시보드 | — | sla_alert, v_inquiry_inbox, inquiry_sla, eval_summary(추가 개발) | GET /dashboard/*, /dashboard |
| 035 | 메시지 이력 | 저장 계층 | ticket_message | 이력 띠 |
| 036 | 실행 로그 | 노드 감싸기 함수 | agent_run, agent_step | 처리 기록 탭 |
| 038 | 마스킹 | mask_text | 모든 저장 경로 | "마스킹됨 n곳" |
| 039 | 초안 대역 표시 | Q13(L7) | message_gloss | 초안 옆 대역, POST /messages/{id}/gloss |
| 041 | 자동 발송 판정 | Q12 | ticket_message(SENT, SYSTEM; auto_send_hold), self_check, agent_step | 접수함 "자동 발송됨", 상세 "자동 발송 보류: {이유}" |

**추가 개발(그룹 7)의 자리**

| FR | 이름 | 들어올 자리 |
|---|---|---|
| 019 | 유사 해결사례 검색 | Q8b(§4-7), gold.resolution_case 색인, agent_step.output_json |
| 042 | 평가 러너 | §10 채점 배치와 같은 eval_run·eval_case·eval_summary에 stage = 2로 쓰고 실행 API를 둔다 |
| 043 | 상담원 수정·승인 기록 | agent_feedback(§6-2), 승인·조정·이관 API가 한 줄씩 쓴다 |
| 044 | 주간 품질 추이 | 스케줄러 주 1회 → FR-042를 agent_feedback 기준으로 실행 → eval_summary, GET /dashboard/quality-trend |
| 045 | 실시간 자체 검사 경고 | Q11 뒤 검사 묶음, self_check 행 → §5-7 조건 ③ |
| 046 | few-shot 예시 자동 선택 | L1·L4 프롬프트 조립 단계, train + ADOPTED agent_feedback만 후보(D27) |

---

## 13. 작성 중 확인한 사항 (기획서·명세서·DB 문서와 다른 점)

아래는 다른 문서를 고치지 않고 적어 둔 것이다. 반영이 필요하면 before/after를 따로 만들어 승인을 받는다.

| 번호 | 대상 | 확인한 사실 | 이 문서의 처리 |
|---|---|---|---|
| F-01 | 명세서 그룹 3 "문서 사실" | "제품 문서 92개(제품 23종 × DS·IG·TG·RN)"라고 적혀 있으나, doc_index.csv 기준 92개 = DS 23 + IG 23 + TG 23 + RN 13 + MG(정비 안내) 10이다. RN은 펌웨어 있는 13개 제품에만 있고, MG는 명세서에 나오지 않는다 | §4-1 표와 검색 범위에 MG 포함 |
| F-02 | 명세서 그룹 3 MANUAL 근거 문서 | "MANUAL → IG/TG/RN"이지만 정답지 MANUAL 근거는 IG 110, TG 85, RN 45, DS 44, MG 41이다 | MANUAL 우선 종류를 IG, TG, RN, DS, MG로 둠(§4-4) |
| F-03 | 명세서 그룹 5 AC-029-1 | v1.0 작성 때 "정답지 미해결 365건"이었으나 명세서 v1.2에서 train 243건으로 고쳐졌다 | 해결됨. T37 확정, W6 |
| F-04 | 명세서 FR-008, FR-012 | 정답지 provided_info에는 항목 이름만 있고 값(예: return_reason의 문장)은 없다 | 추출 채점은 항목 이름 집합으로만. 반품 단어 규칙 점검은 정답 routing_rule_id로(§5-3) |
| F-05 | 기획서 D19와 명세서 FR-013 데이터 주의 | 두 곳의 "7건"은 같은 티켓들이다(NEW, 막는 정보 있음, 요청 미발송, 대기 시간 있음) | 제외 목록에서 한 사유로 묶음(§10-3) |
| F-06 | 견적 유효기간 30일의 출처 | 명세서 FR-021의 "유효기간 30일"은 POL-ORDER §5에 근거가 있다 | QUOTE 초안이 POL-ORDER §5를 항상 인용(§3-3) |
| F-07 | 테이블 정의서 v1.1 vs ticket/sub_ticket 분리안·ERD v1 | 테이블 정의서 v1.1은 `ticket_inquiry`(PK ticket_id, seq)·`priority_change`·`inquiry_evidence`·`doc_candidate`이고 ticket에 category_code(';')가 남아 있다. ERD v1(2026-10-14)은 `sub_ticket`(PK sub_ticket_id = ticket_id-seq), ticket 13열, 이력 표 5개(ticket_message, ticket_status_history, priority_adjustment, sla_alert, sub_ticket_evidence), agent_run/agent_step이다. 2026-10-14 조장 결정: sub_ticket_evidence 표는 두지 않고 `sub_ticket.evidence_json` 1열로(T42); sub_ticket_id는 문자열 `ticket_id-seq` 유지(DB 쪽의 정수 대리키 안은 되돌림). DB 설계 이유서 v1.1 §6이 §6-2 추가 제안 21건을 반영 15 / 보류 4 / 제외 2로 판단했고(조장 확인 전), §5에 평가 표 7개를 더했다. 남은 조장 확인 항목: priority_adjustment를 별도 표로 둘지(§7-1), 반영 예정 묶음을 ERD v1.2에 언제 그릴지(§7-3) | 이 문서는 §6-2에 그 판단을 함께 적었다(반영 예정 / 보류 / 제외). 테이블 정의서·SQL·ERD v1.2 반영은 DB 담당이 맞춘다 |
| F-08 | 기획서 7-1·7-5 vs 기술 명세서 v1.0 | 기획서는 화면 4개(운영 대시보드 포함), v1.0은 3개 | 4개로 맞춤(§1-1, §8-2) |
| F-09 | 기획서 5-3·D18 vs v1.0 | 기획서는 나누는 수 상한 없음, v1.0은 n ≤ 3 | 상한 없음으로 맞춤. 동시 실행은 서버 전체 동시 호출 수(4)로만 제한(§2-4) |
| F-10 | 기획서 D8 vs v1.0 §3-5 | 기획서는 Gemini 확정, v1.0은 Claude 후보와 Voyage/bge-m3 후보 | Gemini로 맞춤. 모델 이름·차원은 T38 |
| F-11 | 기획서 7-5 그림 | 그림의 서버 상자에 자동 발송 판정(규칙), 고장 사전 조회(검색), 대역 번역(LLM 호출 계층), 스케줄러의 리마인드·해결 뒤 종료가 글자로는 없다. 7-4에는 비기능(5-5)이 어느 구성 요소에서 지켜지는지와 실행·배포 구성이 없다 | 이 문서 §1-1 범례, §1-4, §1-5로 보완. 기획서 그림을 고칠지는 조장 판단(이 문서는 기획서를 고치지 않음) |
| F-12 | 명세서 FR-030 9번 | "번역 토글(원문의 한국어 번역)은 여유 시 항목"이고, FR-039는 초안 대역이다. v1.0은 둘을 묶어 "만들지 않는다"고 썼다 | 초안 대역은 만들고(Q13, L7), 원문 번역 토글만 여유 시 항목(§8-2) |
| F-13 | 명세서 FR-033 이관 사유 | 명세서는 "ONSITE_REQUIRED … 등 정답지의 값"이고 테이블 정의서 v1.1은 11개 값으로 고정했다 | 11개 값을 쓴다(§6-2). 선택 부품은 이 목록으로 만든다 |