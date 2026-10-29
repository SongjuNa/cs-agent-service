# 화면 명세: SCR-06 운영 대시보드 (임시 번호)

> 보류(2026-10-29 조장 결정): 어떤 화면을 보여 줄지 아직 정하지 않아, 앱에서는 목업 화면으로 둔다. 아래 명세는 결정 뒤 다시 본다.

- 연결 요구사항: FR-034 (AC-034-1~4·6), FR-초안-05(AI·제품·고객 탭), 2026-10-29 조장 결정(별도 메뉴)
- 기준 목업: cs-agent-mockup_v1.42.html `viewOps`, `opsOverview`, `opsAI`, `opsProduct`, `opsCust` (레이아웃 기준선: 머리 → 탭 → 타일 + 표)
- 화면 정의서: 없음(v1 0-2 #4의 "SCR-04 전체 보기 스위치"는 2026-10-29 결정으로 별도 메뉴가 됨)
- 사용 API (아직 없음): `GET /dashboard/alerts`, `/dashboard/summary`, `/dashboard/quality-trend` (변경 add-ops-dashboard), `GET /dashboard/ai`, `/dashboard/products`, `/dashboard/customers` (변경 add-dashboard-tabs)

## 영역

| 요소 ID | 탭 | 표시 | API 칸 |
|---|---|---|---|
| N-06-01 | 머리 | "운영 대시보드 · 전 부서 · 관리자용 · {as_of} UTC 기준" | as_of |
| N-06-02 | 개요 | 타일: 미해결 문의(부서 수), 해결 기한 지남, 해결 기한 임박, 고객 회신 대기 | summary |
| N-06-03 | 개요 | ① 위험·위반 목록: 티켓(복합이면 #k), 담당 부서, 우선순위, 상태, 경고, 남은 시간. 필터 부서·경고·우선순위 | alerts |
| N-06-04 | 개요 | ② 부서별 미해결 표: 부서, NEW, IN_PROGRESS, WAITING_CUSTOMER, ESCALATED, 합계 | summary 부서별 |
| N-06-05 | 개요 | ③ SLA 상태별 건수: 1차 응답(MET, BREACHED, ON_TRACK), 해결(MET, BREACHED, ON_TRACK, AT_RISK, N/A) + 종료 포함 스위치 + "SLA 미정 n건" | summary SLA별, sla_unset |
| N-06-06 | 개요 | ④ 주간 품질 추이: FR-044 결과가 없으면 "아직 집계 없음" | quality-trend |
| N-06-07 | AI·규칙 품질 | 기간(기본 최근 7일): 만든 초안, 보낸 글, 고쳐 보낸 비율, "그래도 발송" 수, 자체 검사 종류별 걸린 수 | ai (drafts, sent, edited_rate, overrides, checks) |
| N-06-08 | 제품별 통계 | 제품군 > 제품: 문의 수, 미해결, 경고. 제품 모름은 "제품 미상" 한 줄 | products |
| N-06-09 | 고객별 통계 | 등급별, 나라별: 문의 수, 미해결, 경고 | customers |

## 화면 상태

- 로딩: 타일 회색 자리, 표 스켈레톤.
- 위험·위반 없음: "SLA 위험·위반 문의가 없습니다"(FR-034 예외 1행).
- 품질 추이 없음: ④ 영역만 "아직 집계 없음", 나머지는 정상(AC-034-6).
- 오류: 이전 값을 두고 "대시보드를 불러오지 못함. 새로고침"(FR-034 예외 3행).
- 자동 갱신: 5분마다.

## 사용자 동작 → 시스템 반응

| 동작 | 호출 API | 성공 시 | 실패 시 |
|---|---|---|---|
| 화면 열기(개요) | `GET /dashboard/alerts`, `/summary`, `/quality-trend` | 네 영역 그림 | 영역별로 오류 띠, 다른 영역은 정상 |
| 목록 필터 바꾸기 | `GET /dashboard/alerts?dept=&alert=&priority=` | 목록만 다시 그림 | 이전 목록 유지 + 오류 띠 |
| 종료 포함 스위치 | `GET /dashboard/summary?include_closed=true` | ③ 다시 그림 | 같음 |
| 탭 AI·규칙 품질 | `GET /dashboard/ai?from=&to=` | 숫자 그림 | 같음 |
| 탭 제품별 / 고객별 | `GET /dashboard/products` / `/dashboard/customers` | 표 그림 | 같음 |
| 위험·위반 행 누르기 | — | 티켓 상세(SCR-03) | — |
| 제품·고객 행 누르기 | — | 제품이면 제품 상세(SCR-08), 고객 등급·나라면 고객 목록(SCR-07)을 그 값으로 거른 화면 | (아래 "목업과 다른 곳" 3행, 정할 것 Q10) |

## 입력 검증

- AI 탭 기간: from ≤ to, 미래 날짜 거부(구현 선택).

## 수용 기준 (Given / When / Then)

- SCR-06-AC-1 (AC-034-1): Given 미해결 360건 재생 + 스냅샷, When 개요를 열면, Then 위험·위반 목록에 해결 AT_RISK 34건과 BREACHED 140건이 모두 있다.
- SCR-06-AC-2 (AC-034-2): Given 같은 상태, When 부서별 미해결 표를 보면, Then TS_LV 67, WARRANTY_DESK 60, TS_AUTO 52, SCM 52, GCS_L1 35, TS_ENERGY 26, CERT 26, SALES_OPS 21, TS_MV 10, FIELD_SVC 6, TS_TRF 5다.
- SCR-06-AC-3 (AC-034-3): Given 우선순위 조정으로 경고가 새로 생긴 문의, When 다음 갱신 뒤 보면, Then 목록에 나타난다.
- SCR-06-AC-4 (AC-034-4): Given 목록의 한 행, When 누르면, Then 그 티켓 상세가 열린다.
- SCR-06-AC-5 (AC-034-6): Given 품질 추이 결과 없음, When 개요를 열면, Then ④에 "아직 집계 없음"이 보이고 나머지는 정상이다.
- SCR-06-AC-6 (FR-초안-05 AC 초안): Given 같은 360건 상태, When 제품별 통계를 보면, Then 미해결 합이 360이다.

## 목업과 다른 곳

| 목업 | 명세 | 이유 |
|---|---|---|
| 고정 숫자 타일(기한 준수율 91.4 %, 평균 1차 회신 2.6시간, 처리율 14일) | 넣지 않음 | API 없음, 지어낸 숫자(정할 것 Q9) |
| "부서별 통계" 탭 | 개요의 부서별 미해결 표로 대신 | add-dashboard-tabs는 탭 4개(개요, AI, 제품, 고객) |
| 제품·고객 행 → 접수함 거르기(add-dashboard-tabs 결정 3도 같음) | 제품 상세(SCR-08) / 고객 목록(SCR-07)으로 보냄 | `GET /tickets`에 제품·고객 필터가 없음(정할 것 Q10) |
| AI 탭의 "AI 자동 처리" | 넣지 않음 | CLAUDE.md 규칙 3 |
