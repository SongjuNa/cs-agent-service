# Spec Delta: reference-data

## Purpose

운영진이 준 기준정보·규칙표 CSV를 ref 스키마에 채운다. 규칙 엔진과 문서 근거가 이 표를 읽는다(기술 명세서 v1.4 §5-1, W1).

## ADDED Requirements

### Requirement: 기준정보 표의 행 수는 테이블 정의서와 같다 (W1)
기준정보 적재 작업은 ref/ CSV 12개와 docs/doc_index.csv를 읽어 ref 스키마 표 24개(doc_chunk 제외)를 채워야 한다(MUST). 원본에서 바꾸는 방법은 테이블 정의서 v1.3 §2-0을 따라야 하며(MUST), 외래 키를 어기는 행이 있으면 적재 전체가 실패해야 한다(MUST).

#### Scenario: W1-1 적재 뒤 표마다 행 수가 정의서와 같다
- **GIVEN** 빈 ref 스키마
- **WHEN** 기준정보 적재 작업을 실행한다
- **THEN** 행 수가 테이블 정의서 v1.3 §2와 같다: department 13, product_family 11, inquiry_category 10, priority_level 4, customer_tier 3, urgency 6, info_field 32, customer 600, product 23, product_standard 39, product_certification 61, product_spec 169, firmware_release 39, fault 97, fault_product 156, priority_rule 7, priority_rule_urgency 6, priority_rule_category 20, routing_rule 111, required_info_rule 110, required_info_field 437, sla_policy 120, sla_setting 3, document 107

### Requirement: 다시 실행해도 같은 결과가 나온다 (W1)
기준정보 적재 작업은 표를 비우고 다시 넣어야 하며(MUST), 두 번 실행해도 행 수와 값이 같아야 한다(SHALL). 서비스 표(svc)가 기준정보를 가리키고 있어 비울 수 없으면 아무것도 바꾸지 않고 멈춰야 한다(MUST).

#### Scenario: W1-2 두 번 실행해도 행 수가 같다
- **GIVEN** 기준정보 적재를 한 번 마친 DB
- **WHEN** 기준정보 적재 작업을 한 번 더 실행한다
- **THEN** 24개 표의 행 수가 W1-1과 같다

### Requirement: 번호 모양의 값은 문자열 그대로 보존한다 (W1)
펌웨어 버전(fw_version)과 절 번호(section)는 문자열로 저장해야 하며(MUST), 원본 CSV의 글자와 같아야 한다(SHALL)(테이블 정의서 §2-0: '3.10'이 '3.1'로 바뀌지 않게).

#### Scenario: W1-3 펌웨어 버전이 원본 글자 그대로다
- **GIVEN** 기준정보 적재를 마친 DB
- **WHEN** ref.firmware_release의 (product_code, fw_version) 목록을 firmware_history.csv와 비교한다
- **THEN** 39행이 모두 글자까지 같다(예: firmware_history.csv의 '1.50'은 '1.5'가 아니라 '1.50'이다)

### Requirement: 문의 유형별 해결시간 계수를 넣는다 (W1)
기준정보 적재 작업은 inquiry_category.sla_resolution_coef에 sla_policy.csv에서 계산한 계수(유형별 해결 목표 ÷ 같은 등급·우선순위의 TECH_SPEC 해결 목표)를 넣어야 하며(MUST), 한 유형 안에서 계수가 하나로 일정하지 않으면 적재를 멈춰야 한다(MUST). 출처는 운영진 README.html의 "Category 계수"다.

#### Scenario: W1-4 계수가 README 값과 같다
- **GIVEN** 기준정보 적재를 마친 DB
- **WHEN** ref.inquiry_category의 category와 sla_resolution_coef를 읽는다
- **THEN** TECH_SPEC 1.0, INSTALL 1.0, WARRANTY 1.5, ORDER_LEAD 0.5, MANUAL 0.5, DEFECT 1.0, COMPLIANCE 1.0, QUOTE 1.0, FW_UPDATE 1.0, RETURN 2.0이다
