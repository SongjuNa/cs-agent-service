# inquiry-understanding Specification

## Purpose
고객 본문을 언어 모델(L1·L2)로 읽어 본문 언어, 문의 유형, 긴급도, 제공 항목을 정하고 코드로 검사해 상태 객체에 담는다. 규칙 엔진의 입력을 만드는 단계다(기술 명세서 v1.4 §2-2 T1·T2·Q1, §3).

## Requirements

### Requirement: 답장 언어와 본문 언어를 따로 정한다 (FR-004)
문의 이해는 language를 입력값 그대로 쓰고, body_language는 L1이 본문으로 판정한 15개 코드 중 하나로 정해야 한다(MUST)(근거: 명세서 FR-004 처리 1·2). 판정 확신도가 0.6 미만이거나 L1이 코드값 밖 응답을 두 번 내면 body_language = language로 두고 "언어 판정 불확실"을 표시한 뒤 다음 단계를 계속해야 한다(MUST)(근거: FR-004 처리 3·예외, 기술 명세서 §3-6). L1이 시간 초과·오류로 두 번 실패하면 실행을 FAILED로 끝내야 한다(MUST)(근거: FR-005 예외 2행, 기술 명세서 §2-2 T2).

#### Scenario: AC-004-1 전화 메모는 본문 언어가 다르다
- **GIVEN** CSV1-003578 (전화, language = it, 영어 메모)
- **WHEN** 문의를 이해한다
- **THEN** language = it, body_language = en이다

#### Scenario: AC-004-2 아랍어 이메일
- **GIVEN** CSV1-000008 (이메일, 아랍어 본문)
- **WHEN** 문의를 이해한다
- **THEN** language = ar, body_language = ar이다

#### Scenario: AC-004-3 판정이 실패해도 흐름은 계속된다
- **GIVEN** 언어 모델이 본문 언어를 정하지 못하는 상태(L1이 두 번 모두 스키마 밖 응답. 시험 티켓 선택은 구현 선택)
- **WHEN** CSV1-000008을 이해한다
- **THEN** body_language = language(ar)이고 "언어 판정 불확실"이 표시되며 다음 단계(제공 항목 추출)가 실행된다

### Requirement: 문의 유형을 10종 중 하나로 정한다 (FR-005)
문의 이해는 L1에 가린 본문, channel, language, product_family와 팀 정답지 작성 기준서 v0.3 1-1장의 유형 정의를 넣어 category_code, 확신도, 근거 문장을 받아야 한다(MUST)(근거: 명세서 FR-005 처리 1·2, 기술 명세서 §3-1). 제목(inquiry_subject)과 정답 열은 입력에 넣지 않아야 한다(MUST)(근거: FR-005 입력 "제외", 기술 명세서 §3-3). 10종 밖 응답이 두 번이면 category_code를 비우고 "분류 실패"를 표시해야 하고, 확신도가 0.6 미만이면 "확신 낮음"을 표시해야 한다(MUST)(근거: FR-005 처리 3·4, §3-6).

#### Scenario: AC-005-1 추적표 9건의 유형
- **GIVEN** CSV1-000017, 000007, 000004, 000097, 000039, 000008, 000031, 003578, 000085의 입력(gold.v_inputs)
- **WHEN** 문의를 이해한다
- **THEN** category_code가 차례로 DEFECT, DEFECT, QUOTE, RETURN, RETURN, FW_UPDATE, MANUAL, TECH_SPEC, FW_UPDATE다

#### Scenario: AC-005-2 제목은 언어 모델에 가지 않는다
- **GIVEN** 제목이 "Demande de tarif"로 시작하는 CSV1-000004 (시험은 제목을 넣은 입력을 주어, 처리 흐름이 제목을 버리는지 본다)
- **WHEN** 문의를 이해한다
- **THEN** 언어 모델에 보낸 글과 입력 항목 이름 목록에 제목 문자열과 inquiry_subject가 없다

#### Scenario: AC-005-3 코드값 밖 응답이 두 번이면 분류 실패
- **GIVEN** 언어 모델이 category_code에 10종 밖 값을 두 번 내는 상태(시험 티켓 선택은 구현 선택)
- **WHEN** CSV1-000004를 이해한다
- **THEN** category_code가 비고 "분류 실패"가 표시된다

### Requirement: 긴급도를 6값 중 하나로 정한다 (FR-007)
문의 이해는 L1에 urgency_codebook.csv 6값의 설명과 팀 정답지 작성 기준서 v0.3 2장의 판단 기준을 넣어 urgency_flag와 근거 문장을 받아야 한다(MUST)(근거: 명세서 FR-007 처리 1·2, 기술 명세서 §3-1). 둘 이상이면 SAFETY > SITE_DOWN > PROD_IMPACT > COMMISSION > DEADLINE 순으로 높은 것을 코드로 다시 골라야 한다(MUST)(근거: FR-007 처리 3, §3-2). L1이 요청을 둘 이상 돌려주면 모든 요청 중 가장 높은 값을 써야 한다(MUST)(구현 선택: 1순위는 하위 문의 1개라 다른 요청의 SAFETY를 버리지 않기 위함). 6값 밖 응답이 두 번이면 NONE으로 두고 "긴급도 판정 실패"를 표시해야 한다(MUST)(근거: FR-007 처리 4).

#### Scenario: AC-007-1 단자 과열·변색은 SAFETY
- **GIVEN** CSV1-000017 (단자 과열·변색, 설비 정지)
- **WHEN** 문의를 이해한다
- **THEN** urgency_flag = SAFETY이고 근거 문장이 있다 (운영진 값은 SITE_DOWN, 기준서 K4)

#### Scenario: AC-007-2 입찰 기한은 DEADLINE
- **GIVEN** CSV1-000004 (입찰 기한 2025-10-28 명시)
- **WHEN** 문의를 이해한다
- **THEN** urgency_flag = DEADLINE이다

#### Scenario: AC-007-3 특이사항 없는 매뉴얼 요청은 NONE
- **GIVEN** CSV1-000031 (매뉴얼 요청)
- **WHEN** 문의를 이해한다
- **THEN** urgency_flag = NONE이다

### Requirement: 본문에서 제공 항목을 뽑는다 (FR-008)
문의 이해는 L2에 항목 코드북 32개와 그 제품군×유형의 필수 항목, 근거 문장을 넣어 {항목, 원문 값, 정리 값, 위치}를 받아야 한다(MUST)(근거: 명세서 FR-008 처리 1, 기술 명세서 §3-2). 코드북 밖 항목은 버리고, 펌웨어 버전은 숫자·점(끝 0 보존), 날짜는 YYYY-MM-DD, 수량은 정수, 제품 코드는 ref.product와 대조해 정리해야 한다(MUST)(근거: FR-008 처리 2·3). error_code와 current_fw는 error_code_reported, fw_version_reported에 복사하고, product_code가 비어 있으면 본문의 제품 코드를 ref.product와 대조해 채우고, 대조에 실패하면 "제품 미확정"을 표시해야 한다(MUST)(근거: FR-008 처리 4·5). L2가 실패하면 빈 목록과 "추출 실패"로 계속해야 한다(MUST)(근거: FR-008 예외).

#### Scenario: AC-008-1 견적 문의의 네 항목
- **GIVEN** CSV1-000004 본문
- **WHEN** 제공 항목을 뽑는다
- **THEN** product_model = HMI-XGT-eXP60, quantity = 1, incoterms = CIF Le Havre, required_date = 2025-10-28이 나온다

#### Scenario: AC-008-2 펌웨어 버전은 따로 복사된다
- **GIVEN** CSV1-000008 본문 (현재 3.40. 명세서 AC의 "3.50으로 업데이트 요청"은 본문에 없고 운영진 답변에만 있다)
- **WHEN** 제공 항목을 뽑는다
- **THEN** fw_version_reported = 3.40이고 product_model, tool_version, logs가 제공 항목에 있다

#### Scenario: AC-008-3 에러 코드는 따로 복사된다
- **GIVEN** CSV1-001112 본문 (E.OC 트립)
- **WHEN** 제공 항목을 뽑는다
- **THEN** error_code_reported = E.OC이다

#### Scenario: AC-008-4 비어 있는 제품 코드를 본문으로 채운다
- **GIVEN** CSV1-000004에서 product_code를 비운 입력 (본문에 "HMI-XGT-eXP60"이 있음)
- **WHEN** 문의를 이해한다
- **THEN** 하위 문의의 product_code가 HMI-XGT-eXP60이다
