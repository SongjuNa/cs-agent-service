# Design: 운영 대시보드

## Context

나의 업무 현황(FR-047)은 담당 조건(상담원 또는 부서)으로 위험·위반 목록과 SLA 미정 건수를 이미 낸다. 쿼리는 schema 인자로 svc와 scoring(재생 채점)을 모두 읽는다(근거: `backend/app/db/workload.py` _risks·workload). 경고는 svc.sla_alert, 남은 시간은 inquiry_sla(as_of) 함수가 낸다(근거: schema.sql). 이 기능은 규칙 코드가 아니며 언어 모델을 부르지 않는다(근거: FR-034 수행 주체 "시스템(집계)").

## Goals / Non-Goals

- 목표: 전 부서의 위험·위반 목록과 건수 두 가지를 FR-026·027 값 그대로 보인다(근거: FR-034 처리 1~4).
- 목표 아님: 주간 품질 추이 계산, 목업의 다른 탭(근거: proposal 범위 밖).

## Decisions

### 1. 위험·위반 목록 (`GET /dashboard/alerts`)

| 항목 | 정한 것 | 근거 |
|---|---|---|
| 쿼리 | workload.py의 위험 목록 쿼리에서 담당 조건을 빼고 같은 함수를 쓴다. 담당 조건은 인자로 받는다 | 기술 명세서 v1.4 §8-1 dashboard 행 |
| 대상 | 미해결(NEW, IN_PROGRESS, WAITING_CUSTOMER, ESCALATED), sla_id 있음, 기준 시각에 살아 있는 경고 | FR-034 처리 1, 예외 2행, workload.py _risks |
| 열 | ticket_id, seq·inquiry_count, assigned_dept, priority, status, alerts, remaining_h | FR-034 처리 1 |
| 필터 | dept, alert, priority (모두 선택). as_of(기본 지금) | FR-034 입력, `GET /me/workload?as_of=`와 같은 방식(구현 선택) |
| 정렬 | remaining_h 오름차순, 같으면 sub_ticket_id | FR-034 처리 1, workload.py _risks |
| 빈 목록 | 화면에 "SLA 위험·위반 문의가 없습니다" | FR-034 예외 1행 |

### 2. 집계 (`GET /dashboard/summary`)

| 항목 | 정한 것 | 근거 |
|---|---|---|
| 부서별 미해결 | assigned_dept별 NEW, IN_PROGRESS, WAITING_CUSTOMER, ESCALATED 건수 | FR-034 처리 2 |
| SLA 상태별 | inquiry_sla(as_of)의 1차 응답 상태(MET, BREACHED, ON_TRACK)·해결 상태(MET, BREACHED, ON_TRACK, AT_RISK, N/A)별 건수 | FR-034 처리 3·4 |
| 종료 포함 | include_closed=false(기본)면 미해결만, true면 전체 | FR-034 처리 3 |
| SLA 미정 | sla_id가 빈 하위 문의 수를 sla_unset으로 따로 | FR-034 예외 2행, workload.py sla_unset |
| as_of | 위와 같음 | 구현 선택 |

### 3. 주간 품질 추이 (`GET /dashboard/quality-trend`)

- 빈 목록을 돌려준다. FR-044가 eval.eval_summary를 채우면 그 표를 읽도록 바꾼다(근거: FR-034 처리 6, 의존성, 기술 명세서 §8-1 quality-trend 행 "결과 없으면 빈 목록").

### 4. 화면 (`OpsDashboardPage.tsx`)

| 항목 | 정한 것 | 근거 |
|---|---|---|
| 위치 | 메뉴 관리자 › 운영 대시보드, 탭 "개요" 하나 | 목업 ONCE v1.41(저장소 밖), 구현 선택. 화면 정의서 v1의 "SCR-04 전체 보기 스위치"와 다름 |
| 영역 | ① 위험·위반 목록(필터 3개) ② 부서별 미해결 표 ③ SLA 상태별 건수(종료 포함 스위치) ④ 주간 품질 추이 "아직 집계 없음" | FR-034 처리 1~3·6 |
| 행 클릭 | 티켓 상세로 이동 | FR-034 처리 5, AC-034-4 |
| 갱신 | 5분마다 다시 읽기. 실패하면 이전 값을 두고 "대시보드를 불러오지 못함. 새로고침" | FR-034 처리 5·예외 3행, 기술 명세서 §6-4 |
| 응답 모델 | DashAlerts, DashSummary, QualityTrend | 구현 선택, 변경 add-api-response-models 결정 1 |

### 5. 시험 (`backend/tests/acceptance/test_ops_dashboard.py`)

| 시험 | 확인하는 것 | 근거 |
|---|---|---|
| AC-034-1 | scoring 스키마 재생 결과(미해결 360건), as_of = 스냅샷에서 목록에 해결 AT_RISK 34건·BREACHED 140건이 모두 있다 | AC-034-1, AC-027-4, workload.py schema 인자 |
| AC-034-2 | 같은 상태의 부서별 미해결 = TS_LV 67, WARRANTY_DESK 60, TS_AUTO 52, SCM 52, GCS_L1 35, TS_ENERGY 26, CERT 26, SALES_OPS 21, TS_MV 10, FIELD_SVC 6, TS_TRF 5 | AC-034-2, 명세서 그룹 5 데이터 사실 |
| AC-034-3 | 우선순위를 올려 경고가 새로 생긴 문의가 다음 점검 뒤 목록에 있다 | AC-034-3, AC-027-5 |
| AC-034-4 | 화면: 목록 행 클릭 → 상세 주소 | AC-034-4 |
| AC-034-6 | quality-trend가 빈 목록이고 summary·alerts는 정상 | AC-034-6 |
| SLA 미정 | sla_id가 빈 하위 문의는 목록에 없고 sla_unset에 센다 | FR-034 예외 2행 |

AC-034-4는 화면 동작이라 시험 코드에서는 상세 주소가 응답의 ticket_id로 만들어지는지만 본다(구현 선택). AC-034-5는 범위 밖이다(근거: proposal 범위 밖).

## Risks / Trade-offs

- 전 부서를 한 번에 세므로 4,000건 적재 상태에서 inquiry_sla(as_of) 계산이 한 번에 돈다. 나의 업무 현황과 같은 MATERIALIZED 방식을 쓰고, 느리면 따로 보고한다(근거: workload.py _risks, 구현 선택).
- 로그인이 없어 관리자 화면도 누구나 연다(근거: D23).
