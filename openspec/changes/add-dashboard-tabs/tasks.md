# Tasks: 운영 대시보드 AI·제품·고객 탭

## 0. 앞선 변경

- [ ] 0.1 add-ops-dashboard 구현과 화면 위치 결정 (proposal 화면)

## 1. 서버

- [ ] 1.1 `GET /dashboard/ai` (design 결정 1)
- [ ] 1.2 `GET /dashboard/products`, `/dashboard/customers` (design 결정 2)

## 2. 화면

- [ ] 2.1 AI·제품·고객 탭 (design 결정 3)
- [ ] 2.2 `jobs/export_openapi.py`, `npm run gen:api` (변경 add-api-response-models 결정 4)

## 3. 시험

- [ ] 3.1 `tests/acceptance/test_dashboard_tabs.py` (design 결정 4)
- [ ] 3.2 `pytest` 전체 실행, `npm run build`
