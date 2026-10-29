# Design: 운영 대시보드 AI·제품·고객 탭

## Context

이 변경은 add-ops-dashboard 위에 쌓는다. 같은 파일(`app/db/dashboard.py`, `app/api/dashboard.py`)에 주소를 더하고, 같은 as_of 방식을 쓴다(근거: 변경 add-ops-dashboard 결정 1·2). 정답지(gold)나 채점 표는 읽지 않는다(근거: CLAUDE.md 규칙 6).

## Goals / Non-Goals

- 목표: 관리자가 초안 처리 현황과 제품·고객별 위험을 본다(근거: 목업 기능 FR 초안 05).
- 목표 아님: 정답 기준 품질 점수, 자동 발송 현황(근거: proposal 범위 밖, CLAUDE.md 규칙 3).

## Decisions

### 1. AI 탭 (`GET /dashboard/ai?from=&to=`)

| 값 | 세는 법 | 근거 |
|---|---|---|
| drafts | 기간 안에 만든 INFO_REQUEST·FINAL_REPLY DRAFT 행 수(sender SYSTEM) | 테이블 정의서 v1.3 svc.ticket_message |
| sent | 기간 안의 SENT 행 수(sender AGENT) | 테이블 정의서 v1.3 svc.ticket_message |
| edited_rate | sent 중 edited_yn = true 비율 | FR-031 처리 3, 테이블 정의서 v1.3 |
| overrides | sent 중 override_check = true 수 | FR-031 처리 2, 테이블 정의서 v1.3 |
| checks | eval.self_check의 check_type별 passed_yn = false 수 | 테이블 정의서 v1.3 eval.self_check |
| 기간 | from·to(UTC), 기본 최근 7일 | 구현 선택 |

### 2. 제품·고객 탭 (`GET /dashboard/products`, `/dashboard/customers`)

| 항목 | 정한 것 | 근거 |
|---|---|---|
| 제품 | family, product_code별 ticket_count, open_count, alert_count. 제품을 모르는 하위 문의는 "제품 미상" 한 줄로 센다 | 테이블 정의서 v1.3 ref.product·svc.sub_ticket·sla_alert |
| 고객 | tier별, country별 ticket_count, open_count, alert_count | 테이블 정의서 v1.3 ref.customer |
| 미해결·경고 | add-ops-dashboard와 같은 정의(미해결 4상태, 기준 시각에 살아 있는 경고) | 구현 선택, 변경 add-ops-dashboard 결정 1·2 |
| include_closed | false(기본)면 미해결 하위 문의만 센 ticket_count | FR-034 처리 3과 같은 스위치, 구현 선택 |

### 3. 화면

| 항목 | 정한 것 | 근거 |
|---|---|---|
| 탭 | 개요, AI, 제품, 고객 | 목업 viewOps(저장소 밖), 구현 선택 |
| 행 클릭 | 제품·고객 행 → 접수함을 그 제품 또는 고객으로 거른 화면 | FR-029 필터, 구현 선택 |
| 응답 모델 | DashAi, DashProducts, DashCustomers | 구현 선택, 변경 add-api-response-models 결정 1 |

### 4. 시험 (`backend/tests/acceptance/test_dashboard_tabs.py`)

| 시험 | 확인하는 것 | 근거 |
|---|---|---|
| 제품 합 | 미해결 360건 재생 상태에서 제품 탭 open_count 합 = 360 | 목업 기능 FR 초안 05 AC 초안, AC-034-2 |
| 고객 합 | 같은 상태에서 등급별 open_count 합 = 360 | 구현 선택(결정 2) |
| AI 세기 | 초안 2건 만들고 1건을 고쳐 발송하면 drafts 2, sent 1, edited_rate 1.0 | 구현 선택(결정 1) |
| gold 안 읽음 | `app/db/dashboard.py`에 gold. 이 나오지 않는다 | CLAUDE.md 규칙 6 |

## Risks / Trade-offs

- 자체 검사는 실행마다 행이 쌓이므로 같은 초안의 검사가 여러 번 셀 수 있다. 하위 문의별 마지막 실행만 세는지는 구현 때 정해 적는다(근거: 테이블 정의서 v1.3 eval.self_check, 구현 선택).
