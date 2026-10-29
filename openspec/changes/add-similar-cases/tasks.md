# Tasks: 유사 해결사례 검색

## 0. 사람 확인 (구현 전)

- [x] 0.1 해결사례 보관: 파일 캐시(고장 사전 방식)로 결정(2026-10-29 조장). 기술 명세서 §4-7 "ref에 둔다"와 다른 점은 문서 갱신 때 반영

## 1. 서버

- [ ] 1.1 `jobs/build_case_index.py` (design 결정 1)
- [ ] 1.2 `app/retrieval/cases.py` 검색, 벡터 캐시 (design 결정 1·2)
- [ ] 1.3 Q8b 노드, 실행 기록, 다시 처리 (design 결정 3)
- [ ] 1.4 상세 응답 similar_cases, 응답 모델 (design 결정 4)

## 2. 화면

- [ ] 2.1 "비슷한 해결사례" 구역 (design 결정 4)
- [ ] 2.2 `jobs/export_openapi.py`, `npm run gen:api` (변경 add-api-response-models 결정 4)

## 3. 시험

- [ ] 3.1 `tests/acceptance/test_similar_cases.py` (design 결정 5)
- [ ] 3.2 `pytest` 전체 실행, `npm run build`
