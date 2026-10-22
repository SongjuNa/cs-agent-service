# Spec Delta: rule-engine

## Purpose

규칙표(ref 스키마)만 읽어 문의의 고객·제품 값, 우선순위, 담당 부서, 빠진 필수정보, SLA 목표를 정한다. 언어 모델을 부르지 않고, 결과마다 어느 규칙 행을 썼는지 함께 돌려준다(기술 명세서 v1.4 §5).

## ADDED Requirements

### Requirement: 고객과 제품 값을 기준정보에서 읽는다 (FR-010)
규칙 엔진은 customer_id로 ref.customer의 tier, segment, country와 대표 연락처 3열을 읽어야 한다(MUST). product_code가 있으면 제품 값 묶음(제품명, family, family_name, tech_support_dept, has_firmware, 최신 펌웨어, std_lead_time_weeks, list_price_usd, moq, warranty_months, 문서 목록, lifecycle_status)을 읽어야 한다(MUST). product_code가 비어 있으면 제품 값을 비우고 "제품 미확정"을 표시해야 한다(MUST). customer_id가 없으면 서버 로그에 남기고 오류로 멈춰야 한다(MUST).

#### Scenario: AC-010-1 고객·제품 값이 붙는다
- **GIVEN** CSV1-000017의 customer_id CUST-0350, product_code ACB-AS-2000
- **WHEN** 고객·제품을 조회한다
- **THEN** customer_tier = PLATINUM, country = TH, product_family = LV_BREAKER, tech_support_dept = TS_LV다

#### Scenario: AC-010-2 제품이 비면 부서·필수정보가 "제품 확인 필요"로 멈춘다
- **GIVEN** CSV1-000017에서 product_code를 비운 입력
- **WHEN** 고객·제품을 조회하고 부서 배정과 필수정보 확인을 한다
- **THEN** 제품 값이 비어 있고 "제품 미확정"이 표시되며, 부서 배정과 필수정보 확인은 "제품 확인 필요" 상태로 결과 없이 끝난다

### Requirement: 우선순위를 규칙표의 첫 일치로 정한다 (FR-011)
규칙 엔진은 ref.priority_rule을 rule_order 오름차순으로 보고, 조건 표(priority_rule_urgency, priority_rule_category)에 행이 없으면 "모두 맞음"으로 보아 처음 맞는 규칙의 priority와 rule_id를 돌려줘야 한다(MUST). 본 규칙마다 맞음/안 맞음을 판정 과정으로 돌려주고, 화면 표시용으로 그 규칙의 condition 원문을 함께 돌려줘야 한다(MUST). category_code나 urgency_flag가 비면 계산하지 않고 "분류 뒤 계산됨"을, 맞는 규칙이 없으면 "우선순위 미정"을 표시해야 한다(MUST).

#### Scenario: AC-011-1 설비 정지 고장은 P1, PR-02
- **GIVEN** CSV1-000017 (DEFECT, SITE_DOWN)
- **WHEN** 우선순위를 계산한다
- **THEN** P1, PR-02이고 판정 과정에 PR-01 안 맞음, PR-02 맞음이 남는다

#### Scenario: AC-011-2 마감 있는 견적은 P3, PR-06
- **GIVEN** CSV1-000004 (QUOTE, DEADLINE)
- **WHEN** 우선순위를 계산한다
- **THEN** P3, PR-06이다

#### Scenario: AC-011-3 급하지 않은 매뉴얼 문의는 P4, PR-07
- **GIVEN** CSV1-000031 (MANUAL, NONE)
- **WHEN** 우선순위를 계산한다
- **THEN** P4, PR-07이다 (정답지의 P3는 상담원 조정값이다)

### Requirement: 담당 부서와 이관 조건을 정한다 (FR-012)
규칙 엔진은 rule_id = "RT-{family}-{category}" 행(rule_source가 CATEGORY_DEFAULT 또는 FAMILY_OVERRIDE)의 primary_dept를 assigned_dept로, 비어 있으면 product_family.tech_support_dept를 써야 한다(MUST). escalation_dept, escalation_condition과 부서 이름(한/영)을 함께 돌려줘야 한다(MUST). ESCALATION 행은 쓰지 않아야 한다(MUST). 행이 없으면 부서를 비우고 "배정 규칙 없음 — 분류 재검토"를, product_family가 없으면 "제품 확인 뒤 배정됨"을 표시해야 한다(MUST).

#### Scenario: AC-012-1 저압 차단기 고장은 TS_LV
- **GIVEN** CSV1-000017 (LV_BREAKER, DEFECT)
- **WHEN** 부서를 배정한다
- **THEN** assigned_dept = TS_LV, routing_rule_id = RT-LV_BREAKER-DEFECT이고, 이관 조건으로 routing_rules.csv 그 행의 escalation_dept = QA_CLAIM과 escalation_condition이 붙는다 (명세서 AC-012-1은 FIELD_SVC라고 적어 데이터와 다르다. 조장 확인 필요)

#### Scenario: AC-012-2 반품은 사유에 따라 부서가 갈린다
- **GIVEN** CSV1-000097 (HMI, RETURN, 본문 사유 "The units have a recurring quality problem")와 CSV1-000039 (MV_EQUIP, RETURN, 본문 사유는 프랑스어 "Nous avons reçu un modèle différent de celui commandé"(오배송)). CSV1-000039의 사유는 L2가 영어로 바꿨다고 가정해 같은 뜻의 영어 문장 "We received a different model from what we ordered"(반품_사유_단어목록_v1 2장)를 넣는다
- **WHEN** 부서를 배정한다
- **THEN** CSV1-000097은 WARRANTY_DESK, RT-HMI-RETURN이고 CSV1-000039는 SCM, RT-ALL-RETURN-NON_DEFECT다

#### Scenario: AC-012-3 반품 사유가 없으면 기본 행과 확인 필요 표시
- **GIVEN** CSV1-000039 (MV_EQUIP, RETURN)에서 반품 사유가 비어 있는 입력
- **WHEN** 부서를 배정한다
- **THEN** return_kind = UNKNOWN, 기본 행 RT-MV_EQUIP-RETURN으로 배정되고 "반품 사유 확인 필요"가 켜진다. 같은 입력에 반품 구분 NON_DEFECT를 주어 다시 배정하면 SCM, RT-ALL-RETURN-NON_DEFECT가 된다

#### Scenario: AC-012-4 펌웨어 없는 제품군의 펌웨어 문의는 규칙 없음
- **GIVEN** product_family = CONTROL, category_code = FW_UPDATE
- **WHEN** 부서를 배정한다
- **THEN** assigned_dept가 비고 "배정 규칙 없음 — 분류 재검토"가 표시된다

### Requirement: 반품 사유를 단어 목록으로 가른다 (W10)
규칙 엔진은 반품 사유(영어)를 소문자로 바꿔 `config/return_reason_words.yaml`의 단어가 들어 있는지 찾아야 한다(MUST). 비불량 단어만 있으면 NON_DEFECT, 불량 단어만 있으면 DEFECT, 둘 다 없거나 둘 다 있으면 UNKNOWN이어야 한다(MUST). 단어 목록은 코드에 적지 않아야 한다(MUST).

#### Scenario: W10-1 영어 반품 211건이 모두 맞는다
- **GIVEN** tickets.csv에서 category_code = RETURN이고 body_language = en인 211건과, 각 본문에 든 반품 사유 문장(반품_사유_단어목록_v1 2장의 여섯 문장 중 하나)
- **WHEN** 그 문장으로 반품 구분을 정한다
- **THEN** routing_rule_id가 RT-ALL-RETURN-NON_DEFECT인 행은 NON_DEFECT, 나머지는 DEFECT로 211건 모두 맞는다

### Requirement: 빠진 필수정보와 막는 항목을 정한다 (FR-013)
규칙 엔진은 ref.required_info_field의 (family, category) 행을 field_order 순으로 읽어 missing_info = 필수 − 제공, missing_blocking_info = 막는 항목(is_blocking) − 제공을 순서대로 돌려줘야 한다(MUST). 항목마다 info_field.label을 붙이고, missing_blocking_info가 있으면 "정보 요청 필요"를 켜야 한다(MUST). family나 category가 없으면 계산하지 않고 "제품·유형 확인 뒤 계산됨"을 표시해야 한다(MUST). 제공 항목이 비어 있으면 모든 필수 항목을 빠짐으로 계산해야 한다(MUST).

#### Scenario: AC-013-1 고장 문의에서 빠진 항목
- **GIVEN** CSV1-000017 (LV_BREAKER, DEFECT, 제공: product_model, error_code, load_profile)
- **WHEN** 필수정보를 대조한다
- **THEN** missing_info = serial_no, operating_condition, photos이고 missing_blocking_info = serial_no다

#### Scenario: AC-013-2 다 갖춘 견적 문의
- **GIVEN** CSV1-000004 (제공 항목이 필수 4항목과 같음)
- **WHEN** 필수정보를 대조한다
- **THEN** missing_info와 missing_blocking_info가 비어 있고 "정보 요청 필요"가 꺼져 있다

#### Scenario: AC-013-3 상담원이 "제공됨"으로 바꾸면 다시 계산한다
- **GIVEN** CSV1-000017의 제공 항목에 serial_no를 더한 입력
- **WHEN** 필수정보를 다시 대조한다
- **THEN** missing_blocking_info에서 serial_no가 빠지고 "정보 요청 필요"가 꺼진다

### Requirement: SLA 목표 시간을 정한다 (FR-014)
규칙 엔진은 ref.sla_policy에서 (category, customer_tier, priority) 1행을 찾아 sla_id, first_response_hours, resolution_hours를 돌려줘야 한다(MUST). inquiry_category.resolution_definition과 sla_setting 3행(clock, at_risk_threshold, pause_rule)을 표시용으로 함께 돌려줘야 한다(MUST). priority가 없으면 목표를 비우고 "SLA 미정"을, 행이 없으면 목표를 비우고 서버 로그에 남기며 "SLA 정책 없음 — 데이터 확인"을 표시해야 한다(MUST).

#### Scenario: AC-014-1 플래티넘 P1 고장은 1시간/24시간
- **GIVEN** CSV1-000017 (DEFECT, PLATINUM, P1)
- **WHEN** SLA 목표를 찾는다
- **THEN** 1차 응답 1시간, 해결 24시간, sla_id = SLA-DEFECT-PLATINUM-P1이다

#### Scenario: AC-014-2 규칙값 P4 매뉴얼 문의는 72시간/168시간
- **GIVEN** CSV1-000031 (MANUAL, STANDARD, 규칙값 P4)
- **WHEN** SLA 목표를 찾는다
- **THEN** 1차 응답 72시간, 해결 168시간이다 (P3 조정은 FR-028, 2순위)

### Requirement: 4,000건에서 규칙 결과를 100% 재현한다 (W1)
규칙 엔진은 tickets.csv 4,000건의 입력 값(category_code, urgency_flag, customer_id, product_code, provided_info)으로 정답과 같은 우선순위 규칙, SLA 목표, 필수정보를 내야 한다(MUST). 정답 열(gold.ticket_gold)은 정답과 비교하는 시험 코드만 읽는다(CLAUDE.md 규칙 6).

#### Scenario: W1-5 우선순위 규칙 100%
- **GIVEN** gold.ticket_gold 4,000건
- **WHEN** 우선순위를 계산한다
- **THEN** priority_rule_id가 4,000건 모두 같고, priority_adjusted_by_agent = N인 행은 priority도 모두 같다

#### Scenario: W1-6 SLA 목표 100%
- **GIVEN** gold.ticket_gold 4,000건과 각 행의 최종 priority
- **WHEN** SLA 목표를 찾는다
- **THEN** sla_first_response_target_h와 sla_resolution_target_h가 4,000건 모두 같다

#### Scenario: W1-7 필수정보 100%
- **GIVEN** gold.ticket_gold 4,000건과 각 행의 provided_info
- **WHEN** 필수정보를 대조한다
- **THEN** required_info, missing_info, missing_blocking_info가 순서까지 4,000건 모두 같다
