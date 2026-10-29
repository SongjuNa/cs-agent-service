# Tasks: 해결사례 직접 검색

## 0. 앞선 변경

- [x] 0.1 add-similar-cases 구현(색인)

## 1. 서버

- [x] 1.1 색인 열 늘리기 (design 결정 2)
- [x] 1.2 `GET /cases`, `/cases/{case_id}`와 응답 모델 (design 결정 1·2)

## 2. 화면

- [x] 2.1 접수 이력 검색 화면 (design 결정 3)
- [x] 2.2 `jobs/export_openapi.py`, `npm run gen:api` (변경 add-api-response-models 결정 4)

## 3. 시험

- [x] 3.1 `tests/acceptance/test_case_search.py` (design 결정 3)
- [x] 3.2 `pytest` 전체 실행, `npm run build`
