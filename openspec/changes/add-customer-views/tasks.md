# Tasks: 고객 관리 화면

## 1. 서버

- [x] 1.1 `app/db/customers.py` 집계 쿼리 (design 결정 1~3)
- [x] 1.2 `GET /customers`, `/customers/{id}`, `/customers/countries`와 응답 모델 (design 결정 1~3)

## 2. 화면

- [ ] 2.1 고객 관리 목록·상세·나라별 표 (design 결정 3)
- [x] 2.2 `jobs/export_openapi.py`, `npm run gen:api` (변경 add-api-response-models 결정 4)

## 3. 시험

- [x] 3.1 `tests/acceptance/test_customer_views.py` (design 결정 4)
- [ ] 3.2 `pytest` 전체 실행, `npm run build`
