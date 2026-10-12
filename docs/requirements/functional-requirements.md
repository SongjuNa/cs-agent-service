# 기능 요구사항 명세서 v1

결과: 해결 중
구분: 기획
담당자: mj choi
버전: v1
상태: 작성 중
생성일: 2026/10/10
종류: 산출물

# 상세 기능 요구사항 명세서 — 해외고객향 C/S 대응 AI Agent

| 항목 | 내용 |
| --- | --- |
| 버전 / 작성일 | v1.0 / 2026-10-10 (STEP 5 그룹 1~6 승인본을 한 파일로 합침. STEP 6·7의 반영 사항 포함) |
| 대상 | STEP 3에서 확정한 MVP 기능 30개 (FR-001~038 중). 확장·제외 기능은 기획서 4절 참조 |
| 형식 | 기능마다 9항목: 기능 설명 / 우선순위 / 수행 주체 / 입력 / 처리 / 출력 / 예외 처리 / 완료 기준(Given-When-Then) / 의존성 및 확인 사항 |
| 함께 보는 문서 | 프로젝트_기획서_v1.md(결정 필요 사항 D1~D23, 검토용 부록), 기술 설계서(작성 예정) |
| 공통 규칙 | 구현 방식(클래스, 함수, 테이블 컬럼)은 적지 않는다. 결정이 필요한 사항은 D번호로 표시하고 "결정 전 진행 방식"으로 진행한다. 수치 기준 중 "제안"은 팀 합의 전 값이다(D9) |

## 기능 목록

| 그룹 | ID | 기능명 |
| --- | --- | --- |
| 그룹 1 | FR-001 | 문의 접수(접수 시뮬레이터) |
| 그룹 1 | FR-003 | 시연용 티켓 불러오기 |
| 그룹 1 | FR-004 | 언어 식별 |
| 그룹 1 | FR-005 | 문의 유형 분류 |
| 그룹 1 | FR-006 | 문의 분리와 유형 배열 생성(복합 문의) |
| 그룹 1 | FR-007 | 긴급도 판단 |
| 그룹 1 | FR-008 | 제공 항목 추출 |
| 그룹 2 | FR-010 | 고객·제품 조회 |
| 그룹 2 | FR-011 | 우선순위 계산 |
| 그룹 2 | FR-012 | 부서 배정 |
| 그룹 2 | FR-013 | 필수정보 확인 |
| 그룹 2 | FR-014 | SLA 목표 설정 |
| 그룹 3 | FR-015 | 추가정보 요청 메시지 생성 |
| 그룹 3 | FR-016 | 문서 근거 검색 |
| 그룹 3 | FR-017 | 숫자 표 조회 |
| 그룹 3 | FR-021 | 답변 초안 생성 |
| 그룹 3 | FR-022 | 복합 문의 답변 병합 |
| 그룹 3 | FR-023 | 진행 안내 메시지 생성 |
| 그룹 3 | FR-024 | 근거 표시 |
| 그룹 4 | FR-025 | 상태 관리와 변경 이력 |
| 그룹 4 | FR-026 | SLA 경과·상태 계산 |
| 그룹 4 | FR-027 | SLA 위험 경고 |
| 그룹 4 | FR-028 | 우선순위 조정과 SLA 재계산 |
| 그룹 5 | FR-029 | 접수함 |
| 그룹 5 | FR-030 | 티켓 상세 |
| 그룹 5 | FR-031 | 초안 수정·승인·발송 |
| 그룹 5 | FR-032 | 고객 회신 입력 |
| 그룹 6 | FR-035 | **메시지 이력 저장** |
| 그룹 6 | FR-036 | 처리 실행 로그 |
| 그룹 6 | FR-038 | **개인정보 마스킹 유지** |

---

## 그룹 1. 접수와 문의 이해 (FR-001, 003, 004, 005, 006, 007, 008)

공통 용어: "티켓"은 접수된 문의 한 건. "코드값"은 ref/ 코드표에 있는 값만 허용. "처리 흐름"은 FR-004 → 005/006/007 → 008 → (그룹 2) 규칙 적용 → (그룹 3) 근거·초안 순서로 한 티켓에 대해 한 번 도는 것.

---

### FR-001. 문의 접수(접수 시뮬레이터)

**1. 기능 설명**

- 상담원이 채널·고객·제품·언어·본문을 입력해 티켓을 만들고 처리 흐름을 시작한다. 실제 메일·채팅·전화·포털 연동 대신 이 화면이 접수를 대신한다.

**2. 우선순위**

- Must Have

**3. 수행 주체**

- 상담원(입력), 시스템(티켓 생성과 처리 흐름 시작)

**4. 입력(Input)**

| 항목 | 필수 | 검증 |
| --- | --- | --- |
| channel | 필수 | EMAIL, CHAT, PHONE, WEB_FORM, PARTNER_PORTAL 중 하나 |
| customer_id | 필수 | customers.csv에 있는 ID |
| product_code | 선택 | 입력 시 product_master.csv 23종 중 하나. 비우면 FR-008이 본문에서 찾는다 |
| language (고객 언어) | 필수 | 15개 코드(ar, de, en, es, fr, id, it, ja, pl, pt, ru, th, tr, vi, zh) 중 하나. customers.csv에 언어 컬럼이 없으므로 입력받는다 |
| inquiry_body | 필수 | 1자 이상 2,000자 이하(제안 상한. 데이터 최대 756자). 공백만이면 거부 |
| inquiry_subject | 선택 | 저장만 하고 처리 흐름에는 쓰지 않는다(팀 정리 §6 제목 누설) |
| received_at | 선택 | 비우면 현재 시각(UTC). 재현용으로 과거 시각 입력 허용, 미래 시각 거부 |

**5. 처리(Process)**

1. 입력 검증(위 표). 실패하면 항목별 오류를 돌려주고 티켓을 만들지 않는다.
2. 티켓 생성: 상태 NEW, received_at 기록, 입력값 저장.
3. 메시지 이력에 종류 INQUIRY로 본문 저장(FR-035), 상태 이력에 NEW 진입 기록(FR-025).
4. 처리 흐름 시작(FR-004부터). 흐름이 끝나면 상태를 IN_PROGRESS로 바꾼다.
5. 티켓 상세 화면(FR-030)으로 이동.

**6. 출력(Output)**

- 성공: 새 ticket_id, 티켓 상세 화면.
- 저장·변경: 티켓 1건(NEW), 메시지 1건(INQUIRY), 상태 이력 1건.
- 사용자 표시: 처리 흐름이 도는 동안 "처리 중" 표시, 끝나면 결과 표시.

**7. 예외 처리(Exception)**

| 상황 | 시스템 대응 | 사용자에게 보이는 것 |
| --- | --- | --- |
| customer_id가 없음 | 티켓 미생성 | "고객 ID를 찾을 수 없음" 항목 오류 |
| product_code가 목록에 없음 | 티켓 미생성 | "제품 코드를 찾을 수 없음" 항목 오류. 모르면 비우라고 안내 |
| 본문 비어 있음·길이 초과 | 티켓 미생성 | 항목 오류 |
| 처리 흐름 중 LLM 호출 실패(시간 초과, 오류 응답) | 티켓은 NEW로 남기고 실패 단계와 사유를 실행 로그(FR-036)에 기록. 자동 재시도 1회 | "자동 처리 실패. 다시 시도" 버튼 |
| 처리 흐름 중 규칙표 조회 실패(해당 행 없음) | 그룹 2의 예외 규칙을 따름 | 그룹 2 참조 |

**8. 완료 기준(Acceptance Criteria)**

- AC-001-1: Given 유효한 채널·고객·언어·본문, When 접수를 누르면, Then 상태 NEW인 티켓이 생성되고 INQUIRY 메시지와 NEW 상태 이력이 각 1건 기록되며 처리 흐름이 시작된다.
- AC-001-2: Given customers.csv에 없는 customer_id, When 접수를 누르면, Then 티켓이 생성되지 않고 해당 항목에 오류가 표시된다.
- AC-001-3: Given 제목을 입력한 티켓, When 처리 흐름이 돌면, Then 분류(FR-005~007)의 입력에 제목이 포함되지 않는다(실행 로그의 입력 기록으로 확인).
- AC-001-4: Given LLM 호출이 실패하는 상태, When 접수를 누르면, Then 티켓은 NEW로 남고 "다시 시도" 버튼이 보이며, 재시도 시 같은 티켓으로 흐름이 다시 돈다.

**9. 의존성 및 확인 사항**

- 선행: 기준 데이터 적재(customers.csv, product_master.csv). FR-025, FR-035.
- 후행: FR-003(불러오기)은 이 화면을 채우는 기능.

---

### FR-003. 시연용 티켓 불러오기

**1. 기능 설명**

- 상담원이 tickets.csv의 train 티켓 번호를 입력하면 그 티켓의 입력 컬럼만 접수 화면에 채워진다. 추적표 9건 재현과 시연에 쓴다.

**2. 우선순위**

- Could Have (MVP 포함: 성공 기준 5-2에 필요)

**3. 수행 주체**

- 상담원(번호 입력), 시스템(정답지 조회와 화면 채우기)

**4. 입력(Input)**

- ticket_id (필수): "CSV1-" + 6자리 숫자 형식.

**5. 처리(Process)**

1. 정답지(tickets.csv 적재본)에서 ticket_id를 찾는다.
2. data_split이 train인지 확인한다.
3. 다음 컬럼만 접수 화면에 채운다: channel, customer_id, product_code, language, inquiry_body, received_at_utc. 제목(inquiry_subject)과 정답 컬럼(category_code, priority, assigned_dept, final_reply 등)은 채우지 않는다.
4. 상담원이 접수를 누르면 FR-001과 같다. 새 티켓에는 "원본 CSV1-xxxxxx에서 불러옴"을 기록한다.

**6. 출력(Output)**

- 접수 화면의 해당 칸이 채워진 상태. 저장은 없음(접수 전).

**7. 예외 처리(Exception)**

| 상황 | 시스템 대응 | 사용자에게 보이는 것 |
| --- | --- | --- |
| 번호 형식 오류 | 조회 안 함 | "형식: CSV1-000000" |
| 번호가 정답지에 없음 | 채우지 않음 | "티켓을 찾을 수 없음" |
| data_split이 valid 또는 test | 채우지 않음 | "train 행만 불러올 수 있음(채점용 행은 서비스에 넣지 않음)" |

**8. 완료 기준(Acceptance Criteria)**

- AC-003-1: Given 추적표의 CSV1-000017, When 불러오기를 누르면, Then channel=PHONE, customer_id=CUST-0350, product_code=ACB-AS-2000, language=en, 본문, received_at=2025-10-02 09:45:43이 채워지고 제목·정답 컬럼은 비어 있다.
- AC-003-2: Given test 행인 CSV1-001112, When 불러오기를 누르면, Then 아무 칸도 채워지지 않고 train 행만 가능하다는 안내가 보인다. (주: 추적표의 CSV1-001112는 test 행이므로 시연 재현 대상에서 제외하거나 train 행으로 대체 → D12)
- AC-003-3: Given 불러온 값으로 접수한 티켓, When 처리 흐름이 끝나면, Then 분류·우선순위·부서·필수정보·SLA 목표가 추적표의 값과 같다(그룹 2·3의 AC로 상세화).

**9. 의존성 및 확인 사항**

- 선행: 정답지 적재(tickets.csv), FR-001.
- CSV1-001112는 data_split=test라 이 기능으로 불러올 수 없다. 추적표 9건 재현에서 001112를 빼고 같은 흐름(고장→정보 요청→원격 해결)의 train 행으로 대체할지 결정했다.

---

### FR-004. 언어 식별

**1. 기능 설명**

- 티켓마다 고객 언어(language)와 본문 언어(body_language)를 따로 정해 기록한다. 답장은 language로, 본문 해석은 body_language로 한다.

**2. 우선순위**

- Must Have

**3. 수행 주체**

- 시스템(언어 판정), 처리 흐름의 첫 단계

**4. 입력(Input)**

- language: FR-001 입력값(필수).
- inquiry_body: FR-001 입력값(필수).
- channel: FR-001 입력값.

**5. 처리(Process)**

1. language는 입력값을 그대로 쓴다(판정하지 않는다).
2. body_language는 본문으로 판정한다. 판정 결과는 15개 코드 중 하나여야 한다.
3. 판정 확신도가 기준 미만이거나 15개 밖의 코드가 나오면 body_language = language로 두고 "언어 판정 불확실" 표시를 남긴다. 신뢰도 기준은 기술 설계서에서 정한다.
4. 두 값을 티켓에 기록하고 다음 단계로 넘긴다.

**6. 출력(Output)**

- 티켓의 language, body_language, 언어 판정 불확실 여부.
- 사용자 표시: 티켓 상세에 "답장 언어 / 본문 언어" 두 값. 다르면(예: 전화 메모) 눈에 띄게 표시.

**7. 예외 처리(Exception)**

| 상황 | 시스템 대응 |
| --- | --- |
| 본문이 두 언어 혼용 | 더 많은 쪽으로 판정하고 불확실 표시 |
| 판정 도구(LLM 또는 라이브러리) 실패 | body_language = language, 불확실 표시, 흐름은 계속 |

**8. 완료 기준(Acceptance Criteria)**

- AC-004-1: Given CSV1-003578(전화, 이탈리아 고객, 영어 메모), When 처리하면, Then language=it, body_language=en으로 기록된다.
- AC-004-2: Given CSV1-000008(이메일, 아랍어 본문), When 처리하면, Then language=ar, body_language=ar.
- AC-004-3: Given 판정 도구가 실패하는 상태, When 처리하면, Then body_language는 language와 같고 불확실 표시가 남으며 다음 단계가 실행된다.
- AC-004-4: Given test 597건, When body_language를 채점하면, Then 정답과의 일치율이 D9의 제안 기준(분류와 같은 95%) 이상이다.

**9. 의존성 및 확인 사항**

- 선행: FR-001. 후행: FR-005~008(해석 언어), FR-015·021·023(답장 언어).

---

### FR-005. 문의 유형 분류

**1. 기능 설명**

- 본문을 읽어 문의 유형 category_code 10종 중 하나를 고른다. 제목은 쓰지 않는다. 이 값은 우선순위·부서·필수정보·SLA 규칙표의 열쇠다.

**2. 우선순위**

- Must Have

**3. 수행 주체**

- 시스템의 분류 단계(LLM 호출 1회, FR-006·007과 같은 호출로 묶어도 된다)

**4. 입력(Input)**

- inquiry_body(필수), body_language(필수), product_family(product_code가 있으면 product_master.csv에서; 없으면 비움), channel.
- 제외: inquiry_subject, 고객 등급, 정답 컬럼.

**5. 처리(Process)**

1. 유형 10종의 정의(README §6 Category 설명)와 본문을 넣어 분류를 요청한다.
2. 응답은 정해진 칸(category_code, 확신도, 근거 문장)으로만 받는다(구조화 출력).
3. category_code가 10종 밖이면 1회 재요청. 다시 실패하면 category_code를 비우고 "분류 실패" 표시.
4. 확신도가 기준 미만이면 값은 유지하되 "확신 낮음" 표시(기준은 기술 설계서, 표시 여부는 상담원 화면 FR-024).

**6. 출력(Output)**

- 티켓의 category_code, 분류 확신도, 근거 문장(본문 중 어느 문장 때문인지), 분류 실패·확신 낮음 표시.
- 사용자 표시: 티켓 상세에 유형과 근거 문장.

**7. 예외 처리(Exception)**

| 상황 | 시스템 대응 | 사용자에게 보이는 것 |
| --- | --- | --- |
| 코드값 밖의 응답 2회 | category_code 비움, 흐름은 규칙 단계를 건너뛰고 상담원에게 넘김 | "유형을 정하지 못함. 직접 선택" 드롭다운 |
| LLM 실패(시간 초과, 오류) | 1회 재시도 후 FR-001 예외와 같이 NEW로 남김 | "자동 처리 실패. 다시 시도" |
| 본문이 유형을 판단할 수 없을 만큼 짧음(예: "문의드립니다") | 분류는 시도하되 확신 낮음 표시 | 확신 낮음 표시 |

**8. 완료 기준(Acceptance Criteria)**

- AC-005-1: Given 추적표 9건(train)을 FR-003으로 접수, When 분류하면, Then category_code가 추적표와 같다(000017 DEFECT, 000007 DEFECT, 000004 QUOTE, 000097 RETURN, 000039 RETURN, 000008 FW_UPDATE, 000031 MANUAL, 003578 TECH_SPEC, 000085 FW_UPDATE).
- AC-005-2: Given 제목이 "Demande de tarif …"인 CSV1-000004, When 분류 입력을 실행 로그에서 확인하면, Then 제목 문자열이 입력에 없다.
- AC-005-3: Given 코드값 밖의 응답을 두 번 내는 상태, When 분류하면, Then category_code가 비고 상담원 화면에 직접 선택 드롭다운이 보인다.
- AC-005-4: Given test 597건, When 채점하면, Then category_code 일치율이 95% 이상(D9 제안 기준). 복합 문의 행은 FR-006의 AC-006-4로 따로 채점한다.

**9. 의존성 및 확인 사항**

- 선행: FR-004, 기준 데이터 적재. 후행: FR-011~014, FR-016.
- 기술 설계서로 넘길 것: 프롬프트, 구조화 출력 스키마, 확신도 기준, 호출 묶음 여부.

---

### FR-006. 문의 분리와 유형 배열 생성(복합 문의)

**1. 기능 설명**

- 본문에 서로 다른 요청이 둘 이상 있으면 요청마다 나누고, 각 요청의 유형을 category_code에 세미콜론(;)으로 이어 쓴다(예: "FW_UPDATE;MANUAL"). secondary_category 필드는 두지 않는다.
- 나눈 문의는 각각 새 문의로 본다. 주·보조 구분 없이 문의마다 파이프라인(긴급도→추출→규칙→근거→초안) 1개를 만들어 n개를 병렬로 돌린다. 결과는 FR-022에서 하나의 답변으로 합친다.

**2. 우선순위**

- Should Have (MVP 포함)

**3. 수행 주체**

- 시스템의 분류 단계(FR-005와 같은 호출에서 나누기와 유형 고르기를 함께 한다), 파이프라인 생성은 워크플로 엔진

**4. 입력(Input)**

- FR-005와 같다.

**5. 처리(Process)**

1. 분류 요청에 "본문을 서로 다른 요청 단위로 나누고, 요청마다 유형 1개와 해당 본문 문장을 고른다"를 포함한다.
2. 각 유형은 10종 중 하나여야 한다. 같은 유형이 두 번 나오면 하나로 합친다.
3. 나눈 수가 1이면 단일 문의로 처리한다. 2 이상이면 복합 문의 표시를 켜고 category_code를 ';'로 이어 저장한다. 순서는 본문에 나온 순서다.
4. 문의마다 순번(seq)과 본문 근거 문장을 붙여 파이프라인을 만들고 병렬로 실행한다. 각 파이프라인은 자기 문의의 유형과 근거 문장으로 FR-007·008, 그룹 2, 그룹 3을 수행한다.
5. 나눈 수 상한은 3이다(D18). 넘으면 앞의 3개만 파이프라인을 만들고 "문의 분리 확인 필요"를 표시한다.

**6. 출력(Output)**

- 티켓의 category_code(';' 구분 문자열), 복합 문의 표시, 문의별 순번·유형·근거 문장. 문의별 결과는 D17의 저장 위치에 둔다.
- 사용자 표시: 티켓 상세에 "복합 문의: 문의 1 {유형} / 문의 2 {유형}"과 각 문의의 근거 문장.

**7. 예외 처리(Exception)**

| 상황 | 시스템 대응 |
| --- | --- |
| 같은 유형이 두 번 나옴 | 하나로 합치고 근거 문장을 모두 남김 |
| 코드값 밖의 유형 | 그 문의만 1회 재요청, 다시 실패하면 그 문의를 "유형 판정 실패"로 두고 나머지 파이프라인은 계속 |
| 나눈 수가 3 초과 | 앞 3개만 처리, "문의 분리 확인 필요" 표시(D18) |
| 파이프라인 하나가 실패 | 나머지 결과는 유지하고 실패한 문의에 "자동 처리 실패. 다시 시도" 표시 |

**8. 완료 기준(Acceptance Criteria)**

- AC-006-1: Given CSV1-000008(펌웨어 업데이트 + 매뉴얼 요청), When 분류하면, Then category_code에 FW_UPDATE와 MANUAL이 ';'로 들어 있고(순서 무관) 복합 문의 표시가 켜지며 파이프라인 2개가 만들어진다.
- AC-006-2: Given CSV1-000004(단일 견적 문의), When 분류하면, Then category_code = "QUOTE", 복합 문의 표시가 꺼져 있고 파이프라인은 1개다.
- AC-006-3: Given 복합 문의 티켓, When 실행 로그를 보면, Then 문의별 파이프라인이 각자의 유형으로 우선순위·부서·SLA 목표를 따로 계산했다.
- AC-006-4: Given test 597건 중 secondary_category가 있는 행, When 나눈 문의 유형 집합을 정답 {category_code, secondary_category}와 비교하면, Then 일치율 85% 이상(D9 제안 기준, 순서 무관).

**9. 의존성 및 확인 사항**

- 선행: FR-005. 후행: 문의별 FR-007·008, 그룹 2, 그룹 3, 그리고 FR-022(답변 병합).
- 결정 필요: D15 답변 병합 방식, D16 상태·SLA 단위, D17 저장 위치, D18 분리 개수 상한.

---

### FR-007. 긴급도 판단

**1. 기능 설명**

- 본문에서 긴급도 urgency_flag를 urgency_codebook.csv의 6값(SAFETY, SITE_DOWN, PROD_IMPACT, COMMISSION, DEADLINE, NONE) 중 하나로 정한다. 우선순위 규칙(FR-011)의 열쇠다.

**2. 우선순위**

- Must Have

**3. 수행 주체**

- 시스템의 분류 단계(FR-005와 같은 호출 가능)

**4. 입력(Input)**

- inquiry_body, body_language, category_code(FR-005 결과), received_at(기한 임박 판단용).

**5. 처리(Process)**

1. urgency_codebook.csv의 6값과 설명(안전 위험 = 발연·화재·감전·과열·아크 / 설비·라인 전체 정지 / 생산·운전 영향 또는 반복 트립 / 시운전 일정 차질 / 고객이 명시한 기한 임박 / 특이사항 없음)을 그대로 판단 기준으로 쓴다.
2. 응답은 urgency_flag, 근거 문장으로만 받는다.
3. 둘 이상 해당하면 SAFETY > SITE_DOWN > PROD_IMPACT > COMMISSION > DEADLINE 순으로 높은 것을 택한다(priority_rules.csv의 적용 순서와 같은 방향).
4. urgency_codebook.csv의 6개의 값 밖이면 1회 재요청, 다시 실패하면 NONE으로 두고 "긴급도 판정 실패" 표시.

**6. 출력(Output)**

- 티켓의 urgency_flag, 근거 문장, 판정 실패 표시.
- 사용자 표시: 티켓 상세에 긴급도와 근거 문장. SAFETY·SITE_DOWN은 강조.

**7. 예외 처리(Exception)**

| 상황 | 시스템 대응 |
| --- | --- |
| 판정 실패 2회 | NONE + 실패 표시. 우선순위는 NONE 기준으로 계산되므로 상담원이 조정(FR-028)할 수 있게 강조 |
| 기한(DEADLINE)이 본문에 있으나 날짜가 이미 지남 | DEADLINE으로 두되 "기한 경과" 표시 |

**8. 완료 기준(Acceptance Criteria)**

- AC-007-1: Given CSV1-000017(단자 과열·변색, 설비 정지), When 판정하면, Then urgency_flag=SITE_DOWN이고 근거 문장이 기록된다
- AC-007-2: Given CSV1-000004(입찰 기한 2025-10-28 명시), When 판정하면, Then DEADLINE.
- AC-007-3: Given CSV1-000031(매뉴얼 요청, 특이사항 없음), When 판정하면, Then NONE.
- AC-007-4: Given test 597건 중 SAFETY인 행, When 채점하면, Then 재현율 100%; SITE_DOWN 재현율 97% 이상.

**9. 의존성 및 확인 사항**

- 선행: FR-004, FR-005. 후행: FR-011.

---

### FR-008. 제공 항목 추출

**1. 기능 설명**

- 본문·전화 메모에 적힌 값을 info_field_codebook.csv의 항목 이름(32종)과 함께 뽑아 "제공된 항목" 목록을 만든다. 필수정보 확인(FR-013), 숫자 조회(FR-017), 고장 진단의 입력이 된다.

**2. 우선순위**

- Must Have

**3. 수행 주체**

- 시스템의 추출 단계(LLM 호출)

**4. 입력(Input)**

- inquiry_body, body_language, product_code(입력값 또는 비움), category_code, product_family.
- 추출 대상 항목: required_info.csv에서 해당 product_family × category_code의 required_fields에 있는 항목을 우선 찾고, 그 밖에 본문에 있는 코드북 항목도 찾는다.

**5. 처리(Process)**

1. 코드북 32항목과 라벨을 넣고, 본문에 값이 있는 항목만 {항목, 값, 본문 위치}로 돌려받는다(구조화 출력).
2. 항목 이름이 코드북 밖이면 그 항목만 버린다.
3. 값 정리: 펌웨어 버전은 숫자·점만("3.40"), 제품 코드는 product_master.csv와 대조해 표기 통일, 날짜는 YYYY-MM-DD, 수량은 정수.
4. product_code가 입력에 없고 본문에서 product_model이 나오면 product_master.csv와 대조해 티켓의 product_code로 채운다. 대조 실패 시 "제품 미확정" 표시.
5. 에러 코드(error_code), 펌웨어 버전(current_fw)은 별도 칸에도 복사해 그룹 3이 바로 쓰게 한다.

**6. 출력(Output)**

- 티켓의 제공 항목 목록(항목, 값, 본문 위치), product_code(보완된 경우), error_code_reported, fw_version_reported, 제품 미확정 표시.
- 사용자 표시: 티켓 상세에 "본문에서 찾은 정보" 표와 본문의 해당 위치 강조.

**7. 예외 처리(Exception)**

| 상황 | 시스템 대응 |
| --- | --- |
| 본문에 항목이 하나도 없음 | 빈 목록. FR-013이 모든 필수 항목을 "누락"으로 판정 |
| 같은 항목에 값이 둘(예: 제품 코드 두 개) | 둘 다 기록하고 "값 충돌" 표시. 제품 코드 충돌이면 product_code는 입력값 우선 |
| 값 형식이 코드북 라벨과 안 맞음(예: 펌웨어 "v3.4a") | 원문을 보존하고 정리값은 비움, "형식 확인" 표시 |
| LLM 실패 | 1회 재시도, 실패 시 빈 목록 + "추출 실패" 표시. 흐름은 계속(필수정보는 모두 누락으로 보임) |

**8. 완료 기준(Acceptance Criteria)**

- AC-008-1: Given CSV1-000004 본문, When 추출하면, Then product_model=HMI-XGT-eXP60, quantity=1, incoterms=CIF Le Havre, required_date=2025-10-28 네 항목이 나온다(정답지 provided_info와 일치).
- AC-008-2: Given CSV1-000008 본문(현재 3.40, 3.50으로 업데이트 요청), When 추출하면, Then current_fw=3.40이 fw_version_reported에 들어가고 product_model, tool_version, logs도 제공 항목에 있다.
- AC-008-3: Given CSV1-001112 본문(E.OC 트립), When 추출하면, Then error_code=E.OC가 error_code_reported에 들어간다.
- AC-008-4: Given product_code를 비우고 본문에 "HMI-XGT-eXP60"이 있는 접수, When 추출하면, Then 티켓의 product_code가 HMI-XGT-eXP60으로 채워진다.
- AC-008-5: Given test 597건, When provided_info를 채점하면, Then 항목 집합 일치율이 90% 이상(D9 제안 기준, missing_blocking_info 기준과 같은 값).

**9. 의존성 및 확인 사항**

- 선행: FR-004, FR-005, 기준 데이터 적재(info_field_codebook.csv, required_info.csv, product_master.csv). 후행: FR-013, FR-017, FR-018(확장).
- 기술 설계서로 넘길 것: 추출 프롬프트, 값 정리 규칙의 세부, 본문 위치 표기 방식.

---

### 이 그룹에서 새로 생긴 결정 필요 사항 (그룹 1)

| 번호 | 항목 | 내용 |
| --- | --- | --- |
| 1 | FR-001 | customers.csv(고객 테이블)에서 관리하지 않는 고객이 C/S 문의를 한 경우 어떻게 처리할 것인가? |
| 2 | FR-003 | "FR-003”의 경우 실제 사용자가 사용하는 기능이 아니다. 시연 및 개발 테스트 사용하기 위한 기능이다. |
| 3 | FR-004 | 언어의 경우 테이블에 코드로 관리할 것인가? |
| 4 | FR-007 | urgency_codebook.csv의 6값을 확인한다. 회의에서 언급한 적 없음. |

---

## 그룹 2. 규칙 적용 (FR-010, 011, 012, 013, 014)

상태: 승인 (2026-10-10). 이 그룹은 LLM 없이 규칙표(ref/ CSV)를 조회해 결과를 정한다. 네 규칙표는 4,000건 정답지와 다음처럼 맞는 것을 확인했다: 우선순위 규칙 재계산 3,880/4,000 일치(나머지 120건은 상담원 조정), 부서 = 규칙의 1차 담당 4,000/4,000, 필수정보·막는 정보 재계산 4,000/4,000, SLA 목표 4,000/4,000. 새 결정 사항은 D13부터.

공통 원칙: 조회 결과와 함께 "어느 표의 어느 행을 썼는지"(rule_id, sla_id 등)를 티켓에 남긴다. 이것이 FR-024 근거 표시의 재료다.

복합 문의: 이 그룹의 다섯 기능은 FR-006이 나눈 문의마다 따로 실행한다(문의별 파이프라인). 정답지의 priority_rule_id, assigned_dept, SLA 열은 category_code 기준으로 하나씩만 있으므로, 유형이 정답 category_code와 같은 문의만 아래 AC로 채점하고 나머지 문의는 채점하지 않는다.

---

### FR-010. 고객·제품 조회

**1. 기능 설명**

- 티켓의 customer_id와 product_code로 고객 기준정보(customers.csv)와 제품 기준정보(product_master.csv)를 읽어 뒤 단계가 쓰는 값을 티켓에 붙인다.

**2. 우선순위**

- Must Have

**3. 수행 주체**

- 시스템(표 조회)

**4. 입력(Input)**

- customer_id(필수, FR-001에서 검증됨), product_code(FR-001 입력 또는 FR-008 보완값, 비어 있을 수 있음).

**5. 처리(Process)**

1. customers.csv에서 tier(PLATINUM/GOLD/STANDARD), segment, country를 읽어 티켓에 붙인다.
2. product_code가 있으면 product_master.csv에서 family, family_name, tech_support_dept, has_firmware, fw_latest, std_lead_time_weeks, list_price_usd, moq, warranty_months, doc_ids를 읽어 티켓에 붙인다.
3. product_code가 비어 있으면 제품 관련 값은 비워 두고 "제품 미확정" 표시를 유지한다.

**6. 출력(Output)**

- 티켓의 customer_tier, customer_segment, country, product_family, 제품 기준값 묶음.
- 사용자 표시: 티켓 상세 머리에 고객 등급·국가·세그먼트, 제품명·제품군·담당 기술지원 부서.

**7. 예외 처리(Exception)**

| 상황 | 시스템 대응 | 사용자에게 보이는 것 |
| --- | --- | --- |
| customer_id 조회 실패(적재 누락) | 흐름 중단, 실행 로그에 기록 | "고객 기준정보를 읽을 수 없음. 데이터 적재 확인" |
| product_code 비어 있음 | 제품 값 비움, 뒤 단계는 제품군 없이 진행(FR-012·013은 제품군이 필요하므로 "제품 확인 필요"로 멈춤) | 티켓 상세에 제품 선택 드롭다운 |
| 제품이 단종(lifecycle_status가 생산 종료) | 조회는 정상, 표시만 추가 | "단종 제품" 표시 |

**8. 완료 기준(Acceptance Criteria)**

- AC-010-1: Given CSV1-000017(CUST-0350, ACB-AS-2000), When 조회하면, Then customer_tier=PLATINUM, country=TH, product_family=LV_BREAKER, tech_support_dept=TS_LV가 티켓에 붙는다(추적표 §1).
- AC-010-2: Given product_code가 비어 있고 FR-008도 제품을 찾지 못한 티켓, When 조회하면, Then 제품 값이 비어 있고 티켓 상세에 제품 선택 드롭다운이 보이며 FR-012·013은 "제품 확인 필요" 상태로 멈춘다.
- AC-010-3: Given 상담원이 드롭다운에서 제품을 고른 경우, When 저장하면, Then FR-010부터 흐름이 다시 돌아 FR-012·013 결과가 채워진다.

**9. 의존성 및 확인 사항**

- 선행: 기준 데이터 적재, FR-001, FR-008. 후행: FR-011~014, FR-017.

---

### FR-011. 우선순위 계산

**1. 기능 설명**

- 문의 유형(category_code)과 긴급도(urgency_flag)로 우선순위 규칙(priority_rules.csv 7행)을 위에서부터 첫 일치로 찾아 P1~P4와 적용 규칙 ID를 정한다.

**2. 우선순위**

- Must Have

**3. 수행 주체**

- 시스템(규칙 엔진)

**4. 입력(Input)**

- category_code(FR-005, 10종 중 하나), urgency_flag(FR-007, 6값 중 하나). 둘 중 하나라도 비어 있으면 실행하지 않는다.

**5. 처리(Process)**

1. priority_rules.csv를 order 오름차순으로 읽는다.
2. 각 행의 condition을 판정한다. 조건은 표에 적힌 그대로다: PR-01 urgency=SAFETY(모든 유형) → P1 / PR-02 SITE_DOWN이고 유형∈{DEFECT, INSTALL, FW_UPDATE} → P1 / PR-03 SITE_DOWN이고 유형∈{ORDER_LEAD, RETURN, WARRANTY} → P2 / PR-04 urgency∈{PROD_IMPACT, COMMISSION} → P2 / PR-05 유형∈{DEFECT, INSTALL, FW_UPDATE, WARRANTY, RETURN, ORDER_LEAD} → P3 / PR-06 DEADLINE이고 정보성 유형 → P3 / PR-07 그 외 정보 요청(TECH_SPEC, MANUAL, COMPLIANCE, QUOTE) → P4.
3. 처음 맞는 행의 priority와 rule_id를 티켓에 기록하고, 판정 과정(각 행의 ✓/✗)을 근거로 남긴다.
4. 규칙 조건 문구는 코드에 박지 않고 표에서 읽을 수 있는 형태로 둔다(기술 설계서에서 조건 표현 방식을 정함).

**6. 출력(Output)**

- 티켓의 priority(규칙값), priority_rule_id, 판정 과정 표.
- 사용자 표시: "P1 — PR-02: SITE_DOWN이고 DEFECT" 식으로 규칙 ID와 조건.

**7. 예외 처리(Exception)**

| 상황 | 시스템 대응 | 사용자에게 보이는 것 |
| --- | --- | --- |
| 어느 행도 맞지 않음(코드값이 표 밖) | priority 비움, "우선순위 미정" 표시, SLA 목표도 비움 | 상담원이 FR-028로 직접 지정 |
| category_code 또는 urgency_flag가 비어 있음(분류 실패) | 실행 안 함 | "분류 뒤 계산됨" |
| 상담원이 조정한 뒤 흐름이 다시 돌 때 | 규칙값은 다시 계산하되 조정값(FR-028)을 덮어쓰지 않는다 | 규칙값과 조정값을 나란히 표시 |

**8. 완료 기준(Acceptance Criteria)**

- AC-011-1: Given DEFECT + SITE_DOWN(CSV1-000017), When 계산하면, Then P1, PR-02이고 판정 과정에 PR-01 ✗, PR-02 ✓가 남는다.
- AC-011-2: Given QUOTE + DEADLINE(CSV1-000004), When 계산하면, Then P3, PR-06.
- AC-011-3: Given MANUAL + NONE(CSV1-000031), When 계산하면, Then P4, PR-07(정답지의 P3는 상담원 조정값이며 priority_rule_id는 PR-07로 같다).
- AC-011-4: Given test 597건, When priority_rule_id를 채점하면, Then 100% 일치. priority는 priority_adjusted_by_agent=N인 행에서 100% 일치.

**9. 의존성 및 확인 사항**

- 선행: FR-005, FR-007. 후행: FR-014, FR-028.

---

### FR-012. 부서 배정

**1. 기능 설명**

- 제품군(product_family)과 문의 유형(category_code)으로 배정 규칙(routing_rules.csv)을 찾아 1차 담당 부서(assigned_dept)와 이관 조건을 정한다. 반품은 사유에 따라 두 갈래다.

**2. 우선순위**

- Must Have

**3. 수행 주체**

- 시스템(규칙 엔진)

**4. 입력(Input)**

- product_family(FR-010), category_code(FR-005), 반품 사유 구분(RETURN일 때만: 불량 / 비불량 / 미확인. FR-008이 뽑은 return_reason 값으로 정한다, 아래 5-3).

**5. 처리(Process)**

1. 기본 행: rule_id = "RT-{family}-{category}" 행을 찾는다(rule_source가 CATEGORY_DEFAULT 또는 FAMILY_OVERRIDE). 102 + 5 = 107행.
2. 반품 분기: category_code=RETURN이면 반품 사유 구분이 "비불량"(오배송·주문 착오·잉여·변심)일 때 기본 행 대신 RT-ALL-RETURN-NON_DEFECT(SCM)를 쓴다. "불량"(DOA·품질)이면 기본 행(WARRANTY_DESK). "미확인"이면 기본 행을 쓰되 "반품 사유 확인 필요" 표시를 켠다.
3. 반품 사유 구분은 MVP에서는 FR-008이 뽑은 return_reason 값에 대한 단어 규칙으로 정한다(비불량 단어 목록은 기술 설계서). 확장 기능 FR-009(LLM 판별)가 들어오면 그 결과로 바꾼다 (D13).
4. rule_source=ESCALATION인 3행(RT-ESC-DEFECT-RMA/ONSITE/SAFETY)은 1차 배정에 쓰지 않는다. 이관 후보(FR-020, 확장)의 재료다.
5. 찾은 행의 primary_dept를 assigned_dept로, rule_id를 routing_rule_id로, escalation_dept와 escalation_condition을 "이관 조건"으로 티켓에 기록한다.
6. departments.csv에서 부서 이름(한/영)을 읽어 표시용으로 붙인다.

**6. 출력(Output)**

- 티켓의 assigned_dept, routing_rule_id, 이관 조건(부서·조건 문구), 반품 사유 구분과 확인 필요 표시.
- 사용자 표시: "담당: TS_LV(저압 기술지원) — RT-LV_BREAKER-DEFECT. 이관 조건: 현장 확인이 필요한 경우 → FIELD_SVC".

**7. 예외 처리(Exception)**

| 상황 | 시스템 대응 | 사용자에게 보이는 것 |
| --- | --- | --- |
| 해당 family × category 행이 없음(CONTROL·MV_EQUIP·TRANSFORMER × FW_UPDATE: 펌웨어 없는 제품군) | assigned_dept 비움, "배정 규칙 없음 — 분류 재검토" 표시. 그래도 접수함에는 GCS_L1(1차 상담)로 보임 | 유형 또는 제품을 다시 고르라는 안내 |
| product_family 없음(제품 미확정) | 실행 안 함, GCS_L1 접수함에 둠 | "제품 확인 뒤 배정됨" |
| RETURN인데 return_reason이 추출되지 않음 | 미확인 → 기본 행 + 확인 필요 표시 | 상담원이 사유 선택(불량/비불량)하면 재배정 |

**8. 완료 기준(Acceptance Criteria)**

- AC-012-1: Given LV_BREAKER + DEFECT(CSV1-000017), When 배정하면, Then assigned_dept=TS_LV, routing_rule_id=RT-LV_BREAKER-DEFECT, 이관 조건에 FIELD_SVC가 보인다.
- AC-012-2: Given HMI + RETURN, 사유 "품질 불량"(CSV1-000097), When 배정하면, Then WARRANTY_DESK, RT-HMI-RETURN. Given MV_EQUIP + RETURN, 사유 "오배송"(CSV1-000039), When 배정하면, Then SCM, RT-ALL-RETURN-NON_DEFECT(추적표 §4).
- AC-012-3: Given RETURN인데 사유를 뽑지 못한 티켓, When 배정하면, Then 기본 행으로 배정되고 "반품 사유 확인 필요" 표시가 켜지며, 상담원이 사유를 고르면 재배정된다.
- AC-012-4: Given CONTROL + FW_UPDATE, When 배정하면, Then 부서가 비고 "배정 규칙 없음 — 분류 재검토"가 표시된다.
- AC-012-5: Given test 597건 중 category_code가 정답과 같은 행, When routing_rule_id와 assigned_dept를 채점하면, Then 100% 일치(반품 사유 구분이 정답과 같은 행 기준; 다른 행은 D13의 판별 정확도 문제로 따로 집계).

**9. 의존성 및 확인 사항**

- 선행: FR-005, FR-008(return_reason), FR-010. 후행: FR-029(접수함 부서 필터), FR-020·033(확장).
- D13(신규): 반품 사유 구분을 MVP에서 단어 규칙으로 할지, FR-009(LLM 판별)를 MVP로 올릴지. 정답지의 반품 350건 중 176건이 비불량(SCM) 행이라 이 분기 없이는 부서 일치율이 반품에서 절반이 틀린다.

---

### FR-013. 필수정보 확인

**1. 기능 설명**

- 제품군 × 문의 유형의 필수 항목(required_info.csv의 required_fields)과 막는 항목(blocking_fields)을 FR-008의 제공 항목과 대조해, 빠진 항목(missing_info)과 그중 막는 항목(missing_blocking_info)을 정한다.

**2. 우선순위**

- Must Have

**3. 수행 주체**

- 시스템(표 대조)

**4. 입력(Input)**

- product_family, category_code, 제공 항목 목록(FR-008의 항목 이름 집합).

**5. 처리(Process)**

1. required_info.csv에서 (family, category) 행을 찾는다(110행, 모든 조합이 있다).
2. missing_info = required_fields − 제공 항목. missing_blocking_info = blocking_fields − 제공 항목. 순서는 표의 순서를 유지한다.
3. 항목마다 field_labels의 라벨을 붙인다(요청 문안과 화면 표시용).
4. missing_blocking_info가 비어 있지 않으면 "정보 요청 필요" 상태로 표시하고 FR-015로 넘긴다. 비어 있으면 근거·초안 단계로 넘긴다.
5. 빠진 항목이 있어도 본문에 값이 있을 수 있으므로(FR-008 누락), 상담원이 티켓 상세에서 "제공됨"으로 바꾸면 다시 계산한다.

**6. 출력(Output)**

- 티켓의 missing_info, missing_blocking_info(각 항목 이름 목록), 정보 요청 필요 여부.
- 사용자 표시: 필수 항목 체크리스트(제공됨 ✓ / 빠짐 / 막는 항목은 강조).

**7. 예외 처리(Exception)**

| 상황 | 시스템 대응 | 사용자에게 보이는 것 |
| --- | --- | --- |
| product_family 또는 category_code 없음 | 실행 안 함 | "제품·유형 확인 뒤 계산됨" |
| 제공 항목이 비어 있음(추출 실패) | 모든 필수 항목이 빠짐으로 계산, "추출 실패" 표시 유지 | 체크리스트 전부 빠짐 + 추출 실패 안내 |
| 상담원이 체크리스트를 손으로 바꿈 | 변경 기록을 남기고 재계산 | 변경 뒤 상태 |

**8. 완료 기준(Acceptance Criteria)**

- AC-013-1: Given CSV1-000017(LV_BREAKER × DEFECT, 제공: product_model, error_code, load_profile), When 대조하면, Then missing_info = serial_no, operating_condition, photos / missing_blocking_info = serial_no (정답지와 같음).
- AC-013-2: Given CSV1-000004(제공 4항목이 필수 4항목과 같음), When 대조하면, Then 둘 다 비어 있고 정보 요청 필요가 꺼져 있다.
- AC-013-3: Given 상담원이 serial_no를 "제공됨"으로 바꾼 경우, When 저장하면, Then missing_blocking_info에서 serial_no가 빠지고 정보 요청 필요가 꺼진다.
- AC-013-4: Given test 597건 중 provided_info가 정답과 같은 행, When 채점하면, Then missing_info·missing_blocking_info 100% 일치(표 대조는 결정적). 전체 행 기준 일치율은 FR-008 정확도에 좌우되며 90% 이상(D9).

**9. 의존성 및 확인 사항**

- 선행: FR-005, FR-008, FR-010. 후행: FR-015, FR-025(WAITING_CUSTOMER 전이는 요청을 보낼 때, 그룹 3·4).
- 데이터 주의: 정답지에서 막는 항목이 빠졌는데 요청을 보내지 않은 건이 7건 있다(info_request_sent=N). 요청 발송 여부는 이 기능이 아니라 FR-015·031에서 상담원이 정한다.

---

### FR-014. SLA 목표 설정

**1. 기능 설명**

- 문의 유형 × 고객 등급 × 우선순위로 SLA 정책(sla_policy.csv 120행)을 찾아 1차 응답 목표 시간과 해결 목표 시간을 티켓에 기록한다. 우선순위가 바뀌면 다시 찾는다(FR-028).

**2. 우선순위**

- Must Have

**3. 수행 주체**

- 시스템(표 조회)

**4. 입력(Input)**

- category_code, customer_tier(FR-010), priority(조정값이 있으면 조정값, 없으면 FR-011 규칙값).

**5. 처리(Process)**

1. sla_policy.csv에서 (category, customer_tier, priority) 행을 찾는다. 10 × 3 × 4 = 120행, 모든 조합이 있다.
2. first_response_hours → sla_first_response_target_h, resolution_hours → sla_resolution_target_h로 티켓에 기록하고 sla_id를 남긴다.
3. 같은 행의 resolution_definition(무엇이 "해결"인가), at_risk_threshold(경과 ≥ 목표의 75%), pause_rule(WAITING_CUSTOMER 제외), clock(24x7)을 표시용으로 붙인다.
4. 목표 시각 = received_at + 목표 시간은 저장하지 않고 FR-026이 조회 때 계산한다(대기 시간 때문에 고정값이 틀리므로).
5. 우선순위 조정(FR-028)이 들어오면 새 priority로 1~3을 다시 한다. 이전 목표값과 sla_id는 변경 이력으로 남긴다.

**6. 출력(Output)**

- 티켓의 sla_first_response_target_h, sla_resolution_target_h, sla_id, 해결 정의 문구.
- 사용자 표시: "1차 응답 1시간 / 해결 24시간 (SLA-DEFECT-PLATINUM-P1). 해결 = 원인 규명 및 조치 완료".

**7. 예외 처리(Exception)**

| 상황 | 시스템 대응 | 사용자에게 보이는 것 |
| --- | --- | --- |
| priority 없음(규칙 미일치) | 목표 비움, SLA 상태 "미정" | 우선순위 지정 뒤 계산됨 |
| 행이 없음(코드값 밖) | 목표 비움, 실행 로그에 기록 | "SLA 정책 없음 — 데이터 확인" |
| 무응답 종료(CLOSED_NO_RESPONSE) | 목표는 유지하되 FR-026이 상태를 N/A로 판정 | 그룹 4 참조 |

**8. 완료 기준(Acceptance Criteria)**

- AC-014-1: Given DEFECT × PLATINUM × P1(CSV1-000017), When 조회하면, Then 1차 응답 1시간, 해결 24시간, sla_id=SLA-DEFECT-PLATINUM-P1.
- AC-014-2: Given MANUAL × STANDARD × 규칙 P4(CSV1-000031), When 조회하면, Then 72시간 / 168시간. When 상담원이 P3로 조정하면(FR-028), Then 24시간 / 120시간으로 바뀌고 이전 값이 변경 이력에 남는다(추적표 §6).
- AC-014-3: Given test 597건, When sla_first_response_target_h, sla_resolution_target_h를 채점하면, Then 100% 일치(조정 건은 조정값 기준, 데이터로 확인됨).

**9. 의존성 및 확인 사항**

- 선행: FR-005, FR-010, FR-011. 후행: FR-026, FR-027, FR-028.

---

### 이 그룹에서 새로 생긴 결정 필요 사항 (그룹 2)

| 번호 | 항목 | 결정 전 진행 방식 |
| --- | --- | --- |
| D13 | 반품 사유 구분(불량/비불량)을 MVP에서 FR-008 추출값의 단어 규칙으로 할지, 확장 기능 FR-009(LLM 판별)를 MVP로 올릴지. 반품 350건 중 176건이 비불량 행이라 이 분기가 부서 일치율에 직접 영향 | 단어 규칙 + "확인 필요" 표시로 진행, FR-009는 확장 2순위(FR-002 앞)로 올려 둠 |

---

## 그룹 3. 근거와 초안 (FR-015, 016, 017, 021, 022, 023, 024)

상태: 승인 (2026-10-10). 이 그룹은 고객에게 나갈 글(정보 요청, 답변 초안, 진행 안내)을 만든다. 운영 원칙: 글은 문서에서 찾은 절과 표에서 읽은 값만 근거로 쓰고, 인용을 남기며, 발송은 상담원이 한다(그룹 5 FR-031). 새 결정 사항은 D14부터.

복합 문의: FR-015·016·017·021은 FR-006이 나눈 문의마다 따로 실행한다(문의별 파이프라인). 문의별 결과는 FR-022가 하나의 답변으로 합친다.

문서 사실(docs/doc_index.csv): 문서 107개 = 제품 문서 92개(제품 23종 × DS 데이터시트·IG 설치안내·TG 트러블슈팅·RN 릴리스노트) + 정책 4개(POL-ORDER, POL-RETURN, POL-WARRANTY, POL-SERVICE) + 제품군 FAQ 11개. 모두 영어 마크다운이며 "## 2. / ### 2.1" 식 번호 절로 나뉜다. 정답지의 근거 문서는 유형별로 정해져 있다: TECH_SPEC·COMPLIANCE → DS, DEFECT → TG, INSTALL → IG/TG, FW_UPDATE → RN, MANUAL → IG/TG/RN, QUOTE·ORDER_LEAD·RETURN·WARRANTY → POL.

---

### FR-015. 추가정보 요청 메시지 생성

**1. 기능 설명**

- 막는 항목(missing_blocking_info)이 있으면 무엇을 왜 보내 달라는지 고객 언어로 요청 문안을 만들어 상담원 화면에 둔다. 발송은 FR-031에서 상담원이 승인한다.

**2. 우선순위**

- Must Have

**3. 수행 주체**

- 시스템(문안 생성, LLM 호출 1회), 상담원(승인·발송)

**4. 입력(Input)**

- missing_blocking_info와 missing_info(FR-013, 항목 이름 + field_labels 라벨), language(FR-004), 제품명, 문의 유형, 채널.

**5. 처리(Process)**

1. 막는 항목이 없으면 실행하지 않는다.
2. 요청 항목 = 막는 항목 전부 + 빠진 항목 중 함께 받으면 좋은 것(missing_info). 막는 항목은 "필수"로, 나머지는 "가능하면"으로 구분한다.
3. 문안은 고객 언어로 쓰되, 항목 이름은 field_labels의 영어 라벨을 괄호로 함께 적는다(고객이 양식 항목을 알아보도록).
4. 문안에 정답지의 info_request_message와 같은 뼈대를 쓴다: 인사 → 처리를 위해 필요한 항목 목록 → 회신 방법 → 감사. 추측한 값이나 기한 약속은 넣지 않는다.
5. 채널이 CHAT이면 3문장 이내, PHONE이면 상담원이 전화로 읽을 체크리스트 형태(고객 언어 + 영어 병기)로 만든다.
6. 결과를 메시지 이력에 종류 INFO_REQUEST, 상태 "초안"으로 저장한다(FR-035). 승인·발송과 WAITING_CUSTOMER 전이는 FR-031·025.

**6. 출력(Output)**

- INFO_REQUEST 초안 1건(언어, 본문, 요청 항목 목록).
- 사용자 표시: 티켓 상세의 "정보 요청" 탭에 초안과 항목 체크리스트, 승인·수정·발송 버튼.

**7. 예외 처리(Exception)**

| 상황 | 시스템 대응 | 사용자에게 보이는 것 |
| --- | --- | --- |
| LLM 실패 | 1회 재시도. 실패 시 고정 문구 템플릿("We need some additional details before we can help: {labels}.")을 고객 언어 번역 없이 영어로 채우고 "자동 번역 실패" 표시 | 영어 초안 + 표시 |
| 문안에 요청 항목이 빠짐(검사: 막는 항목 라벨이 본문에 없음) | 1회 재생성, 다시 빠지면 빠진 항목을 본문 끝에 목록으로 덧붙임 | 초안 |
| 막는 항목 없음 | 실행 안 함 | 탭 비활성 |

**8. 완료 기준(Acceptance Criteria)**

- AC-015-1: Given CSV1-000017(막는 항목 serial_no, 언어 en, 전화), When 생성하면, Then 영어 체크리스트 형태의 INFO_REQUEST 초안이 생기고 본문에 "Serial number (nameplate)"가 포함된다.
- AC-015-2: Given CSV1-003578(이탈리아 고객, 본문 영어 메모, 막는 항목 있음), When 생성하면, Then 초안 언어가 이탈리아어이고 항목 라벨이 영어로 병기된다.
- AC-015-3: Given 막는 항목이 없는 CSV1-000004, When 흐름이 돌면, Then INFO_REQUEST 초안이 만들어지지 않는다.
- AC-015-4: Given 생성된 초안, When 발송 전 상태를 보면, Then 메시지 이력에 "초안"으로만 있고 티켓 상태는 바뀌지 않는다.

**9. 의존성 및 확인 사항**

- 선행: FR-004, FR-013. 후행: FR-031(승인·발송), FR-025(WAITING_CUSTOMER).

---

### FR-016. 문서 근거 검색

**1. 기능 설명**

- 문의에 맞는 문서 절을 제품 문서 + 정책 4종 + 제품군 FAQ 범위에서 찾아, 문서 ID와 절 번호와 절 본문을 "근거 후보"로 티켓에 붙인다. 답변 초안(FR-021)은 이 후보 안에서만 쓴다.

**2. 우선순위**

- Must Have

**3. 수행 주체**

- 시스템(검색)

**4. 입력(Input)**

- 문의 본문(단일 문의면 inquiry_body 전체, 복합 문의면 FR-006이 나눈 그 문의의 근거 문장; 해석 언어 body_language), 그 문의의 유형, product_code, product_family, 제공 항목(에러 코드, 펌웨어 버전 등).

**5. 처리(Process)**

1. 검색 범위를 먼저 좁힌다(꼬리표 필터): 해당 product_code의 문서(DS, IG, TG, RN) + 정책 4개 + 해당 product_family의 FAQ. 다른 제품의 문서는 제외한다.
2. 유형별 우선 문서 종류를 적용한다(위 문서 사실의 대응표). 예: DEFECT면 TG를 먼저, QUOTE·ORDER_LEAD·RETURN·WARRANTY면 POL을 먼저. 우선 종류에서 못 찾으면 범위 전체로 넓힌다.
3. 절 단위로 검색한다(문서는 "## n." / "### n.m" 절로 미리 쪼개 둔다, 기술 설계서). 에러 코드나 펌웨어 버전처럼 정확한 문자열이 있으면 그 문자열이 들어 있는 절을 우선한다.
4. 상위 k개 절(k는 기술 설계서, 제안 5)을 점수와 함께 "근거 후보"로 문의 순번(seq)과 함께 저장한다.
5. 후보가 비어 있거나 모든 후보의 점수가 기준(기술 설계서) 미만이면 "근거 없음"으로 표시한다. 초안은 만들지 않거나(FR-021 예외) 일반 안내만 쓴다.

**6. 출력(Output)**

- 근거 후보 목록(문의별): 문의 순번, doc_id, 절 번호, 절 제목, 절 본문, 점수.
- 사용자 표시: 티켓 상세 "근거" 탭에 후보 절 목록, 클릭하면 절 본문.

**7. 예외 처리(Exception)**

| 상황 | 시스템 대응 | 사용자에게 보이는 것 |
| --- | --- | --- |
| product_code 없음 | 정책 4개 + (제품군 있으면) FAQ만 검색, "제품 문서 미검색" 표시 | 제품 확인 안내 |
| 색인이 없거나 검색 서비스 실패 | 1회 재시도, 실패 시 근거 없음 + "검색 실패" 표시, 흐름은 계속 | 초안 탭에 "근거 없이 초안 불가" |
| 점수가 모두 기준 미만 | 후보는 보여 주되 "관련성 낮음" 표시 | 상담원이 직접 문서 선택 가능 |

**8. 완료 기준(Acceptance Criteria)**

- AC-016-1: Given CSV1-000017(ACB-AS-2000, DEFECT, 과열·변색), When 검색하면, Then 후보에 TG-ACB-AS-2000의 절이 있고 다른 제품의 문서는 없다.
- AC-016-2: Given CSV1-000004(QUOTE), When 검색하면, Then 후보 1순위가 POL-ORDER의 절이다.
- AC-016-3: Given product_code가 비어 있는 티켓, When 검색하면, Then 제품 문서는 검색되지 않고 정책·FAQ만 후보에 있으며 "제품 문서 미검색"이 표시된다.
- AC-016-4: Given test 597건 중 reference_doc_id가 있는 행, When 후보 상위 k개 안에 정답 문서가 있는지 채점하면, Then 85% 이상(D9). reference_section이 있는 행(TECH_SPEC, DEFECT, INSTALL, COMPLIANCE, FW_UPDATE)은 문서+절 일치로도 집계한다.

**9. 의존성 및 확인 사항**

- 선행: 문서 색인(기능 아닌 작업), FR-005·006·008·010. 후행: FR-021, FR-022, FR-024.
- 기술 설계서로 넘길 것: 절 분할 방식, 임베딩·검색 방식, k와 점수 기준.

---

### FR-017. 숫자 표 조회

**1. 기능 설명**

- 가격·표준 납기·최소 주문 수량·사양값·펌웨어 최신 버전을 문서 검색이 아니라 표에서 읽어 "조회값"으로 티켓에 붙인다. 초안(FR-021)은 숫자를 이 조회값에서만 가져온다.

**2. 우선순위**

- Must Have

**3. 수행 주체**

- 시스템(표 조회)

**4. 입력(Input)**

- product_code, category_code, received_at, 제공 항목(current_fw, quantity, 요청 사양 항목명).

**5. 처리(Process)**

1. 가격·납기·MOQ(QUOTE, ORDER_LEAD): product_master.csv의 list_price_usd, std_lead_time_weeks, moq를 읽는다. 수량이 있으면 합계 = 단가 × 수량을 계산한다.
2. 사양값(TECH_SPEC, COMPLIANCE): product_spec_facts.csv(169행: product_code, attribute, value, doc_id, section)에서 문의가 묻는 attribute를 찾는다. 어느 attribute인지는 FR-016의 근거 후보와 제공 항목으로 정하고, 못 정하면 그 제품의 전체 사양 행을 후보로 붙인다.
3. 펌웨어(FW_UPDATE, MANUAL의 릴리스노트 요청): firmware_history.csv(39행)에서 product_code의 행 중 release_date ≤ received_at(날짜 기준)인 것만 남기고 그중 가장 늦은 fw_version을 "접수 시점 최신"으로 정한다. 고객 보고 버전(current_fw)과 비교해 "최신 아님 → 업데이트 안내" 또는 "이미 최신"을 정한다.
4. 모든 조회값에 출처(표 이름, 행 식별자)를 붙여 저장한다.

**6. 출력(Output)**

- 조회값 묶음: {항목, 값, 단위, 출처}. 펌웨어 비교 결과(접수 시점 최신, 고객 버전, 판정).
- 사용자 표시: "표에서 읽은 값" 표. 초안의 숫자 옆에 출처 표시(FR-024).

**7. 예외 처리(Exception)**

| 상황 | 시스템 대응 | 사용자에게 보이는 것 |
| --- | --- | --- |
| product_code 없음 | 조회 안 함, "제품 확인 필요" | 초안에 숫자 없음 |
| 제품에 펌웨어 없음(has_firmware=N)인데 FW_UPDATE로 분류 | 조회값 없음 + "펌웨어 없는 제품 — 분류 재검토" | 안내 |
| 접수일 이전 출시 버전이 하나도 없음 | 최신 없음 + 표시 | 안내 |
| 사양 attribute를 못 정함 | 전체 사양 행을 후보로, 상담원이 선택 | 선택 목록 |
| 요청 납기(required_date)가 표준 납기보다 빠름 | 조회값은 그대로, "요청 납기 < 표준 납기" 표시 | 초안에 납기 확정 문구 넣지 않음(운영 원칙: 납기 확정은 사람) |

**8. 완료 기준(Acceptance Criteria)**

- AC-017-1: Given CSV1-000004(HMI-XGT-eXP60, 수량 1), When 조회하면, Then 단가 520.00 USD, 합계 520.00 USD, 표준 납기 4주가 출처 product_master.csv 14행과 함께 붙는다(추적표 §3).
- AC-017-2: Given CSV1-000008(ESS-BMS-V3, 접수 2025-10-01, 고객 3.40), When 조회하면, Then 접수 시점 최신 = 3.40(2025-05-19), 판정 "이미 최신". 3.50(2026-01-19)은 후보에서 제외된다.
- AC-017-3: Given 접수일을 2026-02-01로 한 같은 문의, When 조회하면, Then 접수 시점 최신 = 3.50, 판정 "업데이트 안내".
- AC-017-4: Given test 597건의 TECH_SPEC 행, When 조회값이 정답 final_reply의 사양 숫자와 같은지 채점하면, Then 100%(표 값 그대로이므로).
- AC-017-5: Given 초안(FR-021)에 들어간 모든 숫자, When 조회값과 대조하면, Then 조회값에 없는 숫자가 없다.

**9. 의존성 및 확인 사항**

- 선행: FR-008, FR-010, 기준 데이터 적재. 후행: FR-021, FR-024.
- D14(신규): 정답지의 견적 단가와 납기는 표 값과 다른 건이 많다(영어 견적 89건 중 54건이 정가와 다른 단가, 할인율 제각각; 견적·납기 답변 271건 중 156건이 표준 납기와 다른 주 수). 기준이 없으므로(팀 정리 §7 질문 4와 같은 성격) MVP는 정가·표준 납기만 안내하고, 이 항목의 정답지 채점은 "표 값 일치"로만 한다.

---

### FR-021. 답변 초안 생성

**1. 기능 설명**

- FR-016의 근거 절과 FR-017의 조회값만 사용해 고객 언어로 답변 초안을 쓰고, 어느 절과 어느 값을 썼는지 인용을 함께 남긴다. 발송은 상담원이 한다(FR-031).

**2. 우선순위**

- Must Have

**3. 수행 주체**

- 시스템(LLM 호출 1회), 상담원(수정·승인)

**4. 입력(Input)**

- 문의 본문(FR-016 입력과 같음), language, 그 문의의 유형, 그 문의의 근거 후보(FR-016), 조회값(FR-017), 제공 항목, 막는 항목 여부(FR-013).

**5. 처리(Process)**

1. 막는 항목이 있으면 답변 초안 대신 정보 요청(FR-015)만 만든다. 단, 막는 항목 없이 빠진 항목만 있으면 초안을 만들고 끝에 "가능하면 보내 주실 것" 한 줄을 넣는다.
2. 근거 후보가 없으면(FR-016 근거 없음) 초안을 만들지 않고 "근거 없음 — 상담원 작성 필요" 표시만 남긴다.
3. 초안 작성 지시: 근거 절 본문과 조회값만 사실로 쓴다 / 절에 없는 내용은 쓰지 않는다 / 숫자는 조회값만 쓴다 / 인용은 "(DS-CONT-MC-32a §2.1)" 형식으로 문장 끝에 단다 / 유형별 뼈대를 따른다(아래) / 승인·거절·납기 확정 문구는 쓰지 않는다.
4. 유형별 뼈대(정답지 final_reply의 형태): QUOTE = 제품·수량·단가·합계·표준 납기·유효기간 30일 / ORDER_LEAD = 표준 납기(확정 출하일은 쓰지 않음) / TECH_SPEC·COMPLIANCE = 묻는 사양값 + 출처 절 + 데이터시트 첨부 안내 / DEFECT·INSTALL = 원인 후보·점검 순서(TG/IG 절) / FW_UPDATE = 현재 버전·접수 시점 최신·업데이트 또는 이미 최신 + RN 인용 / RETURN·WARRANTY = 해당 정책 조항과 필요한 서류, 판정은 사람이 한다는 안내 / MANUAL = 해당 문서 ID와 절 안내.
5. 생성 후 자체 대조: 초안 속 인용이 모두 근거 후보 안에 있는지, 초안 속 숫자가 모두 조회값에 있는지 검사한다. 어긋나면 1회 재생성, 다시 어긋나면 어긋난 자리를 표시해 상담원에게 넘긴다.
6. 단일 문의면 메시지 이력에 종류 FINAL_REPLY, 상태 DRAFT로 저장한다(FR-035). 복합 문의면 문의별 초안을 FR-022로 넘기고, 합친 답변 하나만 FINAL_REPLY·DRAFT로 저장한다.

**6. 출력(Output)**

- 초안 본문(고객 언어), 인용 목록(doc_id, 절), 사용한 조회값 목록, 자체 대조 결과.
- 사용자 표시: 티켓 상세 "답변 초안" 탭. 인용과 숫자에 출처 표시, 어긋난 자리는 강조.

**7. 예외 처리(Exception)**

| 상황 | 시스템 대응 | 사용자에게 보이는 것 |
| --- | --- | --- |
| LLM 실패 | 1회 재시도, 실패 시 초안 없음 + 표시 | "초안 생성 실패. 다시 시도" |
| 자체 대조 2회 실패 | 초안은 두되 어긋난 문장 강조, 승인 버튼 옆에 경고 | 경고 |
| 언어가 15개 밖 | 발생하지 않음(FR-001 검증) | — |
| 초안 길이 초과(제안 상한 1,500자) | 재생성 1회, 그래도 길면 그대로 두고 표시 | 표시 |

**8. 완료 기준(Acceptance Criteria)**

- AC-021-1: Given CSV1-000004, When 초안을 만들면, Then 프랑스어이고 "520.00 USD", "4 semaines"(또는 동등 표현), 유효기간 30일이 있으며 숫자 출처가 product_master.csv로 표시된다.
- AC-021-2: Given CSV1-000008(아랍어, 접수 시점 최신 3.40), When 초안을 만들면, Then "이미 최신" 취지의 아랍어 문장과 RN-ESS-BMS-V3 인용이 있고, 3.50은 나오지 않는다.
- AC-021-3: Given 근거 후보가 비어 있는 티켓, When 흐름이 돌면, Then 초안이 생성되지 않고 "근거 없음 — 상담원 작성 필요"가 표시된다.
- AC-021-4: Given 생성된 초안 30건 표본(D9), When 인용과 숫자를 사람이 대조하면, Then 근거 밖 인용과 조회값 밖 숫자가 0건이다.
- AC-021-5: Given test 597건, When 초안을 정답 final_reply와 비교하면, Then 참고 점수로만 기록하고 성공 기준에는 넣지 않는다(문장 일치가 불가능).

**9. 의존성 및 확인 사항**

- 선행: FR-004, 013, 016, 017. 후행: FR-022, FR-024, FR-031.
- 기술 설계서로 넘길 것: 프롬프트, 유형별 뼈대 템플릿, 자체 대조 구현, 길이 상한.

---

### FR-022. 복합 문의 답변 병합

**1. 기능 설명**

- 복합 문의면 문의별 파이프라인 n개가 만든 초안(FR-021)을 고객에게 보내는 답변 하나로 합친다(D15의 진행 방식). 인용 목록과 조회값 목록도 합친다. 정답지에는 secondary_category 쪽 문의의 답이 없으므로(팀 정리 §1) 그 부분의 채점은 "답 존재와 근거 유무"로만 한다.

**2. 우선순위**

- Should Have (MVP 포함)

**3. 수행 주체**

- 시스템(모든 문의 파이프라인이 끝난 뒤 실행. LLM 호출 1회로 할지 템플릿 결합으로 할지는 기술 설계서)

**4. 입력(Input)**

- 문의별 초안 n개(순번, 유형, 본문, 인용 목록, 조회값 목록, 자체 대조 결과), language, 문의별 담당 부서(FR-012).

**5. 처리(Process)**

1. 정보 요청(FR-015)으로 간 문의는 "끝난 것"으로 보지 않는다. 그 문의의 정보 요청은 문의별로 먼저 발송하고, 답변 병합은 모든 문의가 답변 초안까지 간 뒤에 한다(D15 결정 전 기본값). 모든 문의 파이프라인이 끝날 때까지 기다린다. 실패한 파이프라인이 있으면 나머지로 진행하고 그 문의 자리에 "해당 요청은 확인 후 별도로 안내" 한 문장을 넣는다.
2. 인사말·맺음말은 한 번만 쓰고, 문의별 답을 본문 순서(순번)대로 단락으로 잇는다. 단락 내용은 바꾸지 않는다(새 사실·숫자를 더하지 않음).
3. 근거가 없어 초안이 없는 문의(FR-021 근거 없음)도 "확인 후 별도 안내" 한 문장으로 채우고 그 문의에 "근거 없음" 표시를 켠다.
4. 합친 답변에 FR-021 5번의 자체 대조를 한 번 더 한다(인용·숫자가 각 문의의 근거·조회값 안에 있는지).
5. 문의마다 담당 부서가 다르면 상담원 화면에만 "문의 {순번} 담당: {부서}" 메모를 표시한다(고객 문안에는 넣지 않음).
6. 메시지 이력에 종류 FINAL_REPLY, 상태 DRAFT로 하나만 저장한다(FR-035).

**6. 출력(Output)**

- 합친 답변 본문, 합친 인용 목록(문의 순번 포함), 문의별 근거 없음·실패 표시, 상담원용 담당 메모.

**7. 예외 처리(Exception)**

| 상황 | 시스템 대응 |
| --- | --- |
| 합친 답변에서 문의 단락이 빠짐(검사: 단락 수 < 문의 수) | 1회 재생성, 실패 시 "문의 답 누락" 표시 |
| 합친 뒤 자체 대조 실패 | 어긋난 문장 강조, 승인 버튼 옆 경고 |
| 파이프라인 하나가 끝나지 않음(시간 초과, 기준은 기술 설계서) | 끝난 문의만 합치고 남은 문의는 "확인 후 별도 안내" |

**8. 완료 기준(Acceptance Criteria)**

- AC-022-1: Given CSV1-000008(FW_UPDATE;MANUAL), When 답변을 만들면, Then 답변 하나에 펌웨어 단락(RN 인용)과 매뉴얼 단락(IG 또는 RN 인용)이 모두 있고, 각 인용이 해당 문의의 근거 후보 안에 있다.
- AC-022-2: Given 한 문의의 근거 후보가 비어 있는 복합 문의, When 답변을 만들면, Then 그 문의 단락이 "확인 후 별도 안내" 한 문장이고 "근거 없음"이 표시된다.
- AC-022-3: Given test 597건 중 secondary_category가 있는 행, When 채점하면, Then 나눈 모든 문의의 단락이 있는 비율 95% 이상, 인용이 해당 문의의 근거 후보 안에 있는 비율 100%(D9).

**9. 의존성 및 확인 사항**

- 선행: FR-006, 문의별 FR-016·017·021. 후행: FR-024, FR-031.
- 결정 필요: D15(합쳐 보낼지 따로 보낼지).

---

### FR-023. 진행 안내 메시지 생성

**1. 기능 설명**

- 티켓 상태가 바뀔 때 고객 언어로 진행 안내 문안을 만들어 상담원 화면에 둔다. 발송은 상담원 승인으로 한다(D7의 진행 방식). 정답지에 진행 안내 본문이 없으므로 채점은 생성·발송 기록으로만 한다(D2).

**2. 우선순위**

- Should Have (MVP 포함)

**3. 수행 주체**

- 시스템(문안 생성), 상담원(승인·발송)

**4. 입력(Input)**

- 상태 전이 사건(FR-025): 어느 상태에서 어느 상태로, 시각. language, 티켓 요약(유형, 제품), 담당 부서, SLA 목표(FR-014).

**5. 처리(Process)**

1. 안내를 만드는 전이는 네 가지로 고정한다: ① NEW → IN_PROGRESS(접수 확인) ② IN_PROGRESS → ESCALATED(전문 부서 이관 안내. 확장 FR-033 도입 전에는 발생하지 않음) ③ WAITING_CUSTOMER → IN_PROGRESS(회신 수신 확인) ④ → RESOLVED(해결 안내; 최종 답변 발송과 같은 때면 만들지 않음).
2. 문안 내용은 사실만: 현재 상태, 담당 부서 이름, 다음 단계. SLA 목표 시간을 고객에게 약속으로 쓰지 않는다(운영 원칙). 예상 완료 시각은 넣지 않는다.
3. 고객 언어로 쓰고, 메시지 이력에 종류 PROGRESS_NOTICE, 상태 "초안"으로 저장한다.
4. 같은 전이에 대한 초안이 이미 있으면 새로 만들지 않는다.

**6. 출력(Output)**

- PROGRESS_NOTICE 초안 1건(전이 종류, 언어, 본문).
- 사용자 표시: 티켓 상세 "진행 안내" 탭에 초안, 승인·발송 버튼. 승인 전 초안이 있으면 접수함에 표시.

**7. 예외 처리(Exception)**

| 상황 | 시스템 대응 |
| --- | --- |
| LLM 실패 | 영어 고정 문구 템플릿으로 채우고 "자동 번역 실패" 표시 |
| 전이가 네 가지 밖(예: IN_PROGRESS → CLOSED 무응답 종료) | 만들지 않음 |
| 상담원이 발송하지 않고 다음 전이가 일어남 | 이전 초안은 "미발송"으로 남기고 새 초안 생성 |

**8. 완료 기준(Acceptance Criteria)**

- AC-023-1: Given 새 티켓의 처리 흐름이 끝나 NEW → IN_PROGRESS가 되면, When 전이가 기록되면, Then 고객 언어의 접수 확인 초안이 PROGRESS_NOTICE로 1건 생긴다.
- AC-023-2: Given WAITING_CUSTOMER 티켓에 고객 회신이 입력되면(FR-032), When 상태가 IN_PROGRESS로 바뀌면, Then 회신 수신 확인 초안이 생긴다.
- AC-023-3: Given 생성된 안내 초안, When 본문을 검사하면, Then SLA 목표 시간이나 완료 예정 시각이 들어 있지 않다.
- AC-023-4: Given 같은 전이가 두 번 기록된 경우(재시도), When 확인하면, Then 초안은 1건이다.

**9. 의존성 및 확인 사항**

- 선행: FR-004, FR-025, FR-035. 후행: FR-031.
- D2·D7에 따른 진행: 정답 없음, 발송은 상담원.

---

### FR-024. 근거 표시

**1. 기능 설명**

- 상담원 화면에 "왜 이 결과인가"를 보여 준다: 분류의 근거 문장, 적용된 규칙 ID와 조건 판정, 인용 문서·절, 조회한 표 값, 추출한 항목과 본문 위치. 사람이 확인·승인하는 데 필요한 재료를 한 화면에 모은다.

**2. 우선순위**

- Must Have

**3. 수행 주체**

- 시스템(화면 구성), 상담원(열람)

**4. 입력(Input)**

- 그룹 1~3의 모든 결과물에 붙어 있는 근거: FR-005·006·007 근거 문장, FR-008 항목·위치, FR-011 판정 과정, FR-012 rule_id·이관 조건, FR-013 체크리스트, FR-014 sla_id, FR-016 후보 절, FR-017 조회값·출처, FR-021 인용·자체 대조 결과.

**5. 처리(Process)**

1. 티켓 상세(FR-030) 안에 "근거" 영역을 두고 단계 순서(①~⑧)로 접힌 목록을 보여 준다.
2. 각 항목은 "결과 — 근거" 한 줄 + 펼치면 상세: 예) "P1 — PR-02: SITE_DOWN이고 DEFECT (PR-01 ✗, PR-02 ✓)".
3. 초안 본문의 인용 표시를 클릭하면 해당 절 본문이, 숫자를 클릭하면 조회값 출처가 열린다.
4. 표시(확신 낮음, 판정 실패, 반품 사유 확인 필요, 근거 없음, 자체 대조 불일치 등)는 영역 맨 위에 모아 보여 준다.
5. 근거 데이터는 그룹 1~3이 이미 저장한 것을 읽기만 하고, 이 기능이 새로 계산하지 않는다.

**6. 출력(Output)**

- 화면 요소만. 저장·상태 변경 없음.

**7. 예외 처리(Exception)**

| 상황 | 시스템 대응 |
| --- | --- |
| 어떤 단계의 근거가 비어 있음(실패·미실행) | 그 줄에 "없음(사유)"를 표시하고 다른 줄은 정상 표시 |
| 절 본문 조회 실패 | 인용 문자열만 표시하고 "본문 열기 실패" |

**8. 완료 기준(Acceptance Criteria)**

- AC-024-1: Given 처리가 끝난 CSV1-000017, When 티켓 상세를 열면, Then 근거 영역에 긴급도 근거 문장, PR-02 판정 과정, RT-LV_BREAKER-DEFECT와 이관 조건, 필수정보 체크리스트(serial_no 막는 항목), SLA-DEFECT-PLATINUM-P1, TG-ACB-AS-2000 후보 절이 모두 보인다.
- AC-024-2: Given 초안에 "(DS-CONT-MC-32a §2.1)" 인용, When 클릭하면, Then 그 절 본문이 열린다.
- AC-024-3: Given 분류가 실패한 티켓, When 상세를 열면, Then 분류 줄에 "없음(분류 실패)"가 보이고 나머지 줄은 정상이다.

**9. 의존성 및 확인 사항**

- 선행: 그룹 1~3 전부, FR-030(화면 틀). 저장소의 근거 항목 구조는 기술 설계서.

---

### 이 그룹에서 새로 생긴 결정 필요 사항 (그룹 3)

| 번호 | 항목 | 결정 전 진행 방식 |
| --- | --- | --- |
| D14 | 정답지의 견적 단가·납기가 표 값과 다른 건이 많음(영어 견적 89건 중 54건 단가 상이, 견적·납기 271건 중 156건 납기 상이). 할인·납기 가산 규칙을 운영진에게 물을지, 정가·표준 납기만 안내할지 | 정가·표준 납기만 안내하고, 숫자 채점은 "표 값 일치"로만 한다 |

---

## 그룹 4. SLA와 상태 (FR-025, 026, 027, 028)

상태: 승인 (2026-10-10). 이 그룹은 문의가 지금 어느 단계에 있고(상태), 약속 시간을 얼마나 썼는지(SLA)를 계산한다. LLM은 쓰지 않는다. 새 결정 사항은 D19부터.

공통 원칙

- 복합 문의: D16의 진행 방식대로 상태와 SLA 시계는 FR-006이 나눈 **문의 단위**로 둔다. 단일 문의는 문의 1개짜리 티켓이므로 티켓 단위와 같다. 채점은 그룹 2와 같이 유형이 정답 category_code와 같은 문의만 정답 열과 비교한다.
- 시각은 모두 UTC로 저장한다. "지금"은 조회 시각이다. 정답지와 비교할 때만 "지금" = 스냅샷 2026-09-30 23:59 UTC로 고정한다.

데이터 사실 (tickets.csv 4,000건에서 확인)

- 상태(status) 6종: CLOSED 2,953 / RESOLVED 682 / IN_PROGRESS 241 / ESCALATED 71 / WAITING_CUSTOMER 34 / NEW 19. 상태 변경 이력은 데이터에 없다.
- 1차 응답 SLA 상태(sla_first_response_status)는 MET 3,531 / BREACHED 457 / ON_TRACK 12뿐이다. **1차 응답에는 AT_RISK가 없다.**
- 해결 SLA 상태(sla_resolution_status)는 MET 3,200 / BREACHED 417 / ON_TRACK 190 / N/A 159 / AT_RISK 34. 미해결 AT_RISK의 최소 비율은 목표의 75.3%, ON_TRACK의 최대는 73.8%로 75% 기준과 맞는다.
- 상태 판정식은 정답지와 4,000/4,000 맞는다: 1차 응답은 소요(first_response_hours) ≤ 목표면 MET, 해결은 경과(sla_elapsed_hours) ≤ 목표면 MET.
- 무응답 종료(final_action = CLOSED_NO_RESPONSE) 159건은 모두 추가정보 요청을 보냈고, **1차 응답 시각으로부터 정확히 168시간(7일) 뒤** 종료되었다(159/159). 해결 SLA 상태는 모두 N/A다. 스냅샷 때 WAITING_CUSTOMER인 34건은 1차 응답 뒤 최대 164.9시간이라 아직 7일이 안 됐다.

---

### FR-025. 상태 관리와 변경 이력

**1. 기능 설명**

- 문의의 상태를 정해진 전이 규칙대로만 바꾸고, 바뀔 때마다 이전 상태·새 상태·시각·바꾼 주체·이유를 이력으로 남긴다. 이 이력이 FR-026의 대기 시간 계산과 FR-023 진행 안내의 출발점이다.

**2. 우선순위**

- Must Have

**3. 수행 주체**

- 시스템(자동 전이), 상담원(승인·이관·종료 버튼)

**4. 입력(Input)**

- 전이를 일으키는 사건: 접수(FR-001), 상담원의 메시지 승인·발송(FR-031), 고객 회신 입력(FR-032), 이관 확정(FR-033, 확장), 종료 처리, 무응답 7일 경과.

**5. 처리(Process)**

1. 허용 전이표(아래)에 없는 전이는 거부한다.
2. 전이가 일어나면 이력 한 줄을 남긴다: 문의 순번, 이전 상태, 새 상태, 시각(UTC), 주체(시스템/상담원 ID), 사건 종류, 이유(선택).
3. WAITING_CUSTOMER로 들어간 시각과 나온 시각의 쌍을 "대기 구간"으로 저장한다. FR-026은 이 구간만 해결 시계에서 뺀다.
4. WAITING_CUSTOMER에서 정보 요청 발송 시각(데이터에서는 1차 응답 시각과 같음) 기준 168시간이 지나도록 고객 회신이 없으면 CLOSED로 바꾸고 final_action = CLOSED_NO_RESPONSE로 기록한다(데이터 사실 159/159, D22). 이 검사는 FR-027의 주기 점검과 함께 돈다.
5. 복합 문의는 문의마다 상태가 따로 있다. 티켓 목록에는 대표 상태를 보여 준다(제안, D16): 끝나지 않은 문의가 있으면 그중 가장 급한 문의(FR-027 기준)의 상태, 모두 끝났으면 RESOLVED(모두 CLOSED면 CLOSED).

허용 전이표

| 이전 → 새 상태 | 사건 | 주체 |
| --- | --- | --- |
| (없음) → NEW | 접수 | 시스템 |
| NEW → IN_PROGRESS | 처리 흐름 종료(FR-001 처리 4번) | 시스템 |
| NEW 또는 IN_PROGRESS → WAITING_CUSTOMER | 막는 정보에 대한 정보 요청(FR-015) 승인 발송 | 상담원 |
| WAITING_CUSTOMER → IN_PROGRESS | 고객 회신 입력(FR-032) | 상담원(시연용 대리 입력) |
| IN_PROGRESS → ESCALATED | 이관 확정(FR-033. 확장 기능 도입 전에는 발생하지 않음) | 상담원 |
| ESCALATED → IN_PROGRESS | 전문 부서 회신 수신(확장 FR-033 도입 전에는 발생하지 않음) | 상담원 |
| IN_PROGRESS 또는 ESCALATED → RESOLVED | 최종 답변(FINAL_REPLY) 승인 발송 | 상담원 |
| RESOLVED → CLOSED | 종료 처리 (D20) | 상담원 |
| WAITING_CUSTOMER → CLOSED | 무응답 168시간 경과 (final_action = CLOSED_NO_RESPONSE) | 시스템 |

**6. 출력(Output)**

- 문의의 현재 상태, 상태 변경 이력, 대기 구간 목록, 해결 시각(RESOLVED 또는 CLOSED로 바뀐 첫 시각).
- 사용자 표시: 티켓 상세 "이력" 탭에 시각순 상태 변경, 접수함에 대표 상태.

**7. 예외 처리(Exception)**

| 상황 | 시스템 대응 | 사용자에게 보이는 것 |
| --- | --- | --- |
| 허용되지 않은 전이 요청 | 거부, 실행 로그에 기록 | "현재 상태(○○)에서는 할 수 없는 작업" |
| 같은 문의에 동시 전이 두 건 | 먼저 저장된 것만 반영, 뒤 요청은 거부 | "다른 사용자가 먼저 변경함. 새로고침" |
| WAITING_CUSTOMER가 아닌데 고객 회신 입력 | 상태는 그대로, 회신은 메시지 이력에만 저장 | 회신이 이력에 보임 |
| 종료된(CLOSED) 문의에 고객 회신 | 상태 변경 없음, "종료 후 회신" 표시 | 상담원이 새 티켓으로 접수할지 판단 |

**8. 완료 기준(Acceptance Criteria)**

- AC-025-1: Given CSV1-000017을 접수, When 정보 요청(serial_no)을 승인 발송하면, Then 상태가 NEW → WAITING_CUSTOMER로 바뀌고 이력에 시각·상담원·사건 "정보 요청 발송"이 남는다.
- AC-025-2: Given WAITING_CUSTOMER인 문의, When 고객 회신을 입력하면, Then IN_PROGRESS로 바뀌고 대기 구간(들어간 시각, 나온 시각) 1개가 저장된다.
- AC-025-3: Given CSV1-000085(정보 요청 2025-10-09 18:55:19 발송, 회신 없음), When 시계를 2025-10-16 18:55:19로 돌리면, Then 시스템이 CLOSED로 바꾸고 final_action = CLOSED_NO_RESPONSE가 기록된다(정답지 resolved_at_utc와 같은 시각).
- AC-025-4: Given NEW 상태 문의, When RESOLVED로 바로 바꾸려 하면, Then 거부되고 상태는 NEW 그대로다.
- AC-025-5: Given test 597건의 처리 흐름을 시간순으로 재생, When 스냅샷 시점 상태를 보면, Then 정답 status와 일치율을 기록한다(참고 지표. 데이터에 상태 이력이 없어 재생 규칙이 정답과 같은지 확인할 수 없음).

**9. 의존성 및 확인 사항**

- 선행: FR-001. 후행: FR-023, FR-026, FR-027, FR-031~033.
- 결정 필요: D20(RESOLVED와 CLOSED의 차이), D22(무응답 종료 168시간 규칙의 출처).

---

### FR-026. SLA 경과·상태 계산

**1. 기능 설명**

- 두 시계로 경과 시간과 SLA 상태를 계산한다. 1차 응답 시계는 멈추지 않고, 해결 시계는 WAITING_CUSTOMER 구간 동안 멈춘다. 값은 저장하지 않고 조회할 때마다 상태 이력에서 다시 계산한다(FR-014 처리 4번).

**2. 우선순위**

- Must Have

**3. 수행 주체**

- 시스템(계산)

**4. 입력(Input)**

- received_at, 1차 응답 시각(D21의 메시지가 처음 발송된 시각), 해결 시각(FR-025), 대기 구간 목록(FR-025), sla_first_response_target_h, sla_resolution_target_h(FR-014), final_action, "지금".

**5. 처리(Process)**

1. 1차 응답 경과 = (1차 응답 시각, 없으면 지금) − received_at. 대기 구간을 빼지 않는다.
2. 1차 응답 상태: 1차 응답이 있으면 경과 ≤ 목표 → MET, 초과 → BREACHED. 없으면 지금까지 경과 > 목표 → BREACHED, 아니면 ON_TRACK. (정답지에 1차 응답 AT_RISK가 없으므로 상태값으로 쓰지 않는다. 75% 경고는 FR-027이 따로 단다.)
3. 해결 경과 = (해결 시각, 없으면 지금) − received_at − 대기 구간 합. 아직 대기 중이면 마지막 구간은 지금까지로 계산한다.
4. 해결 상태: final_action = CLOSED_NO_RESPONSE → N/A. 해결 시각이 있으면 경과 ≤ 목표 → MET, 초과 → BREACHED. 해결 시각이 없으면 경과 > 목표 → BREACHED, 목표의 75% 이상 → AT_RISK, 그 밖 → ON_TRACK.
5. 경과는 소수 첫째 자리 시간으로 보여 주되 계산은 초 단위로 한다. 남은 시간 = 목표 − 경과도 함께 낸다.
6. 우선순위 조정(FR-028)으로 목표가 바뀌면 경과는 그대로 두고 상태만 새 목표로 다시 판정한다.

**6. 출력(Output)**

- 문의별 1차 응답 경과·상태, 해결 경과·상태, 남은 시간, 대기 시간 합.
- 사용자 표시: 티켓 상세에 "1차 응답 1.3h / 1h BREACHED", "해결 8.7h / 24h MET (고객 대기 30.8h 제외)"처럼 두 시계를 나란히.

**7. 예외 처리(Exception)**

| 상황 | 시스템 대응 | 사용자에게 보이는 것 |
| --- | --- | --- |
| 목표가 비어 있음(FR-014 예외) | 계산하지 않음 | "SLA 미정" |
| 대기 구간의 나온 시각이 들어간 시각보다 빠름 | 그 구간을 0으로 계산, 실행 로그에 기록 | "대기 시간 기록 오류" 표시 |
| 경과가 음수 | 0으로 표시, 실행 로그에 기록 | "시간 기록 확인 필요" |

**8. 완료 기준(Acceptance Criteria)**

- AC-026-1: Given CSV1-000017(접수 2025-10-02 09:45:43, 1차 응답 1.34h, 대기 30.8h, 해결 2025-10-04 01:19:05, 목표 1h/24h), When 계산하면, Then 1차 응답 BREACHED, 해결 경과 약 8.76h(39.56 − 30.8. 정답지 8.7h, 오차 0.1h 이내), 해결 MET.
- AC-026-2: Given CSV1-003578(접수 2026-09-22 09:37:20, WAITING_CUSTOMER, 대기 100.9h), When 지금 = 스냅샷으로 계산하면, Then 해결 경과 105.5h(206.36 − 100.9), 목표 336h 대비 ON_TRACK, 1차 응답은 BREACHED(목표 72h).
- AC-026-3: Given CSV1-003401(IN_PROGRESS, 접수 2026-09-17 13:02:23, 대기 없음, 목표 360h), When 지금 = 스냅샷으로 계산하면, Then 경과 323.0h(89.7%) → AT_RISK.
- AC-026-4: Given CSV1-003950(NEW, 1차 응답 없음, 접수 2026-09-30 03:58:54, 1차 응답 목표 16h), When 지금 = 스냅샷으로 계산하면, Then 1차 응답 경과 20.0h → BREACHED.
- AC-026-5: Given CSV1-000085(CLOSED_NO_RESPONSE), When 계산하면, Then 해결 상태 N/A.
- AC-026-6: Given test 597건을 정답지의 시각·대기 시간으로 재생, When 채점하면, Then sla_first_response_status, sla_resolution_status 100% 일치, sla_elapsed_hours 오차 0.1h 이내(데이터 오류 행 제외, D19).

**9. 의존성 및 확인 사항**

- 선행: FR-014, FR-025. 후행: FR-027, FR-029(접수함 정렬), FR-030.
- 결정 필요: D19(데이터 오류 행), D21(1차 응답으로 치는 메시지).

---

### FR-027. SLA 위험 경고

**1. 기능 설명**

- 주기적으로 열린 문의의 SLA를 점검해, 해결 경과가 목표의 75% 이상이면 AT_RISK 경고를, 목표를 넘으면 BREACHED 경고를 단다. 1차 응답 시계도 같은 75% 기준으로 경고만 단다(상태값은 바꾸지 않음). 경고는 접수함과 티켓 상세에 보인다.

**2. 우선순위**

- Should Have (MVP 포함)

**3. 수행 주체**

- 시스템(주기 점검 작업)

**4. 입력(Input)**

- 끝나지 않은 문의(NEW, IN_PROGRESS, WAITING_CUSTOMER, ESCALATED) 전체의 FR-026 결과.

**5. 처리(Process)**

1. 정해진 주기(기술 설계서, 제안 5분)마다 끝나지 않은 문의의 FR-026을 다시 계산한다.
2. 해결 상태가 AT_RISK 또는 BREACHED로 처음 바뀐 문의에 경고 한 줄을 남긴다: 문의 순번, 경고 종류(RES_AT_RISK, RES_BREACHED), 발생 시각, 경과, 목표. 같은 종류의 경고는 문의당 한 번만 단다.
3. 1차 응답이 아직 없는 문의는 경과가 목표의 75% 이상이면 FR_AT_RISK, 목표를 넘으면 FR_BREACHED 경고를 단다.
4. WAITING_CUSTOMER 문의는 해결 시계가 멈춰 있으므로 해결 경고를 새로 달지 않는다. 같은 점검에서 무응답 168시간 종료(FR-025 처리 4번)를 함께 검사한다.
5. 접수함 정렬: 경고가 있는 문의를 위로, 그 안에서는 남은 시간이 적은 순.
6. 우선순위 조정으로 목표가 늘어 경고 조건이 풀리면 경고에 "해제" 시각을 기록한다.

**6. 출력(Output)**

- 경고 목록(문의 순번, 종류, 발생 시각, 해제 시각), 접수함 표시.
- 사용자 표시: 접수함 행에 경고 아이콘과 "남은 시간 36.2h", 티켓 상세에 경고 이력.

**7. 예외 처리(Exception)**

| 상황 | 시스템 대응 |
| --- | --- |
| 점검 작업이 한 주기를 건너뜀 | 다음 주기에 그동안의 변화를 한 번에 반영(경고 발생 시각은 실제 조건 충족 시각으로 계산) |
| SLA 미정 문의 | 점검 대상에서 제외, 접수함에 "SLA 미정" |
| 점검 중 오류 | 실행 로그에 기록, 다음 주기에 재시도 |

**8. 완료 기준(Acceptance Criteria)**

- AC-027-1: Given CSV1-003401(경과 323.0h / 목표 360h), When 스냅샷 시점에 점검하면, Then RES_AT_RISK 경고가 한 번 생기고 접수함 위쪽에 보인다.
- AC-027-2: Given 같은 문의, When 다음 주기에 다시 점검하면, Then 경고가 새로 생기지 않는다.
- AC-027-3: Given CSV1-003578(WAITING_CUSTOMER), When 점검하면, Then 해결 경고가 생기지 않는다.
- AC-027-4: Given 정답지 미해결 365건을 스냅샷 시점으로 점검, When 경고를 정답 sla_resolution_status와 비교하면, Then AT_RISK 34건과 BREACHED 141건이 모두 같은 종류의 경고를 받는다(재현율 100%).
- AC-027-5: Given CSV1-000031을 P4(목표 168h)로 처리 중 경과 130h(77%)라 RES_AT_RISK 경고가 있는 상태, When 상담원이 P3(목표 120h)로 올리면, Then 경과가 목표를 넘어 RES_BREACHED 경고가 새로 생긴다. (경과값은 예시)

**9. 의존성 및 확인 사항**

- 선행: FR-026. 후행: FR-029(접수함). FR-034(대시보드)는 이번 범위에서 제외.

---

### FR-028. 우선순위 조정과 SLA 재계산

**1. 기능 설명**

- 상담원이 규칙으로 정해진 우선순위를 바꿀 수 있다. 바꿀 때는 사유를 반드시 입력받고, SLA 목표를 새 우선순위로 다시 찾아 바꾼다(FR-014 처리 5번). 데이터의 조정 120건은 모두 SLA 목표가 조정된 우선순위 기준이다(120/120, 추적표 §6).

**2. 우선순위**

- Must Have

**3. 수행 주체**

- 상담원(조정), 시스템(재조회·재판정)

**4. 입력(Input)**

- 문의 순번, 새 우선순위(P1~P4), 사유(필수, 자유 글 + 사유 분류), 상담원 ID.

**5. 처리(Process)**

1. 새 우선순위가 지금과 같으면 거부한다. 사유가 비어 있으면 저장하지 않는다.
2. 규칙값(priority_rule_id의 결과)은 그대로 두고 "최종 우선순위"만 바꾼다. 조정 표시(priority_adjusted_by_agent = Y)를 켠다.
3. FR-014를 새 우선순위로 다시 돌려 목표 두 개와 sla_id를 바꾼다.
4. FR-026으로 상태를 다시 판정하고 FR-027 경고를 다시 점검한다. 경과 시간은 바꾸지 않는다.
5. 변경 이력 한 줄을 남긴다: 시각, 상담원, 이전·새 우선순위, 이전·새 sla_id와 목표, 사유.
6. 사유 분류의 값 목록은 데이터에 없다(조정 120건에 사유 기록 없음). MVP는 "고객 요청 / 영향 범위 재평가 / 기타" 세 값으로 시작한다(제안 사항).

**6. 출력(Output)**

- 최종 우선순위, 조정 표시, 새 SLA 목표, 다시 판정한 SLA 상태, 변경 이력.
- 사용자 표시: 티켓 상세 우선순위 옆 "P4 → P3 (상담원 조정, 사유: …)", SLA 목표 옆 "변경됨: 72/168h → 24/120h".

**7. 예외 처리(Exception)**

| 상황 | 시스템 대응 | 사용자에게 보이는 것 |
| --- | --- | --- |
| 사유 없음 | 저장 거부 | "조정 사유를 입력하세요" |
| 종료(RESOLVED, CLOSED) 문의 | 조정 거부 | "종료된 문의는 바꿀 수 없음" |
| 조정 뒤 즉시 BREACHED가 됨 | 그대로 반영하고 확인 창 표시 | "이 조정으로 SLA 위반 상태가 됩니다. 계속할까요?" |

**8. 완료 기준(Acceptance Criteria)**

- AC-028-1: Given CSV1-000031(MANUAL × STANDARD, 규칙 PR-07 → P4, 목표 72h/168h), When 상담원이 사유를 넣고 P3로 바꾸면, Then 목표가 24h/120h(SLA-MANUAL-STANDARD-P3)로 바뀌고, priority_rule_id는 PR-07 그대로이며, 변경 이력에 이전·새 값과 사유가 남는다.
- AC-028-2: Given 사유 칸이 빈 상태, When 저장하면, Then 거부되고 값이 바뀌지 않는다.
- AC-028-3: Given test 597건 중 priority_adjusted_by_agent = Y인 행, When 정답 priority로 조정을 재생해 채점하면, Then sla_first_response_target_h, sla_resolution_target_h 100% 일치.

**9. 의존성 및 확인 사항**

- 선행: FR-011, FR-014. 후행: FR-026, FR-027, FR-030(화면).

---

### 이 그룹에서 새로 생긴 결정 필요 사항 (그룹 4)

| 번호 | 항목 | 결정 전 진행 방식 |
| --- | --- | --- |
| D19 | 정답지의 시간 기록 이상 행. 기존에 알려진 고객 대기 시간 음수 3건(CSV1-003890, 003946, 003951)에 더해, NEW 상태인데 정보 요청 없이 고객 대기 시간이 있는 7건(CSV1-003612, 003913, 003950, 003967, 003984, 003995, 003999)이 있다. 이 중 6건은 해결 경과가 음수다. 7건 모두 해결 상태 값은 대기 시간을 빼지 않고 계산해도 정답과 같고 경과 숫자만 다르다. 운영진에게 함께 보고할지 | 10건을 경과 숫자 채점에서 제외 표시, 상태 값은 채점에 포함 |
| D20 | RESOLVED와 CLOSED의 차이. README에 정의가 없고, 해결 시각만으로는 구분 규칙이 보이지 않는다 | 최종 답변 발송 = RESOLVED, 상담원 "종료" 버튼 = CLOSED. SLA는 두 상태 모두 해결 시각 기준 |
| D21 | 1차 응답으로 치는 메시지의 종류. 무응답 종료 159건은 1차 응답 시각 = 정보 요청 시각이므로 정보 요청은 포함된다. 접수 확인 진행 안내(FR-023 ①)를 넣으면 1차 응답 SLA가 사실상 항상 MET이 된다 | 답변·정보 요청만 1차 응답으로 친다. 접수 확인 안내는 제외 |
| D22 | 무응답 168시간 자동 종료 규칙. 데이터에서 159/159로 확인했지만 README·정책 문서에 적힌 규칙은 아니다 | 데이터대로 168시간 자동 종료로 구현, 운영진 확인 대상에 추가 |

---

## 그룹 5. 상담원 화면 (FR-029, 030, 031, 032)

상태: 승인 (2026-10-10). 이 그룹은 1순위 사용자인 상담원이 쓰는 화면이다. 화면은 접수 시뮬레이터(FR-001·003), 접수함(FR-029), 티켓 상세(FR-030) 세 개이고, FR-031·032는 티켓 상세 안의 동작이다. 관리자 대시보드(FR-034)는 이번 범위에서 제외한다(D6). 새 결정 사항은 D23부터.

공통 원칙

- 화면은 보여 주고 입력받기만 한다. 판단(분류, 규칙, 초안)은 그룹 1~4의 기능이 하고, 화면은 그 결과와 근거(FR-024)를 그대로 보여 준다.
- 복합 문의(FR-006)는 티켓 안에 문의가 여러 개다. 접수함은 티켓 한 줄에 대표값(D16: 가장 급한 문의 기준)을, 티켓 상세는 문의마다 구역을 나누어 보여 준다.
- 사용자 식별: 로그인·권한 기능은 기능 목록(STEP 2)에 없다. MVP는 화면 상단에서 상담원 이름과 부서(departments.csv 13개)를 고르는 방식으로 대신한다(제안, D23).

데이터 사실 (tickets.csv 4,000건)

- 담당 부서(assigned_dept)는 11개가 쓰였다: TS_AUTO 669, TS_LV 628, SCM 526, WARRANTY_DESK 474, GCS_L1 400, TS_ENERGY 362, CERT 350, SALES_OPS 300, TS_MV 112, TS_TRF 100, FIELD_SVC 79. RND_FW, QA_CLAIM은 1차 담당으로는 없고 이관 부서(escalated_to)로만 나온다.
- 스냅샷 시점 미해결 365건의 부서별 수: TS_LV 67, WARRANTY_DESK 60, SCM 54, TS_AUTO 52, GCS_L1 36, TS_ENERGY 27, CERT 27, SALES_OPS 21, TS_MV 10, FIELD_SVC 6, TS_TRF 5. 상태×SLA는 IN_PROGRESS 241(BREACHED 113, ON_TRACK 98, AT_RISK 30), ESCALATED 71, WAITING_CUSTOMER 34(모두 ON_TRACK), NEW 19.
- 정보 요청 문안(info_request_message)은 고객 언어이고 빠진 항목 이름을 나열하는 짧은 글이다. 예: CSV1-000017 "We need some additional details before we can help: Serial number (nameplate). Thank you."

---

### FR-029. 접수함

**1. 기능 설명**

- 상담원이 자기 부서의 티켓을 목록으로 본다. 한 줄에 우선순위, 상태, SLA 남은 시간, 경고, 정보 요청 필요 여부를 보여 주고 정렬·필터한다. 접수함은 상담원의 진입점이며, 클릭하면 티켓 상세(FR-030)로 간다.

**2. 우선순위**

- Must Have

**3. 수행 주체**

- 상담원(조회), 시스템(목록 제공)

**4. 입력(Input)**

- 선택한 부서(공통 원칙), 필터 값, 정렬 기준, 검색어(ticket_id 또는 고객사 이름).

**5. 처리(Process)**

1. 기본 범위는 선택한 부서가 담당(assigned_dept)인 티켓 중 끝나지 않은 것(NEW, IN_PROGRESS, WAITING_CUSTOMER, ESCALATED). "종료 포함" 스위치로 RESOLVED·CLOSED도 본다.
2. 열(순서대로): ticket_id, 접수 시각, 채널(channel), 고객사(company_masked)·등급(customer_tier), 제품(product_code), 문의 유형(category_code, 복합이면 "FW_UPDATE;MANUAL"처럼 그대로), 우선순위(최종값, 조정이면 표시), 상태, 해결 SLA 남은 시간(FR-026), 경고(FR-027), 정보 요청 필요(FR-013), 미발송 초안 있음(FR-031).
3. 기본 정렬은 FR-027 처리 5번과 같다: 경고 있는 티켓 위, 그 안에서 남은 시간 오름차순. 열 머리글 클릭으로 바꿀 수 있다.
4. 필터: 상태 / 우선순위 / 경고 종류 / 정보 요청 필요 / 미발송 초안 있음 / 복합 문의 / 채널. 여러 개를 함께 건다.
5. 복합 문의 한 줄의 대표값: 우선순위는 문의 중 가장 급한 것, 상태·남은 시간·경고는 그 문의의 값. 유형 칸에 문의 수를 함께 표시("2건").
6. 목록은 접속 시와 새로고침 때 다시 읽는다. 자동 갱신 주기는 FR-027의 점검 주기와 같게 둔다(기술 설계서).
7. 한 페이지 50건(제안), 페이지 넘김.

**6. 출력(Output)**

- 티켓 목록(위 열), 건수 요약(전체 / 경고 / 정보 요청 필요 / 미발송 초안).
- 사용자 표시: 상태 배지(ON_TRACK 초록, AT_RISK 노랑, BREACHED 빨강, WAITING_CUSTOMER 회색, N/A 없음), 남은 시간은 "36.2h", 넘었으면 "−12.5h".

**7. 예외 처리(Exception)**

| 상황 | 시스템 대응 | 사용자에게 보이는 것 |
| --- | --- | --- |
| 부서를 고르지 않음 | 목록을 비움 | "부서를 선택하세요" |
| 해당 부서 티켓 없음 | 빈 목록 | "처리할 티켓이 없습니다" |
| SLA 미정 티켓(FR-014 예외) | 남은 시간 칸 비움, 정렬은 맨 아래 | "SLA 미정" |
| 목록 읽기 실패 | 이전 목록 유지, 오류 표시 | "목록을 불러오지 못함. 새로고침" |

**8. 완료 기준(Acceptance Criteria)**

- AC-029-1: Given 정답지 미해결 365건을 적재하고 지금 = 스냅샷, When 부서 TS_LV를 고르면, Then 67건이 보이고 맨 위 티켓은 경고가 있으며 남은 시간이 가장 적은 것이다.
- AC-029-2: Given 같은 상태, When 필터 "정보 요청 필요"를 켜면, Then missing_blocking_info가 비어 있지 않은 티켓만 남는다.
- AC-029-3: Given CSV1-000008을 접수해 복합 문의가 된 상태, When 접수함을 보면, Then 유형 칸에 "FW_UPDATE;MANUAL (2건)"이 보이고 한 줄만 있다.
- AC-029-4: Given 접수함의 한 줄, When 클릭하면, Then 그 티켓의 상세 화면(FR-030)이 열린다.
- AC-029-5: Given 종료 포함 스위치가 꺼진 상태, When 목록을 보면, Then RESOLVED·CLOSED 티켓이 없다.

**9. 의존성 및 확인 사항**

- 선행: FR-010(고객·제품 이름), FR-013, FR-026, FR-027. 후행: FR-030.
- 기술 설계서로 넘길 것: 목록 API, 자동 갱신 방식, 페이지 크기.

---

### FR-030. 티켓 상세

**1. 기능 설명**

- 한 티켓의 모든 것을 한 화면에서 본다: 고객이 보낸 것, 시스템이 판단한 것과 근거, 보낼 글(초안), 메시지 이력, 상태·SLA. 시연의 중심 화면이며 FR-031(승인·발송), FR-032(고객 회신 입력), FR-028(우선순위 조정)의 버튼이 여기에 있다.

**2. 우선순위**

- Must Have

**3. 수행 주체**

- 상담원(조회·조작), 시스템(표시)

**4. 입력(Input)**

- ticket_id. 화면이 읽는 데이터: 티켓, 문의별 결과(그룹 1~4), 근거(FR-024), 메시지 이력(FR-035), 상태 이력(FR-025), 실행 로그 요약(FR-036).

**5. 처리(Process)**
화면을 세 칸과 아래 띠로 나눈다.

1. 왼쪽 "고객이 보낸 것": 원문(inquiry_body)과 제목, 채널, 고객 언어(language)·본문 언어(body_language), 고객사·등급, 제품. 원문에서 FR-008이 뽑은 값(제품 코드, 제조번호, 에러 코드, 펌웨어 버전 등)을 강조한다. 전화 건은 "영어 메모, 답장은 {language}" 안내를 붙인다(FR-004).
2. 가운데 "시스템이 판단한 것": 문의마다 한 구역. 구역 안에 유형·긴급도·우선순위(규칙값과 최종값)·담당 부서·SLA 목표와 두 시계(FR-026)·필수 항목 체크리스트(FR-013: 제공 ✓ / 빠짐 / 막는 항목 강조)를 두고, 각 값 옆의 "왜?"를 누르면 FR-024의 근거(적용 규칙 행, 근거 문장, 인용 절, 조회값)가 열린다. 우선순위 옆에 [조정] 버튼(FR-028). 복합 문의면 구역 머리에 "문의 1/2: FW_UPDATE"와 그 문의의 근거 문장을 보여 준다.
3. 오른쪽 "보낼 것": 미발송 초안을 종류별 탭으로 둔다: 정보 요청(FR-015), 답변(FR-021, 복합이면 FR-022의 합친 답변), 진행 안내(FR-023). 각 탭에 편집기, 인용 목록, 자체 대조 결과(어긋난 자리 강조), [승인·발송] 버튼(FR-031). 초안이 없는 종류는 그 이유("막는 정보 요청 중", "근거 없음 — 상담원 작성 필요")를 보여 주고, 빈 편집기에서 직접 쓸 수 있다.
4. 아래 띠 "이력": 메시지 이력(FR-035)과 상태 변경(FR-025)·경고(FR-027)·우선순위 조정(FR-028)을 시각순 한 줄로 합쳐 보여 준다. 메시지는 보낸 쪽·종류·언어·본문. [고객 회신 입력] 버튼(FR-032)은 이 띠에 둔다.
5. "다시 처리" 버튼: 처리 흐름이 실패했거나(FR-001 예외) 상담원이 분류를 직접 고친 뒤에 그 문의의 흐름을 다시 돌린다. 이미 발송한 메시지는 지우지 않는다.
6. 상담원이 유형·긴급도·제공 항목을 직접 고칠 수 있다(FR-005 예외의 드롭다운, FR-013 AC-013-3). 고친 값은 "상담원 수정"으로 표시하고 규칙 단계(그룹 2)를 다시 돌린다.

**6. 출력(Output)**

- 화면 표시만. 저장은 각 버튼의 기능(FR-028, 031, 032)이 한다.

**7. 예외 처리(Exception)**

| 상황 | 시스템 대응 | 사용자에게 보이는 것 |
| --- | --- | --- |
| ticket_id 없음 | 접수함으로 되돌림 | "티켓을 찾을 수 없음" |
| 처리 흐름이 아직 도는 중 | 왼쪽은 보이고 가운데·오른쪽은 "처리 중" | 진행 표시, 끝나면 자동 갱신 |
| 처리 흐름 실패(FR-001 예외) | 실패한 단계와 사유를 가운데 칸에 표시 | "자동 처리 실패: {단계}. 다시 처리" 버튼 |
| 다른 상담원이 같은 티켓을 바꿈 | 저장 때 충돌 감지(FR-025 예외) | "다른 사용자가 변경함. 새로고침" |
| 본문이 긴 경우 | 접어서 보여 주고 펼침 | 펼치기 |

**8. 완료 기준(Acceptance Criteria)**

- AC-030-1: Given CSV1-000017을 접수한 뒤, When 상세를 열면, Then 왼쪽에 원문과 강조된 error_code, 가운데에 DEFECT·SITE_DOWN·P1(PR-02)·TS_LV·SLA 1h/24h·막는 항목 serial_no 강조, 오른쪽 정보 요청 탭에 영어 초안이 보인다.
- AC-030-2: Given 가운데 칸의 우선순위 "P1" 옆 "왜?", When 누르면, Then "PR-02: urgency=SITE_DOWN 이고 Category ∈ {DEFECT, INSTALL, FW_UPDATE} → P1" 규칙 행(priority_rules.csv)과 긴급도 SITE_DOWN의 근거 문장이 보인다.
- AC-030-3: Given CSV1-000008(복합 문의), When 상세를 열면, Then 가운데 칸에 문의 1(FW_UPDATE)과 문의 2(MANUAL) 구역이 따로 있고 각 구역에 자기 근거 문장이 있으며, 오른쪽 답변 탭에는 합친 답변 하나가 있다.
- AC-030-4: Given CSV1-000004(QUOTE, 막는 항목 없음), When 상세를 열면, Then 정보 요청 탭은 "막는 항목 없음"이고 답변 탭에 프랑스어 초안과 인용·조회값(520 USD, 4주)이 보인다.
- AC-030-5: Given 상담원이 유형을 직접 바꾼 경우, When 저장하면, Then "상담원 수정" 표시가 붙고 우선순위·부서·필수 항목·SLA 목표가 새 유형으로 다시 계산되어 보인다.

**9. 의존성 및 확인 사항**

- 선행: 그룹 1~4 전부, FR-024, FR-035, FR-036. 후행: FR-028, 031, 032.
- 기술 설계서로 넘길 것: 상세 API 묶음, 번역 토글(원문의 한국어 번역 표시) 포함 여부는 기능 목록에 없으므로 여유 시 항목.

---

### FR-031. 초안 수정·승인·발송

**1. 기능 설명**

- 상담원이 정보 요청·답변·진행 안내 초안을 고쳐 승인하면 "발송됨"으로 기록되고 상태가 바뀐다. 실제 메일·채팅 발송은 하지 않고 기록만 한다(외부 연계 FR-037은 범위 밖). 시스템이 만든 글이 고객에게 가려면 반드시 이 단계를 거친다(운영 원칙 7).

**2. 우선순위**

- Must Have

**3. 수행 주체**

- 상담원(수정·승인), 시스템(기록·상태 전이)

**4. 입력(Input)**

- 메시지 종류(INFO_REQUEST, FINAL_REPLY, PROGRESS_NOTICE), 문의 순번(복합 문의의 정보 요청·진행 안내는 문의별, 답변은 합친 것 하나), 편집기의 최종 본문, 상담원 ID.

**5. 처리(Process)**

1. 본문이 비어 있으면 거부한다. 고객 언어(language)와 본문 언어가 다르면 경고만 띄우고 계속할 수 있다(전화 건처럼 영어로 보낼 수도 있으므로).
2. 승인 전 검사(FR-021 5번과 같은 자체 대조)를 최종 본문에 다시 한다: 인용이 근거 후보 밖이거나 숫자가 조회값 밖이면 "확인 필요" 창을 띄운다. 상담원이 "그래도 발송"을 누르면 진행하고 그 사실을 기록한다.
3. 메시지 이력(FR-035)에 발송 행을 새로 쓴다: 종류, 문의 순번, 보낸 쪽 = 상담원, 발송 시각(UTC, 지금), 언어, 최종 본문, 원본 초안 ID, 수정 여부(초안과 글자가 다르면 Y). 초안 행은 "승인됨"으로 바꾸고 지우지 않는다.
4. 상태 전이(FR-025 허용 전이표): INFO_REQUEST → 그 문의를 WAITING_CUSTOMER로. FINAL_REPLY → 모든 문의를 RESOLVED로(답변이 하나이므로; 문의별로 따로 보내는 경우는 D15). PROGRESS_NOTICE → 상태 변경 없음.
5. 1차 응답 시각: 이 티켓에서 INFO_REQUEST 또는 FINAL_REPLY가 처음 발송된 시각을 1차 응답 시각으로 기록한다(D21). PROGRESS_NOTICE는 포함하지 않는다.
6. 발송 뒤 FR-026을 다시 계산하고(1차 응답 상태 확정), FR-023이 다음 안내 초안을 만들 수 있게 전이 사건을 넘긴다.
7. 승인 없이 저장만 하는 [임시 저장]도 둔다. 임시 저장은 초안 행의 본문만 바꾸고 상태는 "초안" 그대로다.

**6. 출력(Output)**

- 메시지 이력의 발송 행 1건, 상태 이력(전이가 있을 때), 1차 응답 시각(처음일 때).
- 사용자 표시: 오른쪽 칸의 탭이 "발송됨 {시각}"으로 바뀌고 아래 띠에 메시지가 추가된다. 정보 요청이면 상태 배지가 WAITING_CUSTOMER로 바뀐다.

**7. 예외 처리(Exception)**

| 상황 | 시스템 대응 | 사용자에게 보이는 것 |
| --- | --- | --- |
| 본문 비어 있음 | 거부 | "내용을 입력하세요" |
| 자체 대조 어긋남 | 확인 창, 선택하면 진행 | "근거 밖 인용/숫자 n곳. 그래도 발송?" |
| 허용되지 않은 전이(예: CLOSED 문의에 답변 발송) | 발송 기록은 남기되 상태는 바꾸지 않음, 실행 로그 기록 | "종료된 문의입니다. 메시지만 기록됨" |
| 같은 초안을 두 번 승인 | 두 번째는 거부 | "이미 발송된 초안" |
| 막는 항목이 남아 있는데 FINAL_REPLY 발송 | 확인 창 | "막는 정보(serial_no)가 아직 없습니다. 그래도 발송?" |

**8. 완료 기준(Acceptance Criteria)**

- AC-031-1: Given CSV1-000017의 정보 요청 초안, When 승인·발송하면, Then INFO_REQUEST 발송 행이 생기고 상태가 WAITING_CUSTOMER가 되며 1차 응답 시각이 발송 시각으로 기록된다.
- AC-031-2: Given CSV1-000004의 답변 초안에서 상담원이 한 문장을 고친 뒤, When 승인·발송하면, Then 발송 행의 수정 여부가 Y이고 원본 초안 행은 글자가 바뀌지 않은 채 "승인됨"으로 남으며 상태가 RESOLVED가 된다.
- AC-031-3: Given 답변 초안에 조회값에 없는 숫자를 상담원이 써 넣은 경우, When 승인을 누르면, Then "근거 밖 숫자" 확인 창이 뜨고, "그래도 발송"을 누르면 발송되며 그 선택이 기록된다.
- AC-031-4: Given 진행 안내 초안, When 승인·발송하면, Then PROGRESS_NOTICE 발송 행이 생기고 상태와 1차 응답 시각은 바뀌지 않는다.
- AC-031-5: Given 같은 초안을 두 번 승인, When 두 번째 요청이 오면, Then 거부되고 발송 행은 1건이다.

**9. 의존성 및 확인 사항**

- 선행: FR-015, 021, 022, 023(초안), FR-025, FR-035. 후행: FR-026, FR-023(다음 안내).
- 결정 필요: D15(답변을 문의별로 따로 보내는 경우의 전이), D21(1차 응답 메시지 종류).

---

### FR-032. 고객 회신 입력

**1. 기능 설명**

- 시연과 테스트를 위해 상담원이 고객 회신을 대신 입력한다. 입력하면 WAITING_CUSTOMER가 끝나고(FR-025), 회신 본문에서 제공 항목을 다시 뽑아(FR-008) 필수 항목을 다시 대조하고(FR-013), 막는 항목이 없어지면 근거·초안 단계(FR-016~022)가 돈다. 시나리오 ⓑ(필수정보 누락→요청→대기→회신→해결)의 가운데 단계다.

**2. 우선순위**

- Should Have (MVP 포함)

**3. 수행 주체**

- 상담원(입력), 시스템(저장·재처리)

**4. 입력(Input)**

- 회신 본문(필수, 2,000자 이하(제안 상한)), 회신 언어(기본값 = 고객 언어, 바꿀 수 있음), 회신 시각(기본값 = 지금, 재현용으로 과거 시각 허용, 미래 거부), 어느 문의에 대한 회신인지(복합 문의에서 대기 중인 문의가 둘 이상일 때만 선택, 기본값 = 대기 중인 모든 문의).

**5. 처리(Process)**

1. 메시지 이력에 종류 CUSTOMER_REPLY, 보낸 쪽 = 고객, 시각, 언어, 본문으로 저장한다(FR-035).
2. 대상 문의가 WAITING_CUSTOMER면 IN_PROGRESS로 바꾸고 대기 구간을 닫는다(FR-025). 아니면 상태는 그대로 두고 저장만 한다(FR-025 예외).
3. 대상 문의마다 FR-008을 원문 + 모든 고객 회신 본문으로 다시 돌린다. 제공 항목은 늘어나기만 하고 줄지 않는다(이전에 제공된 값은 유지).
4. FR-013을 다시 돌린다. 막는 항목이 남아 있으면 FR-015가 새 정보 요청 초안을 만든다(이전 요청과 같은 항목이면 "재요청" 표시). 비어 있으면 FR-016~022가 돌아 답변 초안을 만든다.
5. FR-023이 "회신 수신 확인" 안내 초안을 만든다(전이 ③).
6. 재문의 횟수(customer_followups에 해당)는 회신이 정보 요청에 대한 답이 아닐 때만 1 올린다: 대상 문의가 WAITING_CUSTOMER가 아니었거나, 회신에서 새 제공 항목이 하나도 안 나왔을 때(제안 규칙. 정답지의 customer_followups 산정 기준은 README에 없음).

**6. 출력(Output)**

- CUSTOMER_REPLY 메시지 1건, 상태 이력(전이가 있을 때), 갱신된 제공·빠진·막는 항목, 새 초안(정보 요청 또는 답변), 회신 수신 확인 안내 초안.
- 사용자 표시: 아래 띠에 고객 회신, 가운데 칸 체크리스트가 갱신, 오른쪽 칸에 새 초안 탭.

**7. 예외 처리(Exception)**

| 상황 | 시스템 대응 | 사용자에게 보이는 것 |
| --- | --- | --- |
| 본문 비어 있음 | 거부 | "회신 내용을 입력하세요" |
| 회신 시각이 정보 요청 발송 시각보다 빠름 | 거부 | "회신 시각은 요청 발송 이후여야 합니다" |
| 종료(CLOSED)된 문의 | 메시지만 저장, 재처리 없음 | "종료 후 회신으로 기록됨" |
| 재처리 중 LLM 실패 | 회신과 상태 전이는 유지, 재처리만 실패 표시 | "자동 처리 실패. 다시 처리" |
| 회신에서 값을 못 찾음 | 체크리스트 그대로, 재요청 초안 생성 | "제공 항목 변화 없음" 표시 |

**8. 완료 기준(Acceptance Criteria)**

- AC-032-1: Given CSV1-000017이 serial_no 정보 요청 뒤 WAITING_CUSTOMER인 상태, When "Serial number is LVB-2024-00117."(예시)를 회신으로 입력하면, Then 상태가 IN_PROGRESS가 되고 대기 구간이 닫히며 제공 항목에 serial_no가 추가되어 막는 항목이 비고 답변 초안(TG-ACB-AS-2000 인용)이 생긴다.
- AC-032-2: Given 같은 티켓, When 회신에 제조번호가 없는 글("We will check and let you know.")을 입력하면, Then 상태는 IN_PROGRESS가 되지만 막는 항목 serial_no가 남아 "재요청" 표시가 붙은 정보 요청 초안이 생긴다.
- AC-032-3: Given CSV1-003578(product_model 요청 뒤 WAITING_CUSTOMER, 대기 100.9h), When 회신을 입력하면, Then 해결 시계의 대기 구간이 닫히고 FR-026의 대기 시간 합이 회신 시각까지로 확정된다.
- AC-032-4: Given 회신 입력 뒤, When 아래 띠를 보면, Then 고객 회신 메시지와 "회신 수신 확인" 진행 안내 초안이 시각순으로 보인다.
- AC-032-5: Given 회신 시각을 정보 요청 발송보다 앞선 시각으로 입력, When 저장하면, Then 거부된다.

**9. 의존성 및 확인 사항**

- 선행: FR-008, 013, 015, 025, 031, 035. 후행: FR-016~023, FR-026.
- 제안 사항: 재문의 횟수 산정 규칙(처리 6번)은 정답지와 맞는지 확인할 수 없으므로 참고 지표로만 쓴다.

---

### 이 그룹에서 새로 생긴 결정 필요 사항 (그룹 5)

| 번호 | 항목 | 결정 전 진행 방식 |
| --- | --- | --- |
| D23 | 로그인·권한을 범위에 넣을지. 기능 목록(STEP 2)에 없고 제약 조건에도 없다. 시연은 한 화면에서 상담원·부서를 바꿔 가며 보여 주면 된다 | 로그인 없이 화면 상단에서 상담원 이름·부서를 고른다. 선택값은 메시지·이력의 "주체"로 기록 |

### 검토 중 발견한 불일치 (STEP 7에서 함께 정리) (그룹 5)

- FR-001 처리 4번은 "처리 흐름이 끝나면 상태를 IN_PROGRESS로 바꾼다"(시스템)이고, FR-023 ①도 그 전이에서 접수 확인 안내를 만든다. 그런데 FR-025 허용 전이표의 NEW → IN_PROGRESS 행은 주체를 "상담원"으로 적었다. 이 그룹은 FR-001 쪽(처리 흐름 종료 시 시스템이 IN_PROGRESS로)을 따랐다. FR-025 표의 그 행을 "처리 흐름 종료 / 시스템"으로 고쳤다(2026-10-10 승인).

---

## 그룹 6. 기록 (FR-035, 036, 038)

상태: 승인 (2026-10-10). 이 그룹은 눈에 보이는 기능이 아니라 다른 모든 기능이 기대는 기록이다. 메시지 이력(FR-035)은 3순위 문제(진행 상황을 몰라 재문의)의 기록이고, 실행 로그(FR-036)는 "왜 이 결과인가"(FR-024)와 시연·채점의 증거이며, 마스킹(FR-038)은 제약 조건이다. 외부 연계 창구 FR-037은 이번 범위에서 제외한다(STEP 3). 이 그룹에서 새로 생긴 결정 사항은 없다.

공통 원칙

- 기록은 지우지 않는다. 고치는 대신 새 줄을 쓴다(FR-031 처리 3번과 같은 방식).
- 시각은 UTC, 주체는 상담원 이름·부서(D23) 또는 "시스템".
- 복합 문의(FR-006)는 기록마다 문의 순번(seq)을 붙인다. 티켓 전체에 대한 기록(접수 문의, 합친 답변)은 순번을 비운다.

데이터 사실 (tickets.csv 4,000건)

- 정답지에는 과정이 없다: 1차 응답은 시각(first_response_at_utc)만 있고 본문이 없으며, 고객 재문의는 횟수(customer_followups)만 있고, 정보 요청 문안(info_request_message, 887건)과 최종 답변(final_reply, 3,635건)만 본문이 있다. 그래서 메시지 이력의 정답은 없고, 적재할 수 있는 메시지는 티켓당 최대 3줄(접수 문의, 정보 요청, 최종 답변)이다.
- 마스킹 상태: 회사명은 "COMPANY_2464_0436" 꼴(company_masked), 이메일은 "user57705@***.masked" 꼴(contact_email_masked, 4,000건 모두 같은 꼴), 담당자는 "TS_TRF_AGENT_09" 꼴(assignee_masked). 문의 본문(inquiry_body)과 최종 답변에는 이메일 주소("@")와 전화번호 꼴의 숫자가 없다. 본문의 긴 숫자열은 모두 날짜(2025-11-16 같은 꼴, 1,352곳)다. 즉 데이터는 이미 마스킹되어 있고, 우리 시스템이 새로 받는 입력(시뮬레이터, 고객 회신)에서만 마스킹이 새로 필요하다.

---

### FR-035. 메시지 이력 저장

**1. 기능 설명**

- 티켓 안에서 오간 글을 한 줄씩 저장한다: 접수 문의, 시스템이 만든 초안, 상담원이 발송한 정보 요청·답변·진행 안내, 고객 회신. 티켓 상세의 아래 띠(FR-030 처리 4번)와 1차 응답 시각(FR-031 처리 5번), 무응답 종료(FR-025 처리 4번)가 이 표를 읽는다.

**2. 우선순위**

- Must Have

**3. 수행 주체**

- 시스템(저장). 쓰는 기능: FR-001(접수 문의), FR-015·021·022·023(초안), FR-031(발송), FR-032(고객 회신).

**4. 입력(Input)**

- 메시지 한 줄의 값: ticket_id, 문의 순번(seq, 티켓 전체면 비움), 보낸 쪽(sender: CUSTOMER / SYSTEM / AGENT / DEPT), 종류(message_type: INQUIRY / INFO_REQUEST / FINAL_REPLY / PROGRESS_NOTICE / CUSTOMER_REPLY / ESCALATION_NOTE), 상태(message_status: DRAFT / APPROVED / SENT / RECEIVED), 시각(sent_at_utc), 언어(language), 본문(body), 원본 초안 ID(발송 행일 때), 수정 여부, 보낸 주체 이름.

**5. 처리(Process)**

1. 저장 규칙: 한 줄은 한 번 쓰고 바꾸지 않는다. 예외는 상태 칸 하나(DRAFT → APPROVED, FR-031 처리 3번)와 임시 저장(FR-031 처리 7번, DRAFT 행의 본문만).
2. 종류와 상태의 조합은 다음만 허용한다: INQUIRY는 RECEIVED(고객, FR-001). INFO_REQUEST·FINAL_REPLY·PROGRESS_NOTICE는 DRAFT(시스템) → APPROVED(초안 행) + SENT(새 행, 상담원). CUSTOMER_REPLY는 RECEIVED(고객, FR-032). ESCALATION_NOTE는 확장 기능 FR-033이 쓰며 MVP에서는 생기지 않는다.
3. 이름 맞추기: 그룹 3이 쓴 "FINAL_REPLY_DRAFT"는 종류 FINAL_REPLY + 상태 DRAFT, "PROGRESS_NOTICE 초안"은 PROGRESS_NOTICE + DRAFT다. 1차 응답(FIRST_RESPONSE)은 종류가 아니라 "INFO_REQUEST 또는 FINAL_REPLY의 첫 SENT 행"으로 구한다(D21). 고객 재문의(FOLLOWUP)는 CUSTOMER_REPLY 중 FR-032 처리 6번의 조건에 맞는 행이다.
4. 티켓 안 순번(message_no)은 저장 순서대로 1부터 붙인다. 시각이 과거로 입력된 재현용 메시지(FR-001·032의 과거 시각)도 순번은 저장 순서, 표시는 시각순이다.
5. 본문은 FR-038의 마스킹 검사를 거친 뒤에만 저장한다.
6. 정답지 적재(train 행, FR-003·시연 데이터): 티켓당 INQUIRY(inquiry_body, received_at_utc), INFO_REQUEST SENT(info_request_message, 시각 = first_response_at_utc, info_request_sent = Y일 때), FINAL_REPLY SENT(final_reply, 시각 = resolved_at_utc, 값이 있을 때)를 만든다. 본문이 없는 1차 응답은 만들지 않는다.
7. 조회: 티켓의 메시지를 시각순으로 돌려준다. 문의 순번 필터를 받는다.

**6. 출력(Output)**

- 메시지 행(위 입력 항목 + message_no). 티켓 상세 아래 띠의 재료.
- 사용자 표시: FR-030 처리 4번. DRAFT 행은 오른쪽 칸(초안 탭)에, SENT·RECEIVED 행은 아래 띠에.

**7. 예외 처리(Exception)**

| 상황 | 시스템 대응 | 사용자에게 보이는 것 |
| --- | --- | --- |
| 허용되지 않은 종류·상태 조합 | 저장 거부, 실행 로그에 기록 | 해당 기능의 오류 표시("저장 실패") |
| 본문 비어 있음 | 저장 거부 | "내용을 입력하세요"(FR-031·032) |
| 본문 길이 초과(제안 상한 5,000자. 데이터 최대: 본문 756자, 최종 답변 302자, 정보 요청 200자) | 저장 거부 | "길이 초과" |
| 마스킹 검사 실패(FR-038) | 마스킹한 본문으로 저장하고 표시 | "개인정보 마스킹됨 n곳" |
| 같은 초안 ID로 SENT 행 두 번 | 두 번째 거부(FR-031 예외) | "이미 발송된 초안" |

**8. 완료 기준(Acceptance Criteria)**

- AC-035-1: Given CSV1-000004를 train 정답지에서 적재, When 메시지를 조회하면, Then INQUIRY(2025-10-01 08:29:24, fr)와 FINAL_REPLY SENT(2025-10-12 05:29:38, fr, "520.00 USD" 포함) 2줄이고 INFO_REQUEST는 없다(info_request_sent = N).
- AC-035-2: Given CSV1-000017을 적재, When 조회하면, Then INQUIRY, INFO_REQUEST SENT(2025-10-02 11:06:12, "Serial number (nameplate)" 포함), FINAL_REPLY SENT(2025-10-04 01:19:05) 3줄이다. (정보 요청 시각 = first_response_at_utc)
- AC-035-3: Given 접수 → 정보 요청 발송 → 고객 회신 → 답변 발송까지 돌린 새 티켓, When 조회하면, Then INQUIRY RECEIVED, INFO_REQUEST DRAFT→APPROVED, INFO_REQUEST SENT, CUSTOMER_REPLY RECEIVED, FINAL_REPLY DRAFT→APPROVED, FINAL_REPLY SENT 순으로 있고, 1차 응답 시각은 INFO_REQUEST SENT 행의 시각이다.
- AC-035-4: Given 발송된 SENT 행, When 본문 수정을 시도하면, Then 거부된다.
- AC-035-5: Given 복합 문의 CSV1-000008을 처리, When 조회하면, Then 문의 1·2의 INFO_REQUEST·PROGRESS_NOTICE 행에는 순번이 있고 INQUIRY와 FINAL_REPLY 행에는 순번이 비어 있다.

**9. 의존성 및 확인 사항**

- 선행: 없음(기반 표). 후행: FR-001, 015, 021~023, 025, 030, 031, 032.
- 기술 설계서로 넘길 것: 표 이름·컬럼(시스템_요구사항_풀이 v2 R11의 ticket_message 정의를 이 명세의 종류·상태로 맞춤), 길이 상한.

---

### FR-036. 처리 실행 로그

**1. 기능 설명**

- 문의 한 건의 처리 흐름(실행, run)과 그 안의 단계(step)마다 입력·출력·소요 시간·오류·LLM 사용량을 기록한다. 티켓 상세의 "왜?"(FR-024)가 단계 기록으로 이어지고, 시연 기준(STEP1 5-2)과 완료 기준의 "실행 로그로 확인"(AC-001-3, AC-005-2, AC-006-3)이 이 기록을 본다.

**2. 우선순위**

- Should Have (MVP 포함)

**3. 수행 주체**

- 시스템(워크플로 엔진이 자동 기록)

**4. 입력(Input)**

- 실행 시작·종료 사건과 단계마다의 입력·출력. 단계 목록(제안): 언어 식별(FR-004) → 분류·분리(FR-005·006) → 긴급도(FR-007) → 추출(FR-008) → 고객·제품 조회(FR-010) → 우선순위(FR-011) → 부서(FR-012) → 필수정보(FR-013) → SLA 목표(FR-014) → 정보 요청 문안(FR-015) 또는 근거 검색(FR-016) → 숫자 조회(FR-017) → 초안(FR-021) → 병합(FR-022, 복합일 때) → 진행 안내(FR-023).

**5. 처리(Process)**

1. 실행(run) 한 줄: run_id, ticket_id, 문의 순번(FR-006 이후 문의별 실행이면), 시작·종료 시각, 소요(ms), 결과(SUCCESS / FAILED / PARTIAL), 시작 사유(접수 / 다시 처리 / 고객 회신 / 상담원 수정), 마지막으로 끝난 단계 이름.
2. 단계(step) 한 줄: step_id, run_id, 단계 이름, 순서, 시작·종료 시각, 소요(ms), 결과, 입력 요약, 출력 요약, 오류 종류(LLM_TIMEOUT / LLM_INVALID_OUTPUT / RULE_NOT_FOUND / DB / VALIDATION / UNKNOWN)와 오류 문장, LLM 사용량(모델 이름, 입력·출력 토큰, 호출 수), 검색 단계는 찾은 doc_id·절 목록.
3. 입력·출력 요약에는 분류 결과·규칙 ID·빠진 항목·인용 목록처럼 FR-024가 보여 주는 값을 그대로 넣는다. 긴 본문(원문, 초안)은 메시지 이력 ID로 가리키고 로그에는 다시 넣지 않는다.
4. 프롬프트 전문과 LLM 응답 전문은 기본으로 저장하지 않고, 설정으로 켤 수 있게 한다(기술 설계서). 켜면 FR-038 마스킹을 거친다.
5. 재시도(FR-001 예외, FR-030 다시 처리)는 새 run으로 기록하고 이전 run은 남긴다. 같은 ticket_id·순번의 run이 여러 개면 가장 최근 것이 현재 결과다.
6. 분류·분리 단계의 입력 기록에는 분류에 넣은 항목 이름 목록을 남겨 제목(inquiry_subject)이 들어가지 않았음을 확인할 수 있게 한다(AC-001-3).
7. 조회: 티켓(또는 문의)의 run 목록과 run의 step 목록. 티켓 상세 "왜?"에서 해당 단계로 바로 간다.

**6. 출력(Output)**

- run 행, step 행. 티켓 상세의 "처리 기록" 탭(실행 목록 → 단계 목록 → 단계의 입력·출력·오류).
- 사용자 표시: 단계 이름, 결과, 소요, 오류 종류를 한 줄로. 입력·출력 요약은 펼침.

**7. 예외 처리(Exception)**

| 상황 | 시스템 대응 |
| --- | --- |
| 로그 저장 실패 | 처리 흐름은 멈추지 않고 계속, 실패를 앱 로그(파일)에 남김 |
| 단계가 시작만 되고 끝나지 않음(프로세스 중단) | 다음 실행 시작 때 결과 FAILED, 오류 UNKNOWN으로 닫음 |
| 로그가 너무 커짐 | 보존 기간(기술 설계서, 제안 90일) 지난 run을 지움. 메시지 이력은 지우지 않음 |

**8. 완료 기준(Acceptance Criteria)**

- AC-036-1: Given CSV1-000004를 접수, When 실행 로그를 보면, Then run 1개에 언어 식별부터 초안까지의 step이 순서대로 있고 모두 SUCCESS이며, 숫자 조회 단계의 출력에 list_price 520, std_lead 4주가 있다.
- AC-036-2: Given 분류 단계의 입력 기록, When 항목 이름 목록을 보면, Then inquiry_subject가 없다(AC-001-3의 확인 방법).
- AC-036-3: Given LLM 호출이 시간 초과되는 상태, When 접수하면, Then run 결과 FAILED, 마지막 단계 = 분류·분리, 그 step의 오류 종류 = LLM_TIMEOUT이고, 다시 처리하면 새 run이 생기고 이전 run은 남아 있다.
- AC-036-4: Given CSV1-000008(복합), When 로그를 보면, Then 문의 1·2의 run이 따로 있고 병합 단계는 티켓 run(순번 없음)에 있다.
- AC-036-5: Given 티켓 상세의 우선순위 "왜?", When 누르면, Then 우선순위 단계의 출력(priority_rule_id, 적용 조건)이 열린다.

**9. 의존성 및 확인 사항**

- 선행: 없음(기반 표). 후행: FR-024, FR-030, 모든 "실행 로그로 확인" AC.
- 기술 설계서로 넘길 것: 표 설계(code/agent_runs_steps_인사이트.md의 run/step 모양을 참고), 보존 기간, 전문 저장 설정, LLM 사용량 집계 방법.

---

### FR-038. 개인정보 마스킹 유지

**1. 기능 설명**

- 데이터가 이미 마스킹된 값(회사명, 이메일, 담당자)을 그대로 유지하고 절대 풀지 않는다. 우리 시스템이 새로 받는 글(시뮬레이터 입력, 고객 회신, 상담원이 고친 초안)에 이메일·전화번호가 있으면 저장 전에 가린다. LLM에 보내는 입력과 실행 로그에도 가린 값만 들어간다.

**2. 우선순위**

- Must Have

**3. 수행 주체**

- 시스템(저장 전 검사)

**4. 입력(Input)**

- 저장되려는 모든 글: 메시지 본문(FR-035), 실행 로그의 입력·출력(FR-036), 티켓 항목(FR-001), 상담원이 고친 초안(FR-031).

**5. 처리(Process)**

1. 기준 데이터의 마스킹 값은 그대로 쓴다: company_masked, contact_email_masked("user57705@***.masked"), assignee_masked. 화면·초안·로그 어디서도 다른 값으로 바꾸거나 복원하려 하지 않는다. 답변 초안에 고객사 이름이 필요하면 company_masked 값을 그대로 쓴다.
2. 새 글은 저장 직전에 규칙으로 검사한다(LLM 아님): 이메일 주소 꼴(@ 앞뒤 문자열) → "user***@***.masked", 전화번호 꼴(국가 번호 + 또는 숫자 8자리 이상이 구분 기호로 이어진 것) → "*******". 날짜(2025-10-28 꼴), 제조번호, 주문 번호, 에러 코드, 수량·금액은 가리지 않는다.
3. 가린 곳의 수를 그 글과 함께 기록한다("마스킹 n곳"). 원문은 어디에도 저장하지 않는다.
4. LLM 호출 직전에 같은 검사를 한 번 더 한다(입력에 가려지지 않은 값이 남지 않도록).
5. 사람 이름은 데이터에 없고(본문 4,000건에서 호칭+이름 꼴 0건) 규칙으로 가리기 어려우므로 범위에서 뺀다(제안. 필요하면 확장).
6. 정답지 적재(FR-003·035)도 같은 검사를 거친다. 데이터에는 가릴 것이 없으므로 결과는 0곳이어야 한다.

**6. 출력(Output)**

- 가려진 본문, 가린 곳의 수.
- 사용자 표시: 메시지·로그 옆 "개인정보 마스킹됨 n곳".

**7. 예외 처리(Exception)**

| 상황 | 시스템 대응 | 사용자에게 보이는 것 |
| --- | --- | --- |
| 검사 규칙이 제조번호·주문 번호를 잘못 가림 | 제외 목록(숫자-문자 혼합, 날짜 꼴)을 먼저 적용. 그래도 가려지면 상담원이 체크리스트(FR-013)에서 값을 직접 입력 | "마스킹됨" 표시로 알 수 있음 |
| 검사 실패(규칙 오류) | 저장을 막고 실행 로그 기록 | "저장 실패: 마스킹 검사" |
| 마스킹 값을 복원하려는 요청 | 그런 기능을 두지 않음 | — |

**8. 완료 기준(Acceptance Criteria)**

- AC-038-1: Given 시뮬레이터 본문에 "contact me at [kim@example.com](mailto:kim@example.com) or +82-10-1234-5678", When 접수하면, Then 저장된 INQUIRY 본문과 실행 로그에 "[kim@example.com](mailto:kim@example.com)"과 "1234-5678"이 없고 "마스킹 2곳"이 표시된다.
- AC-038-2: Given 본문에 "delivery by 2025-10-28, PO 4500123456, S/N LVB-2024-00117", When 접수하면, Then 세 값이 그대로 저장된다(마스킹 0곳).
- AC-038-3: Given train 정답지 2,800건 적재, When 마스킹 검사 결과를 집계하면, Then 가린 곳이 0이다.
- AC-038-4: Given 답변 초안에 고객사 이름이 들어가는 경우, When 초안을 보면, Then "COMPANY_4975_0183" 같은 마스킹 값 그대로이고 복원된 이름이 없다.
- AC-038-5: Given LLM 호출 입력 기록(FR-036), When 전체를 검색하면, Then "@" 뒤에 "***.masked"가 아닌 도메인이 없다.

**9. 의존성 및 확인 사항**

- 선행: 없음. 후행: FR-001, 031, 032, 035, 036(모든 저장 경로).
- 기술 설계서로 넘길 것: 이메일·전화 검사식, 제외 목록, 검사 위치(저장 계층 한 곳에 두어 모든 경로가 거치게).

---

### 검토 중 발견한 이름 불일치 (STEP 7에서 함께 정리) (그룹 6)

- 시스템_요구사항_풀이_및_추가_설명_v2.md R11의 ticket_message 종류(FIRST_RESPONSE_DRAFT, FIRST_RESPONSE, FOLLOWUP 등)와 이 명세의 종류·상태 구분이 다르다. 이 명세(종류 6개 + 상태 4개)가 FR-031·032의 동작과 맞으므로 이쪽을 기준으로 제안한다. v2 문서는 참고용이므로 고치지 않는다.
