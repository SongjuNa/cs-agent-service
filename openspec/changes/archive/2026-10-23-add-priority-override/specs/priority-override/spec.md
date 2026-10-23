# Spec Delta: priority-override

## Purpose

상담원이 사유를 적고 최종 우선순위를 바꾸면 SLA 목표를 새 우선순위로 다시 정하고 경고를 다시 점검하며 이력을 남긴다(명세서 v1.5 FR-028).

## ADDED Requirements

### Requirement: 사유가 있는 조정만 받아 목표를 다시 정한다 (FR-028)
조정은 사유 분류와 사유 글이 있어야 하고, 같은 우선순위나 종료 문의는 거부해야 한다(MUST)(근거: 명세서 FR-028 처리 1·6, 예외 1·2행). 규칙 결과는 그대로 두고 최종 우선순위·조정 표시·sla_id·목표 두 개를 바꾸며, 이전·새 값과 사유를 이력 한 줄로 남겨야 한다(MUST)(근거: FR-028 처리 2·3·5, FR-014 처리 5). 그 문의의 경고를 바로 다시 점검해야 하고 경과는 바꾸지 않아야 한다(MUST)(근거: FR-028 처리 4). 조정으로 바로 위반이 되면 반영 전에 확인을 받아야 한다(MUST)(근거: 화면 정의서 v1 SCR-03-P3. 명세서 FR-028 예외 3행은 "그대로 반영하고 확인 창"이라 다르며 C-65로 화면 정의서를 따름).

#### Scenario: AC-028-1 P4에서 P3로
- **GIVEN** CSV1-000031(MANUAL × STANDARD, 규칙 PR-07 → P4, 목표 72h/168h)을 끝나지 않은 문의로 둔다
- **WHEN** 상담원이 사유를 넣고 P3로 바꾼다
- **THEN** 목표가 24h/120h(SLA-MANUAL-STANDARD-P3)로 바뀌고 priority_rule_id는 PR-07 그대로이며 변경 이력에 이전·새 값과 사유가 남는다

#### Scenario: AC-028-2 사유 없음
- **GIVEN** 사유 칸이 빈 상태
- **WHEN** 저장한다
- **THEN** "조정 사유를 입력하세요"로 거부되고 값이 바뀌지 않는다

#### Scenario: AC-028-3 조정 120건 목표
- **GIVEN** 운영진 데이터 중 priority_adjusted_by_agent = Y인 120건(팀 정답지 미적재, 기술 명세서 §10-1 1·3번, C-67)
- **WHEN** 정답 priority로 목표를 다시 조회한다(명세서의 "조정 재생" 대신, C-67)
- **THEN** sla_first_response_target_h, sla_resolution_target_h가 100% 일치한다

#### Scenario: AC-027-5 조정으로 위반
- **GIVEN** CSV1-000031을 P4(목표 168h)로 두고 경과 130h에 RES_AT_RISK가 달린 상태
- **WHEN** P3(목표 120h)로 올리고 위반 확인을 한다(확인은 C-65 때문에 더한 조건)
- **THEN** RES_BREACHED 경고가 새로 생긴다

#### Scenario: 즉시 위반 확인
- **GIVEN** 조정하면 바로 위반이 되는 문의
- **WHEN** 확인 없이 조정한다
- **THEN** "이 조정으로 SLA 위반 상태가 됩니다. 계속할까요?"와 미리 보기가 돌아오고 값은 그대로다

#### Scenario: 종료 문의와 같은 값
- **GIVEN** RESOLVED 문의, 또는 지금과 같은 우선순위
- **WHEN** 조정한다
- **THEN** "종료된 문의는 바꿀 수 없음" 또는 "현재와 같은 우선순위"로 거부된다

#### Scenario: 목표가 늘면 경고 해제
- **GIVEN** RES_AT_RISK가 달린 문의
- **WHEN** 목표가 충분히 늘어나는 우선순위로 바꾼다
- **THEN** 그 경고에 해제 시각이 남는다
