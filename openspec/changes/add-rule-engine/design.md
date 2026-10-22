# Design: 규칙 엔진

## Context

동기는 proposal.md의 Why를 본다. 따를 기준은 다음과 같다.

- 명세서 v1.5 FR-010~014(처리, 예외 처리, 완료 기준).
- 기술 명세서 v1.4 §2-2(노드 Q2~Q6의 입력·출력·실패 시), §2-3(상태 객체 필드 이름), §5-2~5-4.
- 테이블 정의서 v1.3 / `docs/database/schema.sql`의 ref 표와 svc.sub_ticket 열 이름.
- 반품_사유_단어목록_v1_20261022.md(단어 목록과 211건 확인 방법).

## Goals / Non-Goals

**Goals**
- 규칙 4가지(우선순위, 부서, 필수정보, SLA 목표)와 고객·제품 조회를 규칙표만 읽는 함수로 만든다(근거: 기술 명세서 §5 첫 문단).
- 결과마다 쓴 규칙 행과 판정 과정을 함께 돌려준다. 근거 표시(FR-024)의 재료다(근거: 기술 명세서 §5 첫 문단).

**Non-Goals**
- DB에 결과 쓰기, 처리 흐름(그래프) 만들기, 화면(proposal "범위 밖").

## Decisions

### 1. 위치와 언어 모델 분리

- 코드는 `backend/app/rules/`에 둔다(근거: 프로젝트 구조 1순위 판 2장 "rules/ 우선순위·부서·필수정보·SLA 목표 (규칙표만, LLM 없음)").
- 고객·제품 조회(FR-010)도 rules/에 둔다(근거: 같은 판 3장 표, Q2 고객·제품 조회 = rules/).
- rules/는 `app.llm`을 import하지 않는다(근거: CLAUDE.md 규칙 1, config.yaml 설계 원칙 2). 시험 하나가 rules/ 파일들에 `app.llm` import가 없는지 확인한다.

### 2. 모듈과 함수

모든 함수는 DB 연결(psycopg `Connection`)을 첫 인자로 받아 ref 표만 읽는다(구현 선택). 돌려주는 값의 이름은 svc.sub_ticket 열 이름을 따르고, 열이 없는 값은 상태 객체(기술 명세서 §2-3) 이름을 따른다. 둘 다 없는 이름은 아래 표에 "구현 선택"으로 적는다.

| 모듈 | 함수 | 입력 | 출력 | 근거 |
|---|---|---|---|---|
| `lookup.py` | `lookup_customer`, `lookup_product` | customer_id / product_code | 고객: tier, segment, country, primary_contact_name·email·phone. 제품: product_name, family, family_name, tech_support_dept, has_firmware, fw_latest, std_lead_time_weeks, list_price_usd, moq, warranty_months, doc_ids, lifecycle_status | FR-010 처리 1·2(목록), FR-010 출력(제품명), FR-010 예외(lifecycle_status, 단종 판단용), 기술 명세서 §2-2 Q2 |
| `priority.py` | `decide_priority` | category_code, urgency_flag | priority, priority_rule_id, condition 원문, priority_trace[(rule_id, matched)] | FR-011 처리 3·출력, §5-2 의사코드와 "원문 condition은 화면 표시용" |
| `routing.py` | `decide_return_kind`, `assign_dept` | return_reason / family, category_code, return_kind | return_kind와 걸린 단어 / assigned_dept, routing_rule_id, escalation_dept, escalation_condition, 부서 이름(한/영), 표시 | FR-012, §5-3, 화면 정의서 v2 C-04("반품 구분과 걸린 단어") |
| `required_info.py` | `check_required_info` | family, category_code, provided_info | required_info, missing_info, missing_blocking_info(field_order 순), 항목 라벨, info_request_needed | FR-013, §5-4. info_request_needed는 FR-013 출력 "정보 요청 필요 여부"에 붙인 이름(구현 선택) |
| `sla.py` | `find_sla_target` | category_code, customer_tier, priority | sla_id, sla_first_response_target_h, sla_resolution_target_h, resolution_definition, sla_setting 3값 | FR-014, §5-4 |

- 결과는 파이썬 dataclass로 돌려준다(구현 선택). 표시 문구는 `flags` 목록에 담는다(근거: 상태 객체 `flags`, 기술 명세서 §2-3). 문구와 출처는 아래 결정 3 표에 적는다.
- 제품 값은 돌려주기만 하고 저장하지 않는다(근거: FR-010 처리 2 "티켓에는 저장하지 않는다").
- fw_latest는 firmware_release의 is_latest = true 행, doc_ids는 document.product_code가 같은 행이다(근거: FR-010 처리 2 괄호).

### 3. 실패할 때

기술 명세서 §2-2 "실패 시" 열과 명세서 예외 처리 표를 따른다.

| 상황 | 동작 | 근거 |
|---|---|---|
| 고객 없음 | 서버 로그 + `CustomerNotFound` 오류(오류 이름은 구현 선택) | FR-010 예외 "흐름 중단, 실행 로그에 기록"(실행 로그 FR-036은 2순위라 서버 로그), §2-2 Q2 |
| product_code 없음 | 제품 값 None + "제품 미확정" | FR-010 처리 3 |
| family 없음 (부서) | 결과 없음 + "제품 확인 뒤 배정됨" | FR-012 예외 |
| family 또는 category 없음 (필수정보) | 결과 없음 + "제품·유형 확인 뒤 계산됨" | FR-013 예외 |
| 제공 항목이 비어 있음 | 필수 항목을 모두 빠짐으로 계산. "추출 실패" 표시는 추출(FR-008, 5번 변경)이 켠다 | FR-013 예외 |
| category_code 또는 urgency_flag 없음 | 우선순위 계산 안 함 + "분류 뒤 계산됨" | FR-011 예외 |
| 맞는 우선순위 규칙 없음 | None + "우선순위 미정" | FR-011 예외, §5-2 |
| 부서 규칙 행 없음 | assigned_dept None + "배정 규칙 없음 — 분류 재검토" | FR-012 예외, AC-012-4 |
| RETURN이고 사유 없음·미확인 | 기본 행 + "반품 사유 확인 필요" | FR-012 처리 2, 예외 |
| priority 없음 | 목표 None + "SLA 미정" | FR-014 예외, §2-2 Q6 |
| SLA 행 없음 | 목표 None + 서버 로그 + "SLA 정책 없음 — 데이터 확인" | FR-014 예외 |
| 단종 제품 | 만들지 않음. lifecycle_status 값(ACTIVE, MATURE)에 단종에 해당하는 값이 없다 | FR-010 예외. 조장 확인 필요 |

### 4. 반품 구분

- 단어 목록은 `config/return_reason_words.yaml`(저장소 루트)에 `non_defect`, `defect` 두 목록으로 둔다. 내용과 모양은 반품_사유_단어목록_v1 4장 그대로다(근거: 기술 명세서 §5-3 4번, §9 W10).
- 판정: 사유를 소문자로 바꾸고 단어가 들어 있는지(부분 문자열) 본다. 비불량만 → NON_DEFECT, 불량만 → DEFECT, 그 밖 → UNKNOWN. 사유가 비면 UNKNOWN(근거: §5-3 2번, FR-012 예외 "추출되지 않음 → 미확인").
- `assign_dept`는 category = RETURN이고 return_kind = NON_DEFECT일 때만 RT-ALL-RETURN-NON_DEFECT를 쓴다. UNKNOWN이면 기본 행 + "반품 사유 확인 필요"(근거: FR-012 처리 2, §2-5 분기②).
- 상담원이 고른 구분은 같은 함수에 return_kind를 직접 넘겨 다시 배정한다(근거: §5-3 3번 "고르면 Q4부터 다시 돈다". 화면은 범위 밖).

### 5. 시험

- AC 시험은 `backend/tests/acceptance/test_rule_engine.py`, 4,000건 재현은 `backend/tests/rules/test_reproduce_gold.py`에 둔다(근거: 프로젝트 구조 1순위 판 2장).
- 시험은 입력과 정답을 모두 gold.ticket_gold에서 읽는다. category_code, urgency_flag, provided_info는 원래 언어 모델(5번 변경)이 만드는 값이라 gold.v_inputs에 없기 때문이다. 정답과 비교하는 시험 코드이므로 정답 열을 읽어도 된다(근거: CLAUDE.md 규칙 6, schema.sql gold.v_inputs 열). rules/ 코드는 gold를 읽지 않는다.
- W10-1의 반품 사유 문장은 반품_사유_단어목록_v1 2장의 여섯 문장이다. 본문에 든 문장을 찾아 넣는다(근거: 같은 문서 2장 "확인 방법").
- 시험 전에 ref·gold가 적재되어 있어야 한다. 2번 변경의 적재 작업을 시험 준비 단계에서 실행한다(근거: 2번 변경 `test_data_load.py`와 같은 방식).

## Risks / Trade-offs

- 반품 단어 판정은 영어 211건으로만 확인한다. 다른 언어는 5번 변경 뒤 시험한다(근거: 반품_사유_단어목록_v1 3장).
- 단어를 부분 문자열로 찾으므로 "doa"처럼 짧은 단어가 다른 낱말 안에서 잡힐 수 있다. 기술 명세서 §5-3이 정한 방식이므로 그대로 두고, 여러 언어 시험에서 확인한다.
