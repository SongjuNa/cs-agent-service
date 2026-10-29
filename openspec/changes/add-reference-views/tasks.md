# Tasks: 기준정보 보기 화면

## 1. 서버

- [x] 1.1 `GET /ref/documents`, `/ref/documents/{doc_id}` (design 결정 1)
- [x] 1.2 `GET /ref/products` 열 더하기, `/ref/products/{product_code}` (design 결정 2)
- [x] 1.3 `GET /ref/rules/{kind}` (design 결정 3)

## 2. 화면

- [x] 2.1 문서 관리·제품 관리·규칙 보기, 「왜?」 연결 (design 결정 4)
- [x] 2.2 `jobs/export_openapi.py`, `npm run gen:api` (변경 add-api-response-models 결정 4)

## 3. 시험

- [x] 3.1 `tests/acceptance/test_reference_views.py` (design 결정 4)
- [x] 3.2 `pytest` 전체 실행, `npm run build`
