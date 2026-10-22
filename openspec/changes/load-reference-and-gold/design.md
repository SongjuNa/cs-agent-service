# Design: 기준정보·정답지 적재

## Context

동기는 proposal.md의 Why를 본다. 따를 기준은 다음과 같다.

- 테이블 정의서 v1.3 §2와 §3(표·열·행 수), §2-0(원본에서 바꾼 점), `docs/database/schema.sql`(이미 만든 표).
- 기술 명세서 v1.4 §5-1(적재 주의)과 §9 W1·W3.
- 프로젝트 구조 1순위 판 2장의 `jobs/load_reference.py`, `jobs/load_gold.py`.

## Goals / Non-Goals

**Goals**
- 명령 두 개로 ref와 gold를 채운다.
- 같은 명령을 다시 실행해도 결과가 같다.

**Non-Goals**
- DB 구조 변경. schema.sql은 그대로 둔다.

## Decisions

### 1. 데이터 위치

- 운영진 데이터 폴더(`CS_AI_Agent_Training_Data_v1/`)를 저장소 안 `data/` 아래에 둔다. `data/`는 뼈대의 `.gitignore`가 이미 커밋에서 빼고 있다(CLAUDE.md 규칙 8).
- 위치는 환경 변수 `DATA_DIR`로 바꿀 수 있다. 기본값은 `data/CS_AI_Agent_Training_Data_v1`이다.

### 2. 실행 방법

- 저장소 루트에서 `python -m jobs.load_reference`, `python -m jobs.load_gold`를 실행한다.
- DB 주소는 뼈대의 `app.config`가 `.env`에서 읽은 `DATABASE_URL`을 쓴다. 따로 설정하지 않는다.
- 순서: load_reference → load_gold. gold 표는 ref를 가리키지 않으므로 순서를 바꿔도 되지만, README에는 기술 명세서 §1-5의 초기화 순서(W1 → W3)대로 적는다.

### 3. 기준정보 변환 규칙

테이블 정의서 §2-0 표를 한 줄씩 코드로 옮긴다. 판단이 필요한 곳은 아래와 같다.

| 항목 | 처리 | 근거 |
|---|---|---|
| CSV 읽기 | `utf-8-sig`(BOM 제거), 모든 값을 문자열로 읽은 뒤 열 형식(정수, 날짜, Y/N → 참/거짓)으로 바꾼다 | 기술 명세서 §5-1 |
| fw_version, section, fw_fix_version | 문자열 그대로 | §5-1, 정의서 §2-0 |
| routing_rules.csv family = 'ALL', primary_dept = '(제품군 기술지원)' | 비어 있음(NULL) | §5-1, 정의서 §2-0 |
| priority_rules.csv condition → priority_rule_urgency, priority_rule_category | 정의서 §2-0의 분해를 표로 적는다. PR-06·PR-07의 생략된 유형 = 정보성 4종(TECH_SPEC, MANUAL, COMPLIANCE, QUOTE) | 정의서 §2-0. 분해 결과 행 수 = 6, 20(정의서 §2-4) |
| required_info.csv → required_info_field | required_fields 순서대로 field_order를 매기고, blocking_fields에 있으면 is_blocking = 참 | 정의서 §2-0 |
| fault_catalog.csv applies_to, fw_fix_version | 제품마다 fault_product 한 행. fw_fix_version은 그 제품의 펌웨어 이력에 있는 버전일 때만 그 행에 둔다 | 정의서 §2-0 (FLT-078 예) |
| sla_policy.csv의 clock, at_risk_threshold, pause_rule | sla_setting 3행 | 정의서 §2-0 |
| inquiry_category.sla_resolution_coef | sla_policy.csv에서 계산해 넣는다(유형별 해결 목표 ÷ 같은 등급·우선순위의 TECH_SPEC 해결 목표). 유형 안에서 값이 하나로 일정하지 않으면 적재를 멈춘다 | 운영진 README.html "Category 계수"(TECH_SPEC ×1.0 … RETURN ×2.0), 정의서 §2-1 (조장 승인 2026-10-22) |
| customer.primary_contact_* 3열 | 비워 둔다 | 정의서 §2-2 (customers.csv에 값 없음) |

### 4. 다시 실행하는 방법: 한 번에 비우고 한 번에 넣기

- 작업 전체를 **트랜잭션 하나**로 묶는다. 트랜잭션은 "전부 되거나, 전부 안 되거나"로 묶은 DB 작업 단위다.
  - 먼저 자식 표부터 `DELETE`(행 지우기)로 비운다. 그다음 부모 표부터 차례로 넣는다.
  - 중간에 하나라도 실패하면 처음 상태로 돌아간다.
- `TRUNCATE`(표 통째로 비우기)는 쓰지 않는다. svc 표가 비어 있어도 기준정보를 가리키는 외래 키만 있으면 PostgreSQL이 거부하기 때문이다(구현 중 확인). `CASCADE`(가리키는 다른 표까지 함께 비우기)도 쓰지 않는다.
  - svc의 티켓이나 doc_chunk가 기준정보를 실제로 가리키고 있으면 지우기가 실패한다. 이때 오류를 보여 주고 아무것도 바꾸지 않는다.
  - 서비스 데이터나 문서 색인이 몰래 지워지는 것을 막기 위해서다(spec W1-2 요구사항).
- 외래 키는 DB가 검사한다(schema.sql의 FK). 위반하면 적재가 실패하므로 "FK 위반 0건"은 적재 성공으로 확인된다.

### 5. 정답지 적재

- tickets.csv와 resolution_cases.csv의 머리글 이름을 표의 열 이름과 맞춰 넣는다. 머리글과 열 이름이 하나라도 다르면 멈춘다.
- **빈 칸은 비어 있음(NULL)으로 넣는다.** schema.sql의 v_inputs 뷰가 `nullif(received_at_utc, '')`로 두 경우를 모두 받으므로 어느 쪽이든 동작한다. NULL로 하면 "값 없음"을 SQL에서 한 가지 방법(`IS NULL`)으로 찾을 수 있다.
- 많은 행은 PostgreSQL의 `COPY`(대량 입력 명령)로 넣는다.

### 6. 시험

- `backend/tests/test_data_load.py` 하나에 W1-1~W1-4, W3-1~W3-2를 하나씩 둔다.
- 시험이 적재 작업을 직접 실행한 뒤 확인한다. 그래서 시험 DB의 ref·gold 내용은 다시 채워진다.
- 데이터 폴더가 없으면 시험은 실패한다(건너뛰지 않는다). 시험이 무엇을 확인하는지 분명히 하기 위해서다.

## Risks / Trade-offs

- [svc에 데이터가 생긴 뒤에는 기준정보를 다시 적재할 수 없다] → 오류 메시지에 "svc 데이터를 먼저 비우거나 `docker compose down -v` 후 다시"라고 안내한다.
- [W2(문서 색인) 뒤에 기준정보를 다시 적재하면 doc_chunk가 document를 가리켜 실패한다] → 같은 안내. W2 변경에서 다시 다룬다.
