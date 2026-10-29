## ADDED Requirements

### Requirement: 전 부서 위험·위반 목록과 건수를 보인다 (FR-034)
운영 대시보드는 해제되지 않은 SLA 경고가 있는 미해결 하위 문의를 부서 구분 없이 남은 시간 오름차순으로 보여야 하고, 부서별 미해결 건수와 SLA 상태별 건수를 FR-026·027 값을 세기만 해서 보여야 한다(MUST). SLA 미정 문의는 목록에서 빼고 건수만 따로 보여야 한다(MUST).

#### Scenario: AC-034-1 위험·위반 목록
- **GIVEN** 미해결 360건을 적재하고 기준 시각 = 스냅샷
- **WHEN** 대시보드를 연다
- **THEN** 목록에 해결 AT_RISK 34건과 BREACHED 140건이 모두 있다

#### Scenario: AC-034-2 부서별 미해결 건수
- **GIVEN** 같은 상태
- **WHEN** 부서별 미해결 건수를 본다
- **THEN** TS_LV 67, WARRANTY_DESK 60, TS_AUTO 52, SCM 52, GCS_L1 35, TS_ENERGY 26, CERT 26, SALES_OPS 21, TS_MV 10, FIELD_SVC 6, TS_TRF 5이다

#### Scenario: AC-034-3 새 경고
- **GIVEN** 우선순위 조정으로 경고가 새로 생긴 문의(AC-027-5)
- **WHEN** 다음 점검 뒤 목록을 본다
- **THEN** 그 문의가 목록에 있다

#### Scenario: AC-034-4 상세 열기
- **GIVEN** 목록의 한 행
- **WHEN** 누른다
- **THEN** 그 티켓 상세가 열린다

#### Scenario: SLA 미정
- **GIVEN** SLA 목표가 없는 미해결 하위 문의
- **WHEN** 대시보드를 연다
- **THEN** 목록에 없고 "SLA 미정 n건"에 센다

### Requirement: 주간 품질 추이 자리를 둔다 (FR-034)
FR-044 결과가 없으면 주간 품질 추이 영역에 "아직 집계 없음"을 보이고 나머지 영역은 정상이어야 한다(MUST).

#### Scenario: AC-034-6 집계 없음
- **GIVEN** FR-044 결과 없음
- **WHEN** 대시보드를 연다
- **THEN** 그 영역에 "아직 집계 없음"이 보이고 나머지 영역은 정상이다
