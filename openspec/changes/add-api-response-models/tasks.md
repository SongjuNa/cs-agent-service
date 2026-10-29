# Tasks: API 응답 모양을 계약에 적기

## 1. 서버

- [x] 1.1 `backend/app/api/schemas.py` 응답 모델 (design 결정 1~3)
- [x] 1.2 라우터 9개에 `response_model` (design 결정 1)
- [x] 1.3 `jobs/export_openapi.py` 계약 뽑기 (design 결정 4)

## 2. 화면

- [x] 2.1 `frontend/openapi.json`, `npm run gen:api`, `api.gen.ts` (design 결정 4)
- [x] 2.2 `api.ts` 응답 타입을 생성 타입 별칭으로 (design 결정 4)

## 3. 시험

- [x] 3.1 `tests/acceptance/test_api_contract.py` (design 결정 5)
- [ ] 3.2 `pytest` 전체(DB 필요), `npm run build` — build 통과, 계약 시험 3개 통과, DB 시험은 아직
