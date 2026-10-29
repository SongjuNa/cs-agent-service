# Proposal: 운영 대시보드 (add-ops-dashboard)

## Why

관리자(C/S 팀장)가 전체 부서의 SLA 위험 현황을 한 화면에서 본다. 접수함이 "내 부서의 처리 순서", 나의 업무 현황이 "내가 손댈 것"이라면, 이 화면은 "전체 부서의 위험 현황"이다(근거: 명세서 v1.5 FR-034 기능 설명). FR-034는 여유 시 1순위이며, 2026-10-29 조장 결정으로 지금 만든다(근거: CLAUDE.md "여유 시 기능은 FR-019 … FR-034 운영 대시보드만 만들고", openspec/config.yaml, D31).

## What Changes

- **위험·위반 목록 `GET /dashboard/alerts`**: 해제되지 않은 경고(RES_AT_RISK, RES_BREACHED, FR_AT_RISK, FR_BREACHED)가 있는 미해결 하위 문의를 부서 구분 없이 모은다. 열은 문의 번호(복합이면 순번), 담당 부서, 우선순위, 상태, 경고 종류, 남은 시간이고, 남은 시간 오름차순으로 놓는다. 필터는 부서, 경고 종류, 우선순위다(근거: FR-034 처리 1·입력, 기술 명세서 v1.4 §8-1 dashboard 행 "alerts는 /me/workload의 위험 목록과 같은 쿼리에서 담당 조건만 뺀 것").
- **집계 `GET /dashboard/summary`**: 부서별 미해결 건수(NEW, IN_PROGRESS, WAITING_CUSTOMER, ESCALATED)와 SLA 상태별 건수(1차 응답 MET·BREACHED·ON_TRACK, 해결 MET·BREACHED·ON_TRACK·AT_RISK·N/A)를 낸다. 기본은 미해결만이고, include_closed로 전체를 본다. SLA 미정 문의는 목록에서 빼고 건수만 따로 낸다(근거: FR-034 처리 2·3, 예외 2행, §8-1).
- **숫자는 세기만 한다**: FR-026·027이 낸 값만 세고, 새로 계산하지 않는다(근거: FR-034 처리 4).
- **주간 품질 추이 `GET /dashboard/quality-trend`**: FR-044가 아직 없으므로 늘 빈 목록을 돌려주고, 화면은 "아직 집계 없음"을 보인다(근거: FR-034 처리 6, AC-034-6, 의존성 "FR-044 구현 전에는 아직 집계 없음").
- **화면**: 목업(ONCE v1.41)의 관리자 › 운영 대시보드 "개요" 탭에 위 세 영역을 둔다. 목록 행을 누르면 티켓 상세로 간다. 갱신은 주기 점검(5분)과 같은 간격이다(근거: FR-034 처리 5, 기술 명세서 §6-4 5분 주기, AC-034-4. 화면 위치는 화면 정의서 v1 "SCR-04에 전체 보기 스위치"와 달라 조장 확인).
- **읽기 실패**: 이전 값을 그대로 두고 "대시보드를 불러오지 못함. 새로고침"을 보인다(근거: FR-034 예외 3행).

## Capabilities

### New Capabilities
- `ops-dashboard`: 전 부서 위험·위반 목록, 부서별 미해결 건수, SLA 상태별 건수, 주간 품질 추이 자리.

## 범위 밖

- **주간 품질 추이의 실제 값과 [내려받기]**: FR-044(여유 시)가 결과를 만들어야 한다. AC-034-5는 FR-044와 함께 만든다(근거: FR-034 의존성, openspec/config.yaml "그 밖의 여유 시 기능은 만들지 않는다").
- **목업의 AI·제품·부서·고객 탭**: FR-034 처리에 없다. FR 초안으로 따로 묻는다(근거: FR-034 처리 1~6, 새 기능 19개 FR 대조표 2026-10-29, 저장소 밖).

## Impact

- 새 파일: `backend/app/db/dashboard.py`(집계 쿼리), `backend/app/api/dashboard.py`(주소 3개), 화면 `frontend/src/OpsDashboardPage.tsx`, 시험 `backend/tests/acceptance/test_ops_dashboard.py`(근거: design 결정 1~5).
- 고치는 파일: `app/main.py`(라우터 등록), `app/db/workload.py`(위험 목록 쿼리를 함께 쓰도록 나눔), `app/api/schemas.py`(응답 모델), 화면 `App.tsx`(메뉴)·`api.ts`·`api.gen.ts`·`openapi.json`(근거: design 결정 1~4).
- DB 구조는 고치지 않는다. 읽는 값은 sla_alert, inquiry_sla(as_of), sub_ticket에 이미 있다(근거: CLAUDE.md 규칙 4, schema.sql).
