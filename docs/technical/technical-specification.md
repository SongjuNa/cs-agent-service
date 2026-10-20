# 기술 명세서 v1

결과: 해결 중
구분: 설계
버전: v1
상태: 작성 중
생성일: 2026/10/10
종류: 산출물

# 기술 명세서 — 해외고객향 C/S 대응 AI Agent

| 항목 | 내용 |
| --- | --- |
| 작성일 / 버전 | 2026-10-10 / v1.0 초안 (검토 대기) |
| 함께 보는 문서 | 프로젝트 기획서 v1(무엇을, 왜), 기능 요구사항 명세서 FR 30개(기능별 입력·처리·출력·완료 기준) |
| 이 문서가 정하는 것 | 구현 방식: 시스템 구성, 처리 흐름, LLM 호출, 검색, 규칙 엔진, 저장 구조, 마스킹, API·화면, 기능이 아닌 작업 |
| 근거 데이터 | 학습 데이터 v1: README.html, tickets.csv 4,000건(train 2,800 / valid 603 / test 597), ref/ CSV 12개, docs/ 107개(doc_index.csv) |
| 팀 문서 인용 | "팀 정리 §n" = 팀공유_데이터분석_정리.md, "추적표 §n" = 추적표_9건 [1.md](http://1.md/) |

이 문서의 뼈대는 기획서 검토(STEP 6 §2)가 "기술 설계서 대상"으로 넘긴 여덟 묶음이다: LLM 호출, 검색, 규칙, 흐름, 저장, 마스킹, 화면, 작업. 각 절은 관련 FR 번호를 달아 기능 명세서와 연결하고, 끝의 §12 추적표에서 FR마다 어느 기술 요소가 맡는지 한 번에 볼 수 있다.

---

## 0. 용어 (개발 경험이 없는 팀원용)

스케줄러(주기 작업)의 경우 구현 방식이 향후 변경될 여지가 존재한다.

| 용어 | 뜻 |
| --- | --- |
| API | 화면(React)이 서버(FastAPI)에 일을 시키는 창구. "주소 + 보내는 값 + 돌려받는 값"의 약속이다. 예: `POST /tickets`는 "티켓을 새로 만들어 줘" |
| 파이프라인 | 문의 한 건이 접수부터 초안까지 거치는 단계의 묶음. 이 프로젝트는 문의(복합이면 나눈 문의)마다 하나씩 돈다 |
| 노드 | 파이프라인의 한 단계. 예: "우선순위 계산 노드" |
| 상태 객체(TicketState / InquiryState) | 파이프라인의 노드들이 돌려 쓰는 공용 메모지. 앞 노드가 적은 값(유형, 우선순위 …)을 뒤 노드가 읽는다 |
| LangGraph | 노드와 노드 사이의 화살표(분기 포함)를 그림처럼 정의해 실행해 주는 Python 라이브러리 |
| 구조화 출력 | LLM이 자유 문장 대신 정해진 칸(JSON)에 정해진 코드값만 채워 답하게 하는 방식 |
| 임베딩 / 벡터 검색 | 글을 "뜻이 비슷하면 가까운 숫자 묶음"(벡터)으로 바꿔 두고, 질문과 가장 가까운 글을 찾는 방식 |
| pgvector | PostgreSQL 안에 벡터를 저장하고 검색하게 해 주는 확장 기능 |
| 청크(chunk) | 검색 단위로 자른 문서 조각. 이 프로젝트에서는 문서의 절(`##`, `###`) 하나 |
| 뷰(view) / SQL 함수 | 값을 저장하지 않고 볼 때마다 다시 계산하는 가상의 표 / 계산식 |
| 스케줄러(주기 작업) | 정해진 간격(예: 5분)마다 자동으로 도는 작업. SLA 경고에 쓴다 |
| 스키마(schema) | DB 안의 칸막이 공간. 같은 DB 안에서 표 묶음을 서로 섞이지 않게 나눈다 |
| 1차 응답 | 접수 뒤 고객에게 처음 보내는 답변 또는 추가정보 요청(README 용어). 접수 확인 안내는 포함하지 않는다(D21) |
| 스냅샷 | 정답지의 "지금" = 2026-09-30 23:59 UTC. 정답지와 비교할 때만 이 시각으로 고정한다 |

---

## 1. 시스템 구성

### 1-1. 전체 구조

```
[React 화면 3개]  접수 시뮬레이터 / 접수함 / 티켓 상세
        │  HTTP API (JSON, OpenAPI 문서 자동 생성)
[FastAPI 서버 (Python 한 프로세스)]
   ├─ 처리 흐름 실행기 (LangGraph): 티켓 그래프 1개 + 문의 그래프 n개(병렬)
   ├─ LLM 호출 계층: 호출 6종(§3), 재시도·시간 상한·마스킹·사용량 기록을 한곳에서
   ├─ 규칙 엔진: 표 조회만, LLM 없음(§5)
   ├─ 검색: 문서 절 검색(§4), 숫자 표 조회(§5-5)
   ├─ 저장 계층: 모든 쓰기가 마스킹 검사를 거친다(§7)
   └─ 스케줄러: 5분마다 SLA 경고·무응답 종료 점검(§6-4)
[PostgreSQL 16 + pgvector]
   ref 스키마     기준정보·규칙표 23개(ref/ CSV 12개 적재)
   svc 스키마     티켓·문의·메시지·상태 이력·경고·근거·실행 로그·문서 청크
   gold 스키마    tickets.csv 4,000건 원본(읽기 전용, 채점·불러오기용)
   scoring 스키마 채점 배치 전용(서비스 표와 같은 모양, 실행마다 비움)
[외부] LLM API, 임베딩 API (D8). 그 밖의 외부 연동 없음
```

![React·FastAPI·PostgreSQL 시스템 아키텍처.png](%EA%B8%B0%EC%88%A0%20%EB%AA%85%EC%84%B8%EC%84%9C%20v1/ReactFastAPIPostgreSQL_%E1%84%89%E1%85%B5%E1%84%89%E1%85%B3%E1%84%90%E1%85%A6%E1%86%B7_%E1%84%8B%E1%85%A1%E1%84%8F%E1%85%B5%E1%84%90%E1%85%A6%E1%86%A8%E1%84%8E%E1%85%A5.png)

### 1-2. 기술 스택

| 층 | 작업 가정 | 이 프로젝트에서 쓰는 이유 |
| --- | --- | --- |
| 서버 | Python 3.11 + FastAPI + Pydantic v2 | 상태 객체를 Pydantic 모델로 두면 파이프라인 입출력·API 응답·로그가 같은 모양이 된다 |
| 처리 흐름 | LangGraph | 분기 6개와 문의별 병렬 실행을 그래프로 표현하고, 노드마다 실행 로그를 남기기 쉽다 |
| DB | PostgreSQL 16 + pgvector | 규칙표, 티켓, SLA 계산, 벡터 검색을 한 DB에서 조인한다. SLA 판정식은 이 DB에서 정답지 4,000건과 상태 4,000/4,000, 경과 3,997/4,000 일치를 확인했다(3건은 고객 대기 시간 음수, D19) |
| 화면 | React + Vite + TypeScript, TanStack Query·Table | 티켓 상세의 세 칸 + 이력 띠(FR-030)를 자유롭게 배치 |
| LLM·임베딩 | gemini-3.8-flash, gemini-embedding-001 | §3-5, §4-3 |
| 실행 환경 | Docker Compose: db(postgres+pgvector), api, web | 4명이 같은 환경에서 실행 |

### 1-3. 설계 원칙 (팀 정리 §3의 8개를 기술 규칙으로)

| 팀 정리 §3 원칙 | 이 문서에서 지키는 방법 |
| --- | --- |
| 1 고객 언어로 답변 | 초안·정보 요청·진행 안내 호출(L3~L6)의 출력 언어 = language. 본문 해석은 body_language(§3) |
| 2 우선순위·라우팅·SLA는 규칙표, LLM은 읽기·쓰기만 | 규칙 노드(§5)는 LLM 호출 계층을 import하지 않는다. 코드 리뷰 체크 항목으로 둔다 |
| 3 답변은 문서 근거만 | 초안은 근거 후보 절과 조회값만 입력으로 받고, 생성 뒤 자체 대조(§3-4)로 인용·숫자를 검사 |
| 4 펌웨어는 release_date ≤ 접수일 | 숫자 조회의 SQL 조건으로 고정(§5-5) |
| 5 결함 진단 없으면 유사 사례 검색 생략 | MVP는 유사 사례 검색(FR-019)과 고장 진단(FR-018)을 만들지 않는다. 확장 때 DEFECT·INSTALL·WARRANTY·FW_UPDATE·RETURN 문의에서만 노드를 켠다 |
| 6 상담원 우선순위 조정(사유 필수) | `priority_change` 표 + 조정 API(§6, §8) |
| 7 사람 승인·발송 | 고객에게 나가는 글은 `message_status = DRAFT`로만 생성. SENT 행은 승인 API만 쓴다(§6-3) |
| 8 가격·납기는 제품 마스터 조회 | 숫자 조회(§5-5)와 숫자 자체 대조(§3-4) |

---

## 2. 처리 흐름 (FR-001, 004~008, 010~017, 021~023, 036)

### 2-1. 두 겹 그래프

복합 문의(FR-006)를 문의별로 병렬 처리하기 위해 그래프를 둘로 나눈다.

```
[티켓 그래프]  (티켓 1건에 1번)
  T1 마스킹·입력 고정 → T2 문의 이해(L1: 언어·분리·유형·긴급도) → T3 문의 그래프 n개 병렬 실행(n ≤ 3)
  → T4 결과 모으기 → (복합이면) T5 답변 병합(FR-022) → T6 상태 NEW→IN_PROGRESS + 진행 안내 초안(FR-023 ①)

[문의 그래프]  (나눈 문의 1개에 1번, seq = 1..n)
  Q1 제공 항목 추출(L2, FR-008) → Q2 고객·제품 조회(FR-010)
  → Q3 우선순위(FR-011) → Q4 부서(FR-012) → Q5 필수정보(FR-013) → Q6 SLA 목표(FR-014)
  → 분기③ 막는 정보 있음? ─ 예 → Q7 정보 요청 문안(L3, FR-015) → 끝
                          └ 아니오 → Q8 문서 절 검색(FR-016) → Q9 숫자 표 조회(FR-017)
                                     → 분기④ 근거 있음? ─ 아니오 → "근거 없음" 표시 → 끝
                                                       └ 예 → Q10 답변 초안(L4, FR-021) → Q11 자체 대조 → 끝
```

- 긴급도(FR-007)는 FR-005와 같은 호출(L1)에서 문의마다 받는다. 그래서 문의 그래프에는 긴급도 노드가 따로 없다(FR-005·006·007이 "같은 호출로 묶어도 된다"고 허용, D24).
- 단일 문의는 n = 1인 경우일 뿐 같은 그래프를 탄다. 따로 분기하지 않는다.
- 단계 순서는 고정한다. LLM이 다음 도구를 고르는 방식(에이전트가 도구를 스스로 선택)은 쓰지 않는다. 이유: 규칙 순서(고객→제품→종류/긴급도→우선순위→부서→필수정보→답변근거→SLA→결과)가 규칙표의 열쇠 때문에 강제되고(추적표 §1), 실행 로그와 채점이 단계 단위로 비교되어야 한다.

### 2-2. 노드 목록

| 노드 | FR | 종류 | 입력(상태 객체에서 읽음) | 출력(상태 객체에 씀) | 실패 시 |
| --- | --- | --- | --- | --- | --- |
| T1 입력 고정 | 001, 038 | 코드 | 접수 입력 | 마스킹된 본문, 마스킹 수 | 저장 거부(§7) |
| T2 문의 이해 | 004~007 | LLM L1 | 본문, language, channel, product_family | body_language, inquiries[] (seq, category_code, 확신도, 근거 문장, urgency_flag, 영어 검색문) | 1회 재시도 → 티켓 NEW 유지, run FAILED, "다시 시도" |
| T3 병렬 실행 | 006 | 실행기 | inquiries[] | 문의별 결과 | 실패한 문의만 표시, 나머지 계속 |
| Q1 추출 | 008 | LLM L2 | 그 문의의 근거 문장 + 원문, 필수 항목 목록 | provided_fields[], product_code 보완, error_code, current_fw, return_reason(영어 정규화) | 빈 목록 + "추출 실패", 계속 |
| Q2 고객·제품 | 010 | 표 조회 | customer_id, product_code | tier, segment, country, family, 제품 값 | 고객 없음 → 멈춤 / 제품 없음 → Q4·Q5 "제품 확인 필요" |
| Q3 우선순위 | 011 | 규칙 | category_code, urgency_flag | priority_rule, rule_id, 판정 과정 | 행 없음 → 비움 |
| Q4 부서 | 012 | 규칙 | family, category_code, return_reason | assigned_dept, routing_rule_id, 이관 조건, 반품 구분 | 행 없음 → 비움 + GCS_L1 표시 |
| Q5 필수정보 | 013 | 규칙 | family, category_code, provided_fields | missing_info, missing_blocking_info | 제품·유형 없음 → 실행 안 함 |
| Q6 SLA 목표 | 014 | 규칙 | category_code, tier, priority(최종) | sla_id, 두 목표 시간 | 비움, "SLA 미정" |
| Q7 정보 요청 | 015 | LLM L3 | 막는·빠진 항목 + 라벨, language, channel | INFO_REQUEST DRAFT 1건 | 영어 고정 문구 |
| Q8 문서 검색 | 016 | 검색 | 영어 검색문, 원문 문장, 유형, product_code, family, error_code, current_fw | 근거 후보 ≤ k개 | 1회 재시도 → "검색 실패", 근거 없음 |
| Q9 숫자 조회 | 017 | 표 조회 | product_code, 유형, received_at, quantity, current_fw | 조회값 묶음 + 출처 | 값 비움 + "표에 없음" |
| Q10 초안 | 021 | LLM L4 | 근거 후보, 조회값, language, 유형 뼈대 | 초안(단일=완성문, 복합=단락), 인용 | 1회 재시도 → 초안 없음 |
| Q11 자체 대조 | 021 | 코드 | 초안, 근거 후보, 조회값 | 대조 결과, 불일치 위치 | 1회 재생성 → 불일치 강조 |
| T5 병합 | 022 | 코드 + LLM L5 | 문의별 단락 | FINAL_REPLY DRAFT 1건 | 템플릿 인사말로 대체 |
| T6 진행 안내 | 023, 025 | 코드 + LLM L6 | 전이 사건 | PROGRESS_NOTICE DRAFT | 영어 고정 문구 |

### 2-3. 상태 객체 (D32: TicketState 필드 확정)

LangGraph 노드끼리 넘기는 값이다. DB 표(§6)와 이름을 맞춘다. 아래는 결정 전 진행 방식의 필드 목록이다.

```python
class InquiryState(BaseModel):          # 문의 그래프 1개의 메모지
    ticket_id: str
    seq: int                             # 1..n, 본문에 나온 순서
    category_code: str | None            # 10종 또는 None(분류 실패)
    category_confidence: float | None
    evidence_sentences: list[str]        # 이 문의의 근거 문장(본문 발췌)
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
    assigned_dept: str | None; routing_rule_id: str | None; escalation: EscalationHint | None
    missing_info: list[str]; missing_blocking_info: list[str]
    sla_id: str | None; fr_target_h: int | None; res_target_h: int | None
    doc_candidates: list[DocCandidate]   # {chunk_id, doc_id, section_no, title, score}
    lookups: list[LookupValue]           # {item, value, unit, source_table, source_key}
    draft_id: int | None; draft_check: DraftCheck | None
    flags: list[str]                     # "확신 낮음", "반품 사유 확인 필요", "근거 없음" …

class TicketState(BaseModel):            # 티켓 그래프의 메모지
    ticket_id: str; channel: str; customer_id: str; language: str
    body_language: str | None; body_language_uncertain: bool
    body_masked: str; received_at: datetime
    inquiries: list[InquiryState]        # n ≤ 3 (D18)
    split_check_needed: bool             # 4개 이상으로 나뉜 경우
    merged_draft_id: int | None
    run_id: int
```

제목(inquiry_subject)은 TicketState에 넣지 않는다. 그래서 어떤 노드도 제목을 읽을 수 없다(팀 정리 §6 제목 누설, AC-001-3).

### 2-4. 실행 방식, 시간 상한, 동시 실행 (D30)

| 항목 | 결정 전 진행 방식 (제안) | 근거 |
| --- | --- | --- |
| 실행 시작 | `POST /tickets`가 티켓·INQUIRY 메시지·상태 이력을 한 트랜잭션으로 저장하고 즉시 ticket_id를 돌려준다. 파이프라인은 서버 안의 백그라운드 작업으로 돈다 | 화면이 "처리 중"을 보여 주고(FR-001 6번) 결과를 다시 읽는다 |
| 화면 갱신 | 티켓 상세가 처리 중이면 2초마다 `GET /tickets/{id}`를 다시 읽는다. 끝나면 멈춘다 | 별도 실시간 연결(WebSocket) 없이 단순하게 |
| LLM 호출 1회 시간 상한 | 30초 | 넘으면 LLM_TIMEOUT, 1회 재시도 |
| 문의 그래프 1개 시간 상한 | 120초 | 넘으면 그 문의만 실패, 병합은 "확인 후 별도 안내"(FR-022 예외) |
| 티켓 전체 시간 상한 | 180초 | 넘으면 run FAILED, 티켓 NEW 유지 |
| 한 티켓 안 병렬 수 | 최대 3 (D18 상한과 같음) | — |
| 서버 전체 LLM 동시 호출 수 | 4 | LLM API 요금 한도·속도 제한 보호. 채점 배치는 별도 설정 |
| 재처리 | "다시 시도/다시 처리"는 새 run을 만든다. 이미 SENT인 메시지는 지우지 않고, 이전 DRAFT는 `SUPERSEDED`로 표시한다. 횟수 제한 없음 | FR-036 5번 |
| 부분 재실행 | 상담원이 유형·긴급도·제공 항목·제품을 고치면 그 문의의 Q2부터(유형·긴급도 수정) 또는 Q5부터(제공 항목 수정) 다시 돈다 | FR-010 AC-010-3, FR-013 5번, FR-030 6번 |
| 고객 회신 재처리 | 대상 문의의 Q1(원문 + 모든 회신)부터 다시 돈다. 제공 항목은 이전 값과 합집합 | FR-032 3번 |

### 2-5. 분기 6개의 구현 위치

| 분기 (STEP 6 1-4) | 조건 | 구현 |
| --- | --- | --- |
| ① 문의 나누기 | inquiries 수 ≥ 2 | T3이 문의 그래프를 n개 띄움. 4개 이상이면 앞 3개 + `split_check_needed` |
| ② 반품 사유 | category = RETURN이고 return_kind = NON_DEFECT | Q4의 규칙 조회 키를 RT-ALL-RETURN-NON_DEFECT로 바꿈(§5-3) |
| ③ 막는 정보 | missing_blocking_info ≠ [] | Q6 뒤 조건 화살표 → Q7 |
| ④ 근거 유무 | doc_candidates = [] 또는 모두 기준 점수 미만(D27) | Q9 뒤 조건 화살표 → 끝("근거 없음") |
| ⑤ 유형별 뼈대 | category_code 10종 | Q8의 우선 문서 종류표(§4-4), Q10의 뼈대 템플릿(§3-3) |
| ⑥ 고객 회신 | 회신 뒤 막는 항목이 남음 / 없음 | FR-032 재처리가 같은 문의 그래프를 다시 태우므로 ③이 그대로 판단 |

복합 문의에서 한 문의는 ③(정보 요청)으로, 다른 문의는 초안까지 간 경우: 정보 요청은 문의별 DRAFT로 먼저 상담원에게 보이고, T5 병합은 모든 문의가 초안(또는 근거 없음·실패)에 도달했을 때만 돈다(FR-022 처리 1번). 정보 요청 중인 문의가 회신으로 초안까지 가면 그때 T5를 다시 돌린다.

---

## 3. LLM 호출 (FR-004~008, 015, 021~023)

### 3-1. 호출 목록

| 호출 | FR | 한 티켓에서 | 입력 | 출력 언어 | 모델 등급 (D8 결정 전) |
| --- | --- | --- | --- | --- | --- |
| L1 문의 이해 | 004·005·006·007 | 1회 | 마스킹된 본문, channel, language, product_family(있으면), 유형 10종 정의(README §6), 긴급도 6값 설명(urgency_codebook.csv) | 코드값 + 원문 발췌 + 영어 검색문 | 소형 |
| L2 제공 항목 추출 | 008 | 문의마다 1회 | 원문 + 그 문의 근거 문장, 항목 코드북 32개(info_field_codebook.csv), 그 제품군×유형의 필수 항목(required_info.csv) | 값(원문 그대로) + 정규화 값 | 소형 |
| L3 정보 요청 문안 | 015 | 막는 정보가 있는 문의마다 1회 | 항목 이름 + 라벨, 제품명, 유형, channel, language | language | 상위 |
| L4 답변 초안 | 021 | 근거가 있는 문의마다 1회 | 근거 절 본문, 조회값, 유형 뼈대, 제공 항목, language, 모드(완성문/단락) | language | 상위 |
| L5 병합 인사말 | 022 | 복합 문의 티켓에 1회 | 티켓 요약, language | language | 소형 |
| L6 진행 안내 | 023 | 전이 ①③④마다 1회 | 전이 종류, 부서 이름, 다음 단계, language | language | 소형 |

D24(호출 묶음): FR-004~007을 L1 한 번으로 묶는 것을 결정 전 진행 방식으로 한다. 이유는 비용(티켓당 1회)과 일관성(유형과 긴급도를 같은 읽기에서 판단)이다. valid 603건에서 유형 일치율이 95%(D9)에 못 미치면 긴급도를 별도 호출로 떼어 비교한다.

### 3-2. 구조화 출력 스키마

모든 호출은 JSON 스키마를 강제한다(구조화 출력). 코드값 칸은 열거형(enum)으로 막아 10종·6값·15개 언어 밖의 값이 나오지 않게 한다. 스키마 검증에 실패하면 LLM_INVALID_OUTPUT으로 1회 재요청한다.

**L1 문의 이해 출력** (D35: 분류 출력 스키마 확정)

```json
{
  "body_language": "ar",
  "body_language_confidence": 0.97,
  "inquiries": [
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
- 티켓의 category_code는 문의 유형을 seq 순서로 ';'로 이은 문자열(예: "FW_UPDATE;MANUAL")로 저장한다. secondary_category 칸은 두지 않는다(기획서 부록 B 설계 변경).
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

### 3-3. 프롬프트 구성 원칙

프롬프트 파일은 저장소의 `prompts/` 폴더에 호출별로 두고 파일 이름에 버전을 붙인다(예: `l4_draft_v3.md`). 실행 로그에 프롬프트 버전을 남긴다(§6-5).

| 원칙 | 적용 |
| --- | --- |
| 규칙표의 정의를 그대로 넣는다 | L1에 README §6 유형 정의와 urgency_codebook.csv 설명 원문을 넣는다. 팀이 지어낸 정의를 쓰지 않는다 |
| 제목·정답 열은 넣지 않는다 | L1~L6 입력 목록에 inquiry_subject, 정답 열이 없다. 실행 로그에 입력 항목 이름 목록을 남겨 확인한다(AC-001-3) |
| few-shot(예시)은 train만 | 예시가 필요하면 train 행에서만 고른다. valid·test 행 문장은 프롬프트에 넣지 않는다 |
| 근거 밖 금지 | L4: "아래 절 본문과 조회값만 사실로 쓴다 / 숫자는 조회값만 / 문장 끝에 (DOC_ID §절) 인용 / 승인·거절·납기 확정 문구 금지" |
| 약속 금지 | L6: SLA 목표 시간, 예상 완료 시각을 쓰지 않는다(AC-023-3). L3: 추측한 값·기한 약속 금지 |
| 채널별 모양 | L3: CHAT 3문장 이내, PHONE은 고객 언어 + 영어 병기 체크리스트(FR-015 5번) |

**L4 유형별 뼈대 템플릿** (FR-021 4번을 그대로 템플릿 파일로)

| 유형 | 뼈대 | 필수 조회값 | 우선 인용 |
| --- | --- | --- | --- |
| QUOTE | 제품·수량·단가·합계·표준 납기·견적 유효기간 | list_price_usd, 합계, std_lead_time_weeks | POL-ORDER |
| ORDER_LEAD | 표준 납기(확정 출하일 금지) | std_lead_time_weeks, moq | POL-ORDER |
| TECH_SPEC, COMPLIANCE | 묻는 사양값 + 출처 절 + 데이터시트 첨부 안내 | product_spec_facts.csv 행 | DS |
| DEFECT, INSTALL | 원인 후보·점검 순서 | (없음) | TG, IG |
| FW_UPDATE | 현재 버전·접수 시점 최신·업데이트 또는 이미 최신 | firmware_history.csv 비교 결과 | RN |
| RETURN, WARRANTY | 정책 조항·필요 서류·판정은 사람이 한다는 안내 | warranty_months(WARRANTY) | POL-RETURN, POL-WARRANTY |
| MANUAL | 해당 문서 ID와 절 안내 | (없음) | IG, TG, RN, DS, MG |

견적 유효기간(정답지 final_reply의 "30일")은 POL-ORDER §5 "Quotations are valid for 30 days."에 있다. 그래서 QUOTE 초안은 이 절을 근거 후보에 항상 넣고 인용하며, 숫자 자체 대조는 근거 절 본문의 숫자로 30을 허용한다. 같은 절의 "Volume discounts apply"는 할인율이 표에 없으므로 숫자를 쓰지 않는다(D14).

### 3-4. 자체 대조 (LLM 아님, 코드)

FR-021 5번, FR-022 처리 4번, FR-031 처리 2번이 같은 함수를 쓴다.

1. **인용 검사**: 정규식으로 `(DOC_ID §n.m)` 꼴을 모두 찾는다. 각 (doc_id, 절)이 그 문의의 근거 후보에 있어야 한다. 복합 문의는 단락별로 그 문의의 후보와 대조한다.
2. **숫자 검사**: 초안의 숫자(정수, 소수, 천 단위 구분 포함, 언어별 소수점 표기 정규화)를 모두 뽑는다. 허용 목록 = 조회값 + 제공 항목 값(수량, 고객 버전, 날짜) + 인용 절 번호 + 근거 절 본문에 나오는 숫자. 허용 목록 밖 숫자가 있으면 불일치.
3. **누락 검사**: L3은 막는 항목 라벨이 본문에 있는지, T5는 단락 수 = 문의 수인지 본다.
4. 불일치면 1회 재생성. 다시 불일치면 초안은 두고 위치 목록을 `draft_check`에 저장해 화면이 강조한다.

### 3-5. 모델 선택과 예산

| 항목 | 결정 전 진행 방식 |
| --- | --- |
| 모델 배분 | gemini-3.8-flash |
| 비교 방법 | valid 603건 중 언어별 층화 표본 150건으로 L1 유형·긴급도 일치율, L4는 검수 30건(15개 언어 각 1건 이상, 기획서 2-2)으로 비교 |
| 비용 기록 | 모든 호출의 모델 이름, 입력·출력 토큰을 `agent_step`에 남겨 티켓당 비용을 계산(§6-5) |
| 대량 실행 | 채점 배치(valid·test 전량)는 공급사의 일괄 처리(Batch) 기능이 있으면 쓴다(시스템구성 문서: 반값) |
| 예산 상한 | 미정. 결정 전에는 실행 로그로 사용량만 집계해 주 1회 팀에 보고 |

### 3-6. 확신도 기준 (D26)

LLM이 스스로 매기는 확신도는 정확하지 않을 수 있어서 기준값은 데이터로 정한다.

- 결정 전 진행 방식: 언어 판정·유형 분류 모두 0.6 미만이면 "확신 낮음"/"언어 판정 불확실" 표시.
- 조정 방법: valid 첫 채점 뒤, 확신도 구간별 실제 일치율을 표로 만들어 "이 값 아래에서는 일치율이 90% 미만"인 지점으로 바꾼다.

<aside>
💡

채점 배치(valid·test 전량)

</aside>

---

## 4. 검색 (FR-016)

### 4-1. 문서 사실 (doc_index.csv와 docs/ 확인 결과)

| 종류 | 문서 수 | 범위 | 비고 |
| --- | --- | --- | --- |
| DS 데이터시트 | 23 | 제품별 | 사양 근거 |
| IG 설치·시운전 안내 | 23 | 제품별 |  |
| TG 트러블슈팅 | 23 | 제품별 | 고장 근거 |
| RN 릴리스노트 | 13 | 펌웨어 있는 제품만 |  |
| MG 정비 안내 | 10 | 일부 제품 | 명세서에는 언급 없음(§13 확인 사항 F-01) |
| POL 정책 | 4 | 전체 | POL-ORDER, POL-RETURN, POL-WARRANTY, POL-SERVICE |
| FAQ | 11 | 제품군별 | 절이 "## Q1." 꼴 |
| 합계 | 107 |  | 모두 영어 마크다운. 문서 길이 680~7,221자, 문서당 절 2~22개, 가장 긴 절 1,092자 |

정답지의 근거 문서 종류(tickets.csv reference_doc_id, 4,000건 중 값이 있는 행): TECH_SPEC·COMPLIANCE → DS, DEFECT → TG, INSTALL → IG 302 / TG 148, FW_UPDATE → RN, MANUAL → IG 110 / TG 85 / RN 45 / DS 44 / MG 41, QUOTE·ORDER_LEAD·RETURN·WARRANTY → POL. reference_doc_id에 문서가 둘 이상인 행은 없다.

### 4-2. 청크(절) 분할 (D35의 일부: 청크 단위)

- 단위: `##` 또는 `###` 머리글 하나 = 청크 하나. 가장 긴 절이 1,092자라 더 자르지 않는다. `##` 아래에 `###`가 있으면 `##` 머리글 바로 아래 글만 `##` 청크로 두고, 각 `###`는 따로 청크로 둔다.
- 청크 ID: `{doc_id}§{절 번호}` (예: `TG-ACB-AS-2000§3.1`, FAQ는 `FAQ-DRIVE§Q3`). 절 번호는 TEXT로 저장한다("2.10"이 2.1로 바뀌지 않게).
- 청크 앞에 문서 제목과 절 제목을 붙여 임베딩한다(예: "ACB 2000A Troubleshooting Guide > 3.1 Terminal overheating / discoloration\n본문 …"). 짧은 절도 무엇에 관한 절인지 드러나게 하기 위해서다.
- 꼬리표(메타데이터): doc_id, doc_type, product_code(정책·FAQ는 비움), family(정책은 비움), section_no, section_title, revision.
- 정답 절 일치 채점(AC-016-4)을 위해 reference_section 값(예: "3.1")과 청크의 section_no가 같은 표기여야 한다. 적재 때 train 정답의 (reference_doc_id, reference_section) 쌍이 모두 청크 ID로 존재하는지 검사한다(작업 W2).

### 4-3. 다국어 검색 방식 (D25, 결정 필요)

문서는 모두 영어이고 질문은 15개 언어다. 두 방식이 있다.

| 방식 | 내용 | 장점 | 단점 |
| --- | --- | --- | --- |
| A 영어 검색문 | L1 단계 문의를 영어로 번역한 뒤 임베딩 | 임베딩 모델 선택이 자유롭고, 키워드 검색도 영어로 된다. 추가 호출 없음 | L1이 번역을 잘못 쓰면 검색도 틀린다 |
| B 다국어 임베딩 | 원문 문장을 다국어 임베딩 모델로 바로 검색 | 요약 단계 오류가 없다 | 임베딩 모델이 15개 언어를 고르게 지원해야 한다. 키워드 보조가 영어 문서와 안 맞는다 |

결정 전 진행 방식: **A로 만들고**, 임베딩 모델은 B로 바꿀 수 있는 다국어 모델(D8 후보: Voyage AI 다국어 모델 또는 로컬 bge-m3)을 쓴다. valid에서 근거 문서 적중률(AC-016-4)을 A와 B로 한 번씩 비교해 정한다.

### 4-4. 검색 절차

1. **범위 좁히기(꼬리표 필터)**: `product_code = 문의의 제품` 인 청크 + `doc_type = POL` 4개 문서 + `doc_type = FAQ AND family = 문의의 제품군`. 제품이 없으면 POL + (제품군이 있으면) FAQ만, "제품 문서 미검색" 표시.
2. **우선 문서 종류**: 위 4-1의 유형별 종류를 먼저 검색. 결과가 없거나 모두 기준 미만이면 범위 전체로 넓힌다.
    
    
    | 유형 | 우선 종류 |
    | --- | --- |
    | TECH_SPEC, COMPLIANCE | DS |
    | DEFECT | TG |
    | INSTALL | IG, TG |
    | FW_UPDATE | RN |
    | MANUAL | IG, TG, RN, DS, MG |
    | QUOTE, ORDER_LEAD | POL(POL-ORDER 우선) |
    | RETURN | POL(POL-RETURN 우선) |
    | WARRANTY | POL(POL-WARRANTY 우선) |
3. **점수 계산**: 벡터 유사도(코사인) + 정확 문자열 가점. 에러 코드(error_code)나 펌웨어 버전(current_fw)이 있으면 그 문자열이 든 청크에 가점을 준다(FR-016 처리 3번). 최종 점수 = 벡터 유사도 + 0.2 × 정확 문자열 포함(제안).
4. **상위 k개**: k = 5(제안, D27). 점수와 함께 문의 순번(seq)을 붙여 `doc_candidate` 표에 저장.
5. **근거 없음**: 후보가 비었거나 모두 기준 점수 미만이면 "근거 없음". 기준 점수는 D27(결정 전에는 기준 없이 빈 결과만 근거 없음으로 처리하고, valid에서 정답 문서가 잡히는 최저 점수 분포를 본 뒤 정함).

### 4-5. 색인 저장

`svc.doc_chunk` 표(§6-2)에 청크 본문과 벡터를 함께 둔다. 107개 문서, 절 2~22개라 청크는 1천 개 안팎이다. 이 규모에서는 근사 색인 없이 전수 비교로도 충분히 빠르다. 색인은 문서가 바뀔 때만 다시 만든다(작업 W2).

---

## 5. 규칙 엔진과 표 조회 (FR-010~014, 017)

규칙 엔진은 Python 함수 묶음이며 LLM을 부르지 않는다. 모든 함수는 결과와 함께 "어느 표의 어느 행을 썼는지"와 판정 과정을 돌려주고, 이것이 근거 표시(FR-024)의 재료가 된다.

### 5-1. 기준정보 적재 구조 (ref 스키마)

ref/ CSV 12개를 정규화해 표 23개로 적재한다. 적재본만으로 tickets.csv 4,000건의 우선순위 규칙·SLA 목표·필수정보를 100% 재현했고 외래 키 위반은 0건이다.

| 묶음 | 표 | 원본 |
| --- | --- | --- |
| 코드 | department, product_family, inquiry_category, priority_level, customer_tier, urgency, info_field | departments.csv, product_master.csv, sla_policy.csv, priority_rules.csv, customers.csv, urgency_codebook.csv, info_field_codebook.csv |
| 마스터 | customer, product, product_standard, product_certification, product_spec, firmware_release | customers.csv, product_master.csv, product_spec_facts.csv, firmware_history.csv |
| 진단(확장용) | fault, fault_product | fault_catalog.csv |
| 규칙 | priority_rule, priority_rule_urgency, priority_rule_category, routing_rule, required_info_rule, required_info_field, sla_policy, sla_setting | priority_rules.csv, routing_rules.csv, required_info.csv, sla_policy.csv |

적재 주의: 모든 CSV가 UTF-8 BOM으로 시작하므로 `utf-8-sig`로 읽는다. fw_version, section, fw_fix_version은 문자열로 읽는다. routing_rules.csv의 family = 'ALL'과 primary_dept = '(제품군 기술지원)'은 NULL로 바꾸고 각각 "모든 제품군", "제품군의 기술지원 부서(product_family.tech_support_dept)"로 해석한다.

### 5-2. 우선순위 (FR-011, D33: 조건 표현 방식)

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

### 5-3. 부서 (FR-012)와 반품 단어 규칙 (D29)

1. 기본 키: `RT-{family}-{category}` (rule_source = CATEGORY_DEFAULT 또는 FAMILY_OVERRIDE). ESCALATION 3행은 1차 배정에 쓰지 않는다.
2. RETURN이면 return_kind를 먼저 정한다. L2가 준 return_reason의 영어 정규화 값에 대해 아래 단어 목록을 소문자로 찾는다. 비불량 단어가 있으면 NON_DEFECT, 불량 단어가 있으면 DEFECT, 둘 다 없거나 둘 다 있으면 UNKNOWN.
    
    
    | 구분 | 단어 목록 |
    | --- | --- |
    | 비불량(NON_DEFECT → RT-ALL-RETURN-NON_DEFECT, SCM) | different model, wrong model, wrong item, wrong product, ordered by mistake, order error, ordering mistake, surplus, excess, overstock, no longer needed, not needed, project cancel, changed mind, change of mind |
    | 불량(DEFECT → 기본 행, WARRANTY_DESK) | defect, defective, quality problem, quality issue, dead on arrival, doa, damaged, crack, broken, does not power, not working, fault |
3. UNKNOWN이면 기본 행 + "반품 사유 확인 필요" 표시. 상담원이 화면에서 불량/비불량을 고르면 Q4부터 다시 돈다.
4. 단어 목록은 코드가 아니라 설정 파일(`config/return_reason_words.yaml`)에 둔다.
5. 점검: train 반품 행(tickets.csv category_code = RETURN)에서 L2 → 단어 규칙 결과를 정답 routing_rule_id(RT-ALL-RETURN-NON_DEFECT 176건 / 그 밖 174건, 전체 4,000건 기준)와 비교해 목록을 고친다. 정답지 본문은 "We received a different model from what we ordered", "The unit was dead on arrival" 같은 문장이 반복되므로 단어 규칙으로 충분할 가능성이 높다. 정확도가 낮으면 D13에 따라 확장 FR-009(LLM 판별)로 바꾼다.

### 5-4. 필수정보 (FR-013)와 SLA 목표 (FR-014)

- 필수정보: `required_info_field`에서 (family, category) 행을 field_order 순으로 읽어 `missing_info = 필수 − 제공`, `missing_blocking_info = (is_blocking = true) − 제공`. 순서를 유지한다(정보 요청 문안의 항목 순서). 라벨은 info_field.label.
- SLA 목표: `sla_policy`에서 (category, customer_tier, priority_final) 1행. 목표 시간은 문의 행(`ticket_inquiry`)에 **복사해 저장**한다. 정책표가 나중에 바뀌어도 그때 약속한 목표로 판정하기 위해서다(의도적 중복 저장). 조정(FR-028) 때는 다시 조회해 덮어쓰고, 이전 값은 `priority_change`에 남긴다.

### 5-5. 숫자 표 조회 (FR-017)

| 유형 | 조회 | 출처 표기 |
| --- | --- | --- |
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

---

## 6. 저장 구조 (FR-001, 024~028, 031, 032, 035, 036)

### 6-1. 스키마 나누기와 정답지 격리

| 스키마 | 담는 것 | 누가 쓰나 |
| --- | --- | --- |
| ref | 기준정보·규칙표 23개 | 적재 작업만. 서비스는 읽기만 |
| gold | tickets.csv 4,000건 원본(58열 그대로) | 적재 작업만. 서비스는 FR-003 불러오기에서 `data_split = 'train'` 행의 입력 열 6개만 읽는다 |
| svc | 서비스 표(아래) | 서비스 |
| scoring | svc와 같은 표 모양. 채점 배치가 실행마다 비우고 쓴다 | 채점 배치만 |

test·valid 행은 svc에 들어가지 않는다. 채점 배치는 같은 파이프라인 코드를 scoring 스키마를 향하게 설정해 돌린다(§9 W4). 서비스 DB 연결 계정은 gold 스키마에서 `data_split = 'train'`인 행만 보이는 뷰(`gold.v_train_inputs`)에만 권한을 준다.

### 6-2. 서비스 표 목록 (svc 스키마)

D17(문의별 결과 저장 위치)의 결정 전 진행 방식대로 티켓과 문의를 나눈다.

| 표 | 한 행은 | 주요 열 | 관련 FR |
| --- | --- | --- | --- |
| ticket | 접수 1건 | ticket_id(PK), source_ticket_id(불러온 원본 CSV1-…), channel, customer_id → ref.customer, product_code → ref.product, language, body_language, body_language_uncertain, inquiry_subject(저장만), inquiry_body(마스킹됨), received_at, category_code(';' 문자열), is_composite, split_check_needed, first_response_at, created_by | 001, 003, 004, 006 |
| ticket_inquiry | 나눈 문의 1개 | (ticket_id, seq) PK, category_code, category_confidence, urgency_flag, product_code, product_family, customer_tier, return_kind, priority_rule, priority_rule_id, priority_final, priority_adjusted(Y/N), assigned_dept, routing_rule_id, missing_info[], missing_blocking_info[], sla_id, fr_target_h, res_target_h, status, resolved_at, final_action, flags[], edited_by_agent[] | 005~014, 025 |
| inquiry_field | 제공 항목 1개 | ticket_id, seq, field → ref.info_field, value_raw, value_norm, span_start, span_end, source(INQUIRY/CUSTOMER_REPLY/AGENT), source_message_id | 008, 013, 032 |
| inquiry_evidence | 근거 1줄 | ticket_id, seq, step(노드 이름), kind(CLASSIFY_SENTENCE / URGENCY_SENTENCE / PRIORITY_TRACE / ROUTING / REQUIRED_CHECK / SLA / LOOKUP_VALUE / DRAFT_CHECK), payload(JSONB), run_id | 024 |
| doc_candidate | 근거 후보 절 1개 | ticket_id, seq, rank, chunk_id → doc_chunk, score, run_id | 016 |
| ticket_message(→history) | 메시지 1줄 | message_id(PK), ticket_id, message_no, seq(티켓 전체면 NULL), sender, message_type, message_status, sent_at_utc, language, body, draft_id(발송 행일 때 원본 초안), is_edited, actor_name, mask_count, notice_transition(PROGRESS_NOTICE일 때 ①~④), override_check(자체 대조를 무시하고 발송했는지) | 015, 021~023, 031, 032, 035 |
| ticket_status_history | 문의 상태 변경 1건 | id, ticket_id, seq, from_status, to_status, changed_at, actor, event_kind, reason | 025, 026 |
| priority_change | 우선순위 조정 1건 | id, ticket_id, seq, changed_at, actor, from_priority, to_priority, from_sla_id, to_sla_id, from_targets, to_targets, reason_kind(고객 요청 / 영향 범위 재평가 / 기타), reason_text | 028 |
| sla_alert | 경고 1건 | id, ticket_id, seq, kind(FR_AT_RISK / FR_BREACHED / RES_AT_RISK / RES_BREACHED), fired_at, elapsed_h, target_h, cleared_at. UNIQUE(ticket_id, seq, kind) | 027 |
| agent_run | 처리 실행 1회 | run_id, ticket_id, seq(문의 실행이면), started_at, ended_at, duration_ms, result(SUCCESS / FAILED / PARTIAL), trigger(INTAKE / RETRY / CUSTOMER_REPLY / AGENT_EDIT), last_step | 036 |
| agent_step | 노드 실행 1회 | step_id, run_id, step_name, step_order, started_at, ended_at, duration_ms, result, input_summary(JSONB), output_summary(JSONB), error_kind, error_message, llm_model, prompt_version, input_tokens, output_tokens, llm_calls, retrieved_chunk_ids[] | 036 |
| doc_chunk | 문서 절 1개 | chunk_id(PK, `DOC§절`), doc_id, doc_type, product_code, family, section_no(TEXT), section_title, text, embedding(vector), revision | 016 |

메시지 종류(message_type)는 INQUIRY, INFO_REQUEST, FINAL_REPLY, PROGRESS_NOTICE, CUSTOMER_REPLY, ESCALATION_NOTE(확장) 6개, 상태(message_status)는 DRAFT, APPROVED, SENT, RECEIVED 4개다(FR-035 기준). 보낸 쪽(sender)은 CUSTOMER, SYSTEM, AGENT, DEPT. 재처리로 밀려난 초안을 구분하기 위해 DRAFT 행에 `superseded_at` 열을 하나 더 둔다(상태값을 늘리지 않음).

### 6-3. 지우지 않는 기록 (FR-035 처리 1번)

- ticket_message, ticket_status_history, priority_change, sla_alert, agent_run, agent_step은 INSERT만 한다. 예외는 FR-035가 허용한 두 가지(DRAFT → APPROVED 상태 변경, 임시 저장 때 DRAFT 본문 수정)와 superseded_at, cleared_at 기록이다.
- DB 수준 보호: SENT·RECEIVED 행의 body를 바꾸는 UPDATE를 막는 트리거, 같은 draft_id로 SENT 행이 두 개 생기지 않게 부분 유일 색인(`UNIQUE (draft_id) WHERE message_status = 'SENT'`).
- 같은 문의에 동시 상태 변경 두 건(FR-025 예외): ticket_inquiry에 `version` 열을 두고 "읽은 version과 같을 때만 바꾸기"로 막는다. 다르면 API가 409(충돌)를 돌려주고 화면이 "다른 사용자가 먼저 변경함. 새로고침"을 띄운다.

### 6-4. 상태 이력과 SLA 계산 (FR-025~027, D16·D21·D22)

**상태 이력은 앱이 사건 시각으로 쓴다.** 트리거가 `now()`로 쓰는 방식은 쓰지 않는다. 시연과 채점에서 과거 시각의 접수·회신(FR-001, FR-032 "재현용 과거 시각")을 넣어야 하는데, 트리거는 사건 시각이 아니라 저장 시각을 남기기 때문이다(D34). 상태를 바꾸는 함수는 하나(`transition(ticket_id, seq, to_status, at, actor, event)`)로 두고, 허용 전이표(FR-025)에 없는 전이는 이 함수가 거부한다.

**SLA는 저장하지 않고 "기준 시각"을 받는 SQL 함수로 계산한다.** 서비스 화면은 기준 시각 = 지금, 채점은 기준 시각 = 스냅샷(2026-09-30 23:59 UTC)으로 같은 함수를 부른다.

```sql
-- svc.inquiry_sla(as_of) : 문의별 두 시계 (FR-026)
-- 1차 응답 시각: 그 문의의 INFO_REQUEST(seq 일치) 또는 티켓의 FINAL_REPLY(seq NULL) 중 첫 SENT 시각 (D21)
-- 대기 합: WAITING_CUSTOMER 구간 합. 아직 대기 중이면 as_of 까지
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
- 티켓 대표값(D16): 끝나지 않은 문의 중 경고가 있는 문의 → 남은 시간이 가장 적은 문의의 상태·SLA. 모두 끝났으면 RESOLVED(모두 CLOSED면 CLOSED). 뷰 `svc.v_ticket_summary`가 계산한다.

**주기 점검(스케줄러, 5분, D30)** — APScheduler를 FastAPI 안에서 돌린다.

1. 끝나지 않은 문의(NEW, IN_PROGRESS, WAITING_CUSTOMER, ESCALATED)의 `inquiry_sla(now())`를 읽는다.
2. 조건을 처음 만족한 경고만 INSERT(유일 제약이 중복을 막는다). 발생 시각은 점검 시각이 아니라 조건을 넘은 실제 시각(received_at + 대기 + 목표 × 0.75)으로 계산해 넣는다(FR-027 예외: 주기를 건너뛰어도 정확).
3. WAITING_CUSTOMER 문의는 해결 경고를 새로 달지 않는다.
4. 무응답 종료(D22): WAITING_CUSTOMER이고 그 문의의 마지막 INFO_REQUEST SENT 시각 + 168시간 ≤ 지금이며 그 뒤 CUSTOMER_REPLY가 없으면 `transition(→ CLOSED, at = 발송 시각 + 168h, actor = SYSTEM)`, final_action = CLOSED_NO_RESPONSE.
5. 조정으로 목표가 늘어 조건이 풀린 경고에는 cleared_at을 쓴다.

### 6-5. 실행 로그 (FR-036, D31)

- LangGraph 노드마다 감싸는 함수(데코레이터) 하나가 agent_step 시작·끝·오류·소요를 쓴다. 노드 코드에는 로그 코드를 넣지 않는다.
- 입력·출력 요약에는 FR-024가 보여 주는 값(유형, 규칙 ID, 빠진 항목, 인용 목록 등)만 넣고, 긴 본문은 메시지 ID로 가리킨다.
- 분류 단계 입력 요약에 "넣은 항목 이름 목록"을 남긴다(제목이 없음을 확인, AC-036-2).
- 오류 종류: LLM_TIMEOUT, LLM_INVALID_OUTPUT, RULE_NOT_FOUND, DB, VALIDATION, UNKNOWN.
- 프롬프트·응답 전문 저장: 기본 꺼짐, 환경 변수 `LOG_FULL_LLM_IO=true`로 켠다. 켜면 마스킹을 거쳐 `agent_step.output_summary.full_io`에 저장.
- 보존 기간: agent_run·agent_step 90일(제안). 매일 1회 스케줄러가 지난 run을 지운다. 메시지 이력은 지우지 않는다.
- 로그 저장이 실패해도 처리 흐름은 계속하고 서버 로그 파일에 남긴다.
- 프로세스가 중간에 죽어 끝나지 않은 step은 다음 서버 시작 때 FAILED / UNKNOWN으로 닫는다.

---

## 7. 개인정보 마스킹 (FR-038)

**위치**: 저장 계층의 함수 `mask_text(text) -> (masked_text, count)` 하나. 메시지 저장, 티켓 저장, 실행 로그 저장, LLM 호출 직전 입력이 모두 이 함수를 지난다. 다른 경로로 DB에 글을 쓰는 코드를 두지 않는다.

**검사식 (결정 전 진행 방식, 규칙 기반이며 LLM 아님)**

| 대상 | 패턴(설명) | 바꾸는 값 |
| --- | --- | --- |
| 이메일 | `영문·숫자·._%+-` 1자 이상 + `@` + 도메인 + `.` + 2자 이상 영문. 단, 이미 `@***.masked`로 끝나는 값은 제외 | `user***@***.masked` |
| 전화번호 | (가) `+`로 시작하고 숫자가 8개 이상인 숫자·공백·`-`·`.`·괄호 묶음, 또는 (나) 숫자가 8개 이상이고 숫자 묶음 사이에 구분 기호(공백, `-`, `.`, 괄호)가 하나 이상 있는 묶음 | `***-****` |

**제외 목록(먼저 적용, 가리지 않음)**: 날짜 꼴(YYYY-MM-DD, YYYY/MM/DD), 구분 기호 없는 숫자열(주문 번호 PO 4500123456 같은 값), 영문이 섞인 토큰(제조번호 S/N LVB-2024-00117, 에러 코드 E.OC), 펌웨어 버전 꼴(숫자.숫자), 금액·수량. 데이터에 이미 있는 `**MASKED**`, `COMPANY_…`, `user…@***.masked`, `…_AGENT_nn`은 그대로 둔다.

**확인**: AC-038-1(이메일·국제 전화 2곳 가림), AC-038-2(날짜·PO·S/N 0곳), AC-038-3(train 2,800건 적재 시 0곳)을 단위 테스트로 만든다. 사람 이름은 범위 밖(FR-038 5번).

---

## 8. API와 화면 (FR-001, 003, 024, 028~032)

### 8-1. API 목록

모든 시각은 UTC ISO 8601. 상담원 식별은 로그인 대신 요청 머리에 `X-Agent-Name`, `X-Agent-Dept`를 싣는다(D23). FastAPI가 OpenAPI 문서(`/docs`)를 자동으로 만들고, 화면 쪽 TypeScript 타입은 이 문서에서 생성한다.

| 메서드·주소 | 하는 일 | FR |
| --- | --- | --- |
| `GET /ref/customers?q=`, `GET /ref/products` | 시뮬레이터 선택 목록 | 001 |
| `GET /gold/train/{source_ticket_id}` | train 행의 입력 열 6개(channel, customer_id, product_code, language, inquiry_body, received_at_utc). valid·test면 422와 "train 행만" 문구 | 003 |
| `POST /tickets` | 접수. 검증 → 저장 → 파이프라인 시작. 응답: ticket_id, processing=true | 001 |
| `GET /tickets?dept=&status=&priority=&alert=&needs_info=&has_draft=&composite=&channel=&q=&include_closed=&page=&size=50&sort=` | 접수함 목록(v_ticket_summary) + 건수 요약 | 029 |
| `GET /tickets/{id}` | 상세 묶음: 티켓, 문의별 결과, 근거, 초안, 처리 중 여부 | 030, 024 |
| `GET /tickets/{id}/timeline` | 메시지·상태 이력·경고·조정을 시각순으로 합친 목록 | 030 |
| `GET /tickets/{id}/runs`, `GET /runs/{run_id}/steps` | 처리 기록 | 036 |
| `GET /chunks/{chunk_id}` | 인용 클릭 시 절 본문 | 024 |
| `PATCH /tickets/{id}/inquiries/{seq}` | 유형·긴급도·제품·반품 구분·제공 항목 수정 → 해당 노드부터 재실행 | 030, 013, 010, 012 |
| `POST /tickets/{id}/inquiries/{seq}/priority` | 우선순위 조정(new_priority, reason_kind, reason_text 필수) | 028 |
| `POST /tickets/{id}/reprocess` | 다시 처리(새 run) | 001, 030 |
| `PUT /messages/{draft_id}` | 임시 저장(DRAFT 본문만) | 031 |
| `POST /messages/{draft_id}/send` | 승인·발송(final_body, override_check). 자체 대조 불일치면 409 + 불일치 목록, override_check=true로 다시 보내면 발송 | 031 |
| `POST /tickets/{id}/replies` | 고객 회신 입력(body, language, received_at, target_seqs) | 032 |
| `POST /tickets/{id}/close` | 종료 처리 RESOLVED → CLOSED | 025 |

외부 연계 창구(FR-037)는 범위 밖이다. 다만 `POST /tickets`와 `POST /tickets/{id}/replies`가 OpenAPI로 문서화되어 있으므로, 나중에 고객지원 시스템이 붙을 때 이 두 주소가 연계 지점이 된다(D36).

### 8-2. 화면 3개 화면에 대해 논의할 필요가 있음

| 화면 | 주소 | 구성 | 데이터 |
| --- | --- | --- | --- |
| 접수 시뮬레이터 | `/intake` | 채널·고객·제품·언어·제목·본문·접수 시각 입력, [train에서 불러오기] | `GET /ref/*`, `GET /gold/train/{id}`, `POST /tickets` |
| 접수함 | `/inbox` | 상단에서 상담원 이름·부서 선택(D23), 필터 7종, 표(FR-029의 열 순서), 상태 배지 색(ON_TRACK 초록, AT_RISK 노랑, BREACHED 빨강, WAITING_CUSTOMER 회색) | `GET /tickets` |
| 티켓 상세 | `/tickets/:id` | 왼쪽 "고객이 보낸 것", 가운데 "시스템이 판단한 것"(문의별 구역, 값마다 "왜?"), 오른쪽 "보낼 것"(정보 요청·답변·진행 안내 탭), 아래 "이력" 띠 | `GET /tickets/{id}`, `/timeline`, 버튼별 POST |
- 자동 갱신: 접수함은 진입·새로고침 때와 5분마다(스케줄러 주기와 같게, FR-029 6번). 티켓 상세는 처리 중일 때만 2초마다.
- 공통 부품을 먼저 만든다: 상태 배지, SLA 두 시계 표시, "왜?" 근거 팝오버, 인용·숫자 출처 링크.
- 번역 토글(원문의 한국어 번역)은 기능 목록에 없으므로 만들지 않는다(FR-030 9번).

---

## 9. 기능이 아닌 작업

| 번호 | 작업 | 내용 | 완료 확인 |
| --- | --- | --- | --- |
| W1 | 기준정보 적재 | ref/ CSV 12개 → ref 스키마 23개 표. BOM, 문자열 열, 특수값 처리(§5-1). 다시 실행해도 같은 결과(기존 표를 비우고 적재) | 외래 키 위반 0건, 우선순위 규칙·SLA 목표·필수정보를 tickets.csv 4,000건에서 100% 재현 |
| W2 | 문서 색인 | docs/ 107개 → 절 단위 청크 → 임베딩 → svc.doc_chunk | train 정답의 (reference_doc_id, reference_section) 쌍이 모두 청크 ID로 존재 |
| W3 | 정답지 적재 | tickets.csv → gold 스키마(4,000건, 58열, 읽기 전용). train만 보이는 뷰 생성 | split 건수 2,800 / 603 / 597 |
| W4 | 채점 배치 | §10 | test 1회 실행 결과표 |
| W5 | 시연 데이터 | 추적표 9건(CSV1-000004·000007·000008·000017·000031·000039·000085·000097·003578, 모두 train)을 불러오기로 재현하는 스크립트. 시나리오 ⓑ용 고객 회신 예시 2건, ⓒ용 복합 문의 예시 2건(팀이 작성) | 9건 분류~SLA 결과가 추적표와 같음 |
| W6 | 접수함 시연용 미해결 데이터 | train 미해결 243건을 정답지 시각으로 svc에 재생(접수 → 정보 요청 SENT → 대기 구간 → 현재 상태). §13 F-03 참고 | 스냅샷 기준 SLA 상태가 정답과 같음 |
| W7 | 배포 구성 | Docker Compose(db, api, web), `.env.example`(LLM·임베딩 키, DB 주소, LOG_FULL_LLM_IO), 초기화 명령 하나로 W1~W3 실행 | 새 노트북에서 README 순서대로 실행해 화면이 뜸 |

train 정답지의 메시지 적재(FR-035 처리 6번): W6과 W5에서 INQUIRY, INFO_REQUEST SENT(시각 = first_response_at_utc, info_request_sent = Y일 때), FINAL_REPLY SENT(시각 = resolved_at_utc, final_reply가 있을 때)를 만든다. 본문이 없는 1차 응답은 만들지 않는다.

---

## 10. 채점 배치 (W4, 기획서 2-2 성공 기준)

### 10-1. 실행 방식

1. 입력: gold에서 `data_split = test`(최종 1회) 또는 `valid`(사전 점검, 반복 가능) 행의 입력 열 6개. 제목·정답 열은 넣지 않는다.
2. 같은 파이프라인 코드를 scoring 스키마로 돌린다. 서비스 DB(svc)에는 아무것도 쓰지 않는다.
3. SLA·상태 항목은 파이프라인 결과가 아니라 **정답지의 시각으로 재생**해 계산식만 채점한다(AC-026-6): received_at, first_response_at_utc, resolved_at_utc, customer_wait_hours를 대기 구간 하나로 넣고 `inquiry_sla(스냅샷)`을 부른다. 목표 시간은 정답 우선순위(조정 건은 조정값, AC-028-3)로 조회한다.
4. 출력: `scoring_{split}_{날짜}.csv`(행 × 항목 일치 여부)와 요약 표(항목별 일치율, 제외 건수, 언어별·유형별 분해).

### 10-2. 채점 항목

| 항목 | 정답 열 | 비교 단위 | 기준 (기획서 2-2) |
| --- | --- | --- | --- |
| 문의 유형(단일) | category_code | 티켓 | ≥ 95% (D9) |
| 문의 유형(복합) | {category_code, secondary_category} 집합 | 티켓, 순서 무관 | ≥ 85% (D9). test 중 복합 57건 |
| 긴급도 | urgency_flag | 정답 유형과 같은 문의 | ≥ 90%, SAFETY 재현율 100%, SITE_DOWN ≥ 97% (D9) |
| 우선순위 규칙 | priority_rule_id | 정답 유형과 같은 문의 | 100% |
| 우선순위 | priority | 조정되지 않은 행(priority_adjusted_by_agent = N) | 100% |
| 부서 | routing_rule_id, assigned_dept | 유형과 반품 구분이 맞은 문의 | 100% (D13) |
| 제공 항목 | provided_info 항목 이름 집합 | 문의 | ≥ 90% (D9) |
| 막는 정보 | missing_blocking_info | 문의 | provided_info가 맞은 행 100%, 전체 ≥ 90% |
| SLA 목표 | sla_first_response_target_h, sla_resolution_target_h | 정답 우선순위로 재조회 | 100% |
| SLA 상태·경과 | sla_first_response_status, sla_resolution_status, sla_elapsed_hours | 정답 시각 재생 | 100% / 100% / 오차 0.1h |
| 근거 문서 | reference_doc_id (+ reference_section) | 상위 k개 포함 | ≥ 85% (D9). test 중 값이 있는 행 586건 |
| 숫자 | 초안 숫자 vs 표 값 | 초안 | 100% (D14) |
| 초안 본문 | final_reply | 참고 점수만 | 기준 없음(AC-021-5) |
| 복합 답변 | 단락 존재, 인용이 그 문의 후보 안 | 복합 티켓 | 단락 ≥ 95%, 인용 100% |

### 10-3. 제외 목록 (한 파일로 통합)

`scoring/exclusions.csv` (ticket_id, 항목, 사유, 출처). 채점 스크립트는 이 파일만 읽는다.

| 사유 | 대상 | 제외 항목 | 출처 |
| --- | --- | --- | --- |
| 펌웨어 모순 | 57건 중 해당 split 행 | 펌웨어 답변 숫자 | D3 |
| 고객 대기 시간 음수 | CSV1-003890(train), 003946(train), 003951(valid) | sla_elapsed_hours | D19 |
| NEW인데 대기 시간 있음, 막는 정보가 있는데 요청 미발송 | CSV1-003612(valid), 003913(test), 003950, 003967, 003995, 003999(train), 003984(valid) | sla_elapsed_hours, 정보 요청 관련 상태 재생 | D19, FR-013 데이터 주의 |
| 정답 없음 | 진행 안내, 복합 답변의 두 번째 문의, 상태 전이 재생 | 일치율 대신 생성·존재 기록 | D2, FR-022·025 |

D19의 NEW 7건과 FR-013 "데이터 주의"의 7건(막는 정보가 있는데 info_request_sent = N)은 같은 티켓들이다. test에는 CSV1-003913 한 건만 해당한다.

---

## 11. 결정 필요 사항 (D24부터)

기획서의 D1~D23은 그대로이며, 이 문서와 관련 있는 것은 D8(모델·예산), D9(기준 수치), D13(반품 구분), D15~D18(복합 문의), D21·D22(1차 응답, 무응답 종료), D23(로그인)이다. 시스템구성 문서가 "먼저 정해야 하는 것"으로 꼽은 6개는 D8(임베딩 모델, LLM 배분), D32(TicketState 필드), D35(청크 단위와 분류 출력 스키마), D36(외부 연계 인터페이스)으로 이어진다.

| 번호 | 항목 | 어디에 영향 | 누가 답하나 | 결정 전 진행 방식 |
| --- | --- | --- | --- | --- |
| D24 | FR-004~007을 LLM 호출 한 번(L1)으로 묶을지 | 비용, 분류 정확도 | 팀 | 묶는다. valid 유형 일치율이 95% 미만이면 긴급도를 떼어 비교 |
| D25 | 다국어 검색 방식(영어 검색문 vs 다국어 임베딩) | 근거 문서 적중률 | 팀 | 영어 검색문(L1의 query_en). valid에서 두 방식 비교 |
| D26 | 확신도 기준값 | "확신 낮음" 표시 빈도 | 팀 | 0.6. valid 첫 채점 뒤 구간별 일치율로 조정 |
| D27 | 검색 k와 근거 없음 점수 기준 | 근거 적중률, 엉뚱한 근거 | 팀 | k = 5, 점수 기준 없음(빈 결과만 근거 없음). valid 점수 분포로 정함 |
| D28 | 복합 답변 병합을 LLM으로 할지 템플릿으로 할지 | 단락 보존, 비용 | 팀 | 템플릿 결합 + 인사말·맺음말만 L5. 단락은 글자 그대로 |
| D29 | 반품 비불량·불량 단어 목록 | 부서 일치율(반품) | 팀 | §5-3 목록. train 반품 행으로 점검 |
| D30 | 시간 상한, 병렬·동시 호출 수, 점검 주기 | 안정성, 비용 | 팀 | 호출 30초 / 문의 120초 / 티켓 180초, 티켓 내 3, 전체 4, 점검 5분 |
| D31 | 실행 로그 보존 기간, 전문 저장 | 저장 용량, 디버깅 | 팀 | 90일, 전문 저장 꺼짐 |
| D32 | TicketState / InquiryState 필드 | 모든 노드의 계약 | 팀 | §2-3 목록 |
| D33 | 우선순위 조건 표현 방식 | 규칙 변경 용이성 | 팀 | 조건 표 2개(priority_rule_urgency, priority_rule_category) |
| D34 | 상태 이력 기록 방식(앱 vs DB 트리거) | 과거 시각 재현 | 팀 | 앱의 전이 함수가 사건 시각으로 기록 |
| D35 | 청크 단위와 분류 출력 스키마 | 검색, 분류 | 팀 | 절(`##`/`###`) 단위, §3-2 L1 스키마 |
| D36 | 외부 연계 인터페이스 | 확장 | 팀 | 별도 어댑터 없이 OpenAPI의 접수·회신 주소를 연계 지점으로 둠(FR-037 범위 밖) |
| D37 | 접수함 시연 데이터(AC-029-1)를 train 미해결 243건으로 바꿀지 | 시연, 정답지 격리 | 팀 | train 243건으로 시연. §13 F-03 |

---

## 12. 추적표 (FR → 기술 요소)

| FR | 이름 | 노드·호출 | 표 | API·화면 |
| --- | --- | --- | --- | --- |
| 001 | 문의 접수 | T1 | ticket, ticket_message, ticket_status_history | POST /tickets, /intake |
| 003 | 시연용 불러오기 | — | gold.v_train_inputs | GET /gold/train/{id} |
| 004 | 언어 식별 | T2(L1) | ticket.body_language | 상세 왼쪽 |
| 005 | 유형 분류 | T2(L1) | ticket_inquiry, inquiry_evidence | 상세 가운데 |
| 006 | 문의 분리 | T2(L1), T3 | ticket.category_code, ticket_inquiry(seq) | 상세 문의별 구역 |
| 007 | 긴급도 | T2(L1) | ticket_inquiry.urgency_flag | 상세 가운데 |
| 008 | 제공 항목 추출 | Q1(L2) | inquiry_field | 상세 왼쪽 강조 |
| 010 | 고객·제품 조회 | Q2 | ref.customer, ref.product | 상세 머리 |
| 011 | 우선순위 | Q3 | ref.priority_rule(+조건 표) | "왜?" |
| 012 | 부서 배정 | Q4 | ref.routing_rule, config/return_reason_words.yaml | "왜?" |
| 013 | 필수정보 | Q5 | ref.required_info_field | 체크리스트 |
| 014 | SLA 목표 | Q6 | ref.sla_policy → ticket_inquiry | 상세 SLA |
| 015 | 정보 요청 문안 | Q7(L3) | ticket_message(INFO_REQUEST, DRAFT) | 정보 요청 탭 |
| 016 | 문서 검색 | Q8 | doc_chunk, doc_candidate | 근거 탭 |
| 017 | 숫자 조회 | Q9 | ref.product, product_spec, firmware_release | "표에서 읽은 값" |
| 021 | 답변 초안 | Q10(L4), Q11 | ticket_message(FINAL_REPLY, DRAFT), inquiry_evidence(DRAFT_CHECK) | 답변 탭 |
| 022 | 복합 답변 병합 | T5(L5) | ticket_message | 답변 탭 |
| 023 | 진행 안내 | T6(L6) | ticket_message(PROGRESS_NOTICE) | 진행 안내 탭 |
| 024 | 근거 표시 | — | inquiry_evidence, doc_candidate, agent_step | "왜?" 팝오버 |
| 025 | 상태·이력 | 전이 함수 | ticket_inquiry.status, ticket_status_history | 이력 띠 |
| 026 | SLA 계산 | SQL 함수 inquiry_sla(as_of) | (계산) | 두 시계 |
| 027 | SLA 경고 | 스케줄러 | sla_alert | 접수함 정렬·아이콘 |
| 028 | 우선순위 조정 | Q6 재실행 | priority_change | POST …/priority |
| 029 | 접수함 | — | v_ticket_summary | GET /tickets, /inbox |
| 030 | 티켓 상세 | — | (읽기) | GET /tickets/{id}, /tickets/:id |
| 031 | 승인·발송 | 자체 대조 | ticket_message(SENT), 전이 | POST /messages/{id}/send |
| 032 | 고객 회신 | Q1부터 재실행 | ticket_message(CUSTOMER_REPLY), inquiry_field | POST …/replies |
| 035 | 메시지 이력 | 저장 계층 | ticket_message | 이력 띠 |
| 036 | 실행 로그 | 노드 감싸기 함수 | agent_run, agent_step | 처리 기록 탭 |
| 038 | 마스킹 | mask_text | 모든 저장 경로 | "마스킹됨 n곳" |

---

## 13. 작성 중 확인한 사항 (기획서·명세서와 다른 점)

아래는 기획서·명세서 파일을 고치지 않고 적어 둔 것이다. 반영이 필요하면 before/after를 따로 만들어 승인을 받는다.

| 번호 | 대상 | 확인한 사실 | 이 문서의 처리 |
| --- | --- | --- | --- |
| F-01 | 명세서 그룹 3 "문서 사실" | "제품 문서 92개(제품 23종 × DS·IG·TG·RN)"라고 적혀 있으나, doc_index.csv 기준 92개 = DS 23 + IG 23 + TG 23 + RN 13 + MG(정비 안내) 10이다. RN은 펌웨어 있는 13개 제품에만 있고, MG는 명세서에 나오지 않는다 | §4-1 표와 검색 범위에 MG 포함 |
| F-02 | 명세서 그룹 3 MANUAL 근거 문서 | "MANUAL → IG/TG/RN"이지만 정답지 MANUAL 근거는 IG 110, TG 85, RN 45, DS 44, MG 41이다 | MANUAL 우선 종류를 IG, TG, RN, DS, MG로 둠(§4-4) |
| F-03 | 명세서 그룹 5 AC-029-1 | "정답지 미해결 365건을 적재"하고 TS_LV 67건을 기대하지만, 365건 중 valid 59건·test 63건이 섞여 있어 "test·valid는 서비스 DB에 넣지 않는다" 원칙과 충돌한다. train만 쓰면 243건, TS_LV는 46건이다 | train 243건으로 시연(W6), D37 |
| F-04 | 명세서 FR-008, FR-012 | 정답지 provided_info에는 항목 이름만 있고 값(예: return_reason의 문장)은 없다 | 추출 채점은 항목 이름 집합으로만. 반품 단어 규칙 점검은 정답 routing_rule_id로(§5-3) |
| F-05 | 기획서 D19와 명세서 FR-013 데이터 주의 | 두 곳의 "7건"은 같은 티켓들이다(NEW, 막는 정보 있음, 요청 미발송, 대기 시간 있음) | 제외 목록에서 한 사유로 묶음(§10-3) |
| F-06 | 견적 유효기간 30일의 출처 | 명세서 FR-021의 "유효기간 30일"은 POL-ORDER §5에 근거가 있다 | QUOTE 초안이 POL-ORDER §5를 항상 인용(§3-3) |