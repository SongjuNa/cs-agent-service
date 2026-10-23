# Spec Delta: sla-alert

## Purpose

주기적으로 끝나지 않은 문의의 SLA 두 시계를 점검해 위험·위반 경고를 문의당 한 번씩 정확한 발생 시각으로 남긴다(명세서 v1.5 FR-027, 기술 명세서 v1.4 §6-4).

## ADDED Requirements

### Requirement: 조건을 처음 넘은 경고를 한 번씩 단다 (FR-027)
끝나지 않은 문의의 해결 경과가 목표의 75% 이상이면 RES_AT_RISK, 목표를 넘으면 RES_BREACHED를, 1차 응답이 없는 문의의 1차 응답 경과가 75% 이상이면 FR_AT_RISK, 넘으면 FR_BREACHED를 달아야 한다(MUST)(근거: 명세서 FR-027 처리 1~3). 같은 종류는 문의당 한 번이어야 하고, 발생 시각은 조건을 실제로 넘은 시각이어야 한다(MUST)(근거: FR-027 처리 2, 예외 1행, 기술 명세서 §6-4). WAITING_CUSTOMER 문의에는 해결 경고를 새로 달지 않고, SLA 미정 문의는 점검하지 않아야 한다(MUST)(근거: FR-027 처리 4, 예외 2행). 목표가 늘어 조건이 풀리면 해제 시각을 남겨야 한다(MUST)(근거: FR-027 처리 6).

#### Scenario: AC-027-1 위험 경고
- **GIVEN** CSV1-003401(IN_PROGRESS, 목표 360h)을 정답지 시각으로 만든 문의
- **WHEN** 스냅샷 시점에 점검한다
- **THEN** RES_AT_RISK 경고가 한 줄 생기고 발생 시각은 접수 + 270h이며 접수함 뷰의 경고 목록에 보인다

#### Scenario: AC-027-2 두 번째 점검
- **GIVEN** AC-027-1 뒤
- **WHEN** 다음 주기에 다시 점검한다
- **THEN** 경고가 새로 생기지 않는다

#### Scenario: AC-027-3 고객 대기 중
- **GIVEN** CSV1-003578(WAITING_CUSTOMER)
- **WHEN** 점검한다
- **THEN** 해결 경고가 생기지 않는다

#### Scenario: AC-027-4 운영진 미해결 문의 재현율
- **GIVEN** 운영진 4,000건을 정답지 시각으로 재생한 scoring 스키마의 미해결 360건(팀 정답지 문의 5건 제외)
- **WHEN** 스냅샷 시점으로 점검해 정답 sla_resolution_status와 비교한다
- **THEN** AT_RISK 34건은 모두 RES_AT_RISK, BREACHED 140건은 모두 RES_BREACHED를 받는다

#### Scenario: 위험을 넘은 뒤 고객 대기
- **GIVEN** 해결 경과가 75%를 넘은 뒤 정보 요청을 보내 WAITING_CUSTOMER인 문의
- **WHEN** 점검한다
- **THEN** 해결 경고가 생기지 않는다

#### Scenario: 1차 응답 경고
- **GIVEN** CSV1-003950(NEW, 1차 응답 없음, 목표 16h)
- **WHEN** 스냅샷 시점에 점검한다
- **THEN** FR_AT_RISK(접수 + 12h)와 FR_BREACHED(접수 + 16h)가 생긴다

#### Scenario: SLA 미정
- **GIVEN** 목표가 없는 문의
- **WHEN** 점검한다
- **THEN** 경고가 생기지 않는다

#### Scenario: 목표가 늘어 해제
- **GIVEN** RES_AT_RISK가 달린 문의의 해결 목표를 경과보다 충분히 늘린 경우
- **WHEN** 다시 점검한다
- **THEN** 그 경고에 해제 시각이 기록된다

### Requirement: 5분마다 주기 점검을 돌린다 (FR-027, 기술 명세서 §6-4)
서버 안의 스케줄러가 5분마다 경고 점검과 무응답 종료·해결 뒤 종료를 차례로 해야 하고, 한 단계의 오류는 서버 로그에 남기고 다음 주기에 다시 해야 한다(MUST)(근거: 기술 명세서 §6-4 주기 점검, FR-027 처리 1·4, 예외 3행). 상세 API는 하위 문의마다 경고 이력을 돌려줘야 한다(MUST)(근거: FR-027 출력).

#### Scenario: 한 주기
- **GIVEN** 경고 조건을 넘은 문의와 무응답 168시간이 지난 문의
- **WHEN** 주기 점검을 한 번 부른다
- **THEN** 경고가 생기고 무응답 문의는 CLOSED가 된다

#### Scenario: 서버 시작
- **GIVEN** 스케줄러가 켜진 설정
- **WHEN** 서버를 켠다
- **THEN** 5분 간격 작업 하나가 등록되고, 서버를 끄면 멈춘다
