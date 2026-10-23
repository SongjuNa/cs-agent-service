# Design: SLA 위험 경고

## Context

동기는 proposal.md의 Why를 본다. 따를 기준은 다음과 같다.
- 명세서 v1.5 FR-027(처리 1~6, 예외 3행, AC-027-1~5) (근거: 명세서 FR-027).
- 기술 명세서 v1.4 §6-4(SLA 계산식, 주기 점검 1·3·4, 시계 돌리기), §10-1 3(재생) (근거: 기술 명세서 §6-4, §10-1).
- 테이블 정의서 v1.3(schema.sql): svc.sla_alert(UNIQUE(sub_ticket_id, alert_type), 넣은 뒤 cleared_at_utc·notified_to만 바꿈), svc.inquiry_sla(), ref.sla_setting at_risk_threshold, scoring 스키마의 같은 표·함수 (근거: schema.sql 4-9, 3번 inquiry_sla).

## Goals / Non-Goals

**Goals**
- 기준 시각마다 경고를 정확한 발생 시각으로 한 번씩 달고, 5분마다 자동으로 점검한다(근거: FR-027 처리 1·2, 예외 1행).

**Non-Goals**
- 접수함 정렬·아이콘, 우선순위 조정 API, 리마인드(proposal "범위 밖") (근거: proposal 범위 밖).

## Decisions

### 1. 경고 점검 (`app/sla/alerts.py`)

`raise_alerts(conn, as_of, schema="svc") -> list[(sub_ticket_id, alert_type, raised_at)]` (구현 선택. 이름은 기술 명세서에 없음).

| 경고 | 대상 | 조건(as_of 기준) | 발생 시각 | 근거 |
|---|---|---|---|---|
| RES_AT_RISK | 상태 NEW·IN_PROGRESS·ESCALATED, 해결 목표 있음 | 해결 경과 ≥ 목표 × 0.75 | 접수 + 대기 합 + 목표 × 0.75 | FR-027 처리 2·4, §6-4 주기 점검 1 |
| RES_BREACHED | 같음 | 해결 경과 > 목표 | 접수 + 대기 합 + 목표 | 같음. "넘으면"은 inquiry_sla의 BREACHED 조건(>)과 같게 (근거: FR-027 처리 2, schema.sql inquiry_sla) |
| FR_AT_RISK | 상태 NEW·IN_PROGRESS·WAITING_CUSTOMER·ESCALATED, 1차 응답 목표 있음, as_of까지 1차 응답 없음 | 1차 응답 경과 ≥ 목표 × 0.75 | 접수 + 목표 × 0.75 | FR-027 처리 3, §6-4(1차 응답 시계는 멈추지 않음) |
| FR_BREACHED | 같음 | 1차 응답 경과 > 목표 | 접수 + 목표 | 같음 (근거: FR-027 처리 3) |

- 경과·목표·대기 합은 `{schema}.inquiry_sla(as_of)`에서 읽는다. 1차 응답 여부는 inquiry_sla가 주지 않으므로 sub_ticket.first_response_at_utc ≤ as_of로 본다(구현 선택). 75%는 ref.sla_setting at_risk_threshold의 글("elapsed >= 75% of target")에서 inquiry_sla와 같은 식으로 숫자를 뽑고, 없으면 0.75(근거: §6-4 "75%는 ref.sla_setting에서 읽는다", schema.sql inquiry_sla thr).
- AT_RISK와 BREACHED는 따로 판단한다. 점검을 건너뛰어 한 번에 둘 다 넘었으면 두 줄을 각자의 실제 시각으로 넣는다(근거: FR-027 예외 1행 "그동안의 변화를 한 번에 반영". 두 줄 다 넣는 것은 구현 선택).
- `INSERT … ON CONFLICT (sub_ticket_id, alert_type) DO NOTHING`으로 문의당 한 번(근거: FR-027 처리 2 "같은 종류의 경고는 문의당 한 번", schema.sql UNIQUE).
- elapsed_h·target_h는 발생 당시 값이다. elapsed_h = 넘은 기준값(목표 × 0.75 또는 목표), target_h = 그때 목표(근거: 기술 명세서 §6-2 "elapsed_h·target_h(발생 당시 값, FR-027 2번)", 테이블 정의서 4-9 "그때 경과 시간"). 발생 당시 경과는 정의상 기준값과 같다(구현 선택).
- 발생 시각 식은 §6-4 그대로 대기 합을 as_of까지의 합으로 쓴다. 조건을 넘은 뒤에 대기 구간이 생겼다면 실제보다 늦게 계산된다. 점검을 건너뛴 사이 조건을 넘고 WAITING_CUSTOMER가 된 문의는 해결 경고를 받지 않는다(처리 4). FR-027 예외 1행 "실제 조건 충족 시각"과 다를 수 있다(C-59). (근거: 기술 명세서 §6-4 주기 점검 1, C-59)
- SLA 미정(목표 NULL)은 그 시계를 점검하지 않는다(근거: FR-027 예외 2행).
- schema는 "svc"와 "scoring"만 받는다(재생 채점용, 구현 선택).

### 2. 경고 해제

- 풀리지 않은 경고(cleared_at_utc IS NULL) 가운데 경고의 target_h가 지금 목표와 다르고, 지금 목표로는 조건이 맞지 않으면 cleared_at_utc = as_of로 쓴다(근거: FR-027 처리 6 "목표가 늘어 경고 조건이 풀리면 해제 시각", §6-4).
- 해제된 경고는 같은 종류로 다시 달 수 없다. UNIQUE(sub_ticket_id, alert_type) 때문이다. 목표가 늘어 해제된 뒤 시간이 지나 새 목표의 75%·100%에 닿아도 다시 달리지 않아, 해제되지 않은 경고만 보는 접수함·현황 목록에서 빠진다(C-60). (근거: schema.sql sla_alert UNIQUE, C-60)
- 1차 응답을 보내거나 해결해도 경고는 풀지 않는다(근거: FR-027 처리 6은 목표 변경만 말함).

### 3. 주기 점검 (`app/scheduler.py`)

- `periodic_check(conn, as_of)`: 경고 점검 → `close_due`(무응답 종료, 해결 뒤 종료) 순서로 부르고 건수를 돌려준다(근거: §6-4 "한 주기에 네 가지를 차례로": 1 경고, 3 무응답 종료, 4 해결 뒤 종료. 2 리마인드는 14번 변경).
- 각 단계를 자기 트랜잭션에서 돌리고, 오류가 나면 서버 로그(실행 로그 표 아님)에 남기고 다음 단계로 넘어간다. 다음 주기에 같은 조건으로 다시 잡힌다(근거: FR-027 예외 3행 "다음 주기에 재시도"). 실행 로그 표(agent_run)는 티켓 번호가 필수이고 trigger 값에 스케줄러가 없어 주기 점검 오류를 넣을 수 없다. FR-027 예외 3행·§6-5의 실행 로그는 FR-036(15번 변경)에서 정한다(C-61).
- 주기 5분은 `app.scheduler.INTERVAL_MINUTES` 한 곳에 둔다. 접수함·현황 자동 갱신(FR-029 처리 6, FR-047 처리 6)이 같은 값을 쓴다(구현 선택).
- FastAPI lifespan에서 APScheduler BackgroundScheduler를 시작하고(종류·max_instances 1·coalesce는 구현 선택) 5분 간격(`interval`)으로 `periodic_check(새 연결, now)`를 부른다. 서버를 끌 때 멈춘다(근거: §6-4 "APScheduler를 FastAPI 안에서 돌린다", "5분", T30).
- 설정 `SCHEDULER_ENABLED`(기본 켜짐)으로 끌 수 있다. 시험과 일괄 작업은 스케줄러 없이 `periodic_check`를 직접 부른다(구현 선택).
- apscheduler 3.10.4를 의존성에 더한다(근거: §6-4 APScheduler. 판은 구현 선택).

### 4. 상세 API

- 하위 문의마다 `alerts`: sla_alert의 alert_type, raised_at_utc, elapsed_h, target_h, cleared_at_utc를 발생 시각순으로(근거: FR-027 출력 "경고 목록(문의 순번, 종류, 발생 시각, 해제 시각)", "티켓 상세에 경고 이력").

### 5. 시험 (`tests/acceptance/test_sla_alert.py`)

- AC-027-1: CSV1-003401을 svc에 정답지 시각으로 만들고 스냅샷으로 점검 → RES_AT_RISK 한 줄, 발생 시각 = 접수 + 270h, svc.v_inquiry_inbox의 alerts에 RES_AT_RISK(근거: AC-027-1. "접수함 위쪽"은 18번 변경).
- AC-027-2: 같은 기준 시각·다음 주기(+5분)에 다시 점검 → 새 줄 없음. (근거: AC-027-2)
- AC-027-3: CSV1-003578(WAITING_CUSTOMER) → 해결 경고 없음. 이 문의는 31%라 규칙 없이도 경고가 없으므로, 75%를 넘은 뒤 WAITING_CUSTOMER가 된 문의(CSV1-003401에 300h 시점 정보 요청)로 처리 4를 따로 확인한다. (근거: AC-027-3)
- AC-027-4: 4,000건을 scoring에 재생(10번의 replay), 스냅샷으로 scoring 경고 점검. 명세서가 이름으로 정한 팀 정답지 문의 5건(CSV1-003290, 003742, 003774, 003820, 003888)을 빼면 미해결 360건이고, 정답이 AT_RISK인 34건은 모두 RES_AT_RISK, BREACHED 140건은 모두 RES_BREACHED(재현율 100%)(근거: AC-027-4, 명세서 그룹 5 데이터 사실).
- FR-027 처리 3: CSV1-003950(NEW, 1차 응답 없음, 목표 16h) → FR_AT_RISK(접수 + 12h), FR_BREACHED(접수 + 16h). (근거: FR-027 처리 3, tickets.csv CSV1-003950)
- 예외 1행: 한참 뒤 한 번만 점검해도 발생 시각은 조건을 넘은 시각(AC-027-1에서 확인). (근거: FR-027 예외 1행)
- 예외 2행: 목표가 없는 문의 → 경고 없음. (근거: FR-027 예외 2행)
- 처리 6: 목표를 늘린 뒤 점검 → 해제 시각. AC-027-5(P3로 올려 BREACHED)는 12번 변경(근거: proposal 범위 밖).
- 주기 점검: 한 번 부르면 경고와 무응답 종료가 함께 일어남. 앱을 켜면 5분 간격 작업 하나가 등록되고 끄면 멈춤. (근거: §6-4 주기 점검, design 결정 3)
- 경고 코드가 app.llm을 import하지 않음(근거: 명세서 그룹 4 머리).

## Risks / Trade-offs

- 4,000건 재생 시험이 하나 더 늘어 약 15초 더 걸린다(근거: 변경 10 시험 시간).
- 스케줄러는 서버 프로세스 하나 기준이다. 여러 프로세스로 띄우면 중복 실행되지만 UNIQUE와 전이표가 중복 쓰기를 막는다(구현 선택).
