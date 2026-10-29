# Tasks: 운영 대시보드

## 0. 사람 확인 (구현 전)

- [x] 0.1 화면 위치: 목업처럼 별도 메뉴(관리자 › 운영 대시보드)로 결정(2026-10-29 조장). 화면 정의서 v1과 다른 점은 문서 갱신 때 반영 (design 결정 4)

## 1. 서버

- [ ] 1.1 위험 목록 쿼리 나누기, `app/db/dashboard.py` (design 결정 1·2)
- [ ] 1.2 `GET /dashboard/alerts`, `/summary`, `/quality-trend`와 응답 모델 (design 결정 1~3)

## 2. 화면

- [ ] 2.1 `OpsDashboardPage.tsx`, 메뉴 (design 결정 4)
- [ ] 2.2 `jobs/export_openapi.py`, `npm run gen:api` (변경 add-api-response-models 결정 4)

## 3. 시험

- [ ] 3.1 `tests/acceptance/test_ops_dashboard.py` (design 결정 5)
- [ ] 3.2 `pytest` 전체 실행, `npm run build`
