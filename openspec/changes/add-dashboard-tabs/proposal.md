# Proposal: 운영 대시보드 AI·제품·고객 탭 (add-dashboard-tabs)

## Why

목업(ONCE v1.41)의 운영 대시보드에는 개요 말고도 AI·제품·고객 탭이 있다. 이 탭들은 FR-034 처리에 없어서, FR 초안 05로 적었고 조장이 승인했다(근거: 목업 기능 FR 초안 문서 "정하실 것 1 → 승인", 2026-10-29, 저장소 밖, FR-034 처리 1~6). 모두 이미 있는 표를 세기만 한다(근거: FR-034 처리 4 "새로 계산하지 않는다"와 같은 원칙).

## What Changes

- **AI 탭 `GET /dashboard/ai`**: 기간 안의 초안 수, 승인·발송된 초안 수, 고쳐서 보낸 비율(발송 행 edited_yn), "그래도 발송"(override_check) 수, 자체 검사 종류별(check_type) 걸린 수를 낸다(근거: 테이블 정의서 v1.3 svc.ticket_message edited_yn·override_check, eval.self_check check_type·passed_yn).
- **제품 탭 `GET /dashboard/products`**: 제품군·제품별 문의 수, 미해결 수, 살아 있는 경고 수를 낸다(근거: 테이블 정의서 v1.3 svc.sub_ticket product_code, ref.product family, svc.sla_alert).
- **고객 탭 `GET /dashboard/customers`**: 등급별·나라별 문의 수, 미해결 수, 살아 있는 경고 수를 낸다(근거: 테이블 정의서 v1.3 ref.customer tier·country).
- **"AI 자동 처리" 넣지 않음**: 목업 AI 탭의 "승인 없이 보냈습니다"는 CLAUDE.md 규칙 3과 D32에 어긋나므로 만들지 않는다(근거: CLAUDE.md 규칙 3, 명세서 v1.5 D32).
- **화면**: 운영 대시보드에 탭 3개를 더한다. 화면은 별도 메뉴인 운영 대시보드에 둔다(근거: 변경 add-ops-dashboard tasks 0.1, 조장 결정 2026-10-29).

## Capabilities

### New Capabilities
- `dashboard-tabs`: 운영 대시보드의 AI·제품·고객 집계.

## 범위 밖

- **AI 품질 점수(채점)**: 정답과 비교한 점수는 평가 러너·주간 추이(FR-042·FR-044)의 일이다. 이 탭은 서비스 기록만 센다(근거: CLAUDE.md 규칙 6, FR-044, openspec/config.yaml).

## Impact

- 새 파일: 시험 `backend/tests/acceptance/test_dashboard_tabs.py`(근거: design 결정 4).
- 고치는 파일: `app/db/dashboard.py`·`app/api/dashboard.py`(add-ops-dashboard가 만든 파일), `app/api/schemas.py`, 화면 `OpsDashboardPage.tsx`·`api.ts`·`api.gen.ts`·`openapi.json`(근거: design 결정 1~3).
- DB 구조는 고치지 않는다(근거: CLAUDE.md 규칙 4).
