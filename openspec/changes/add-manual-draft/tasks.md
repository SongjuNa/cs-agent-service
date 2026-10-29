# Tasks: 근거 없을 때 상담원이 직접 쓰는 초안

## 0. 사람 확인 (구현 전)

- [ ] 0.1 새 주소 `POST /sub-tickets/{id}/drafts`를 기술 명세서 §8-1에 더할지 (proposal What Changes)
- [ ] 0.2 제안 AC-030-6·7을 명세서 FR-030에 넣을지 (design 결정 5)
- [ ] 0.3 직접 쓴 초안에 [다시 검증] 버튼을 열지 (proposal 범위 밖)
- [ ] 0.4 직접 쓴 초안에도 대역을 만들지: FR-039 기능 설명과 화면 정의서 v2 R-05·기술 명세서 §8-1이 다름 (design 결정 3)
- [ ] 0.5 예외 부서 메일 임시 저장의 mask_count UPDATE와 schema.sql 트리거 차이 (design Risks)

## 1. 서버

- [ ] 1.1 `POST /sub-tickets/{id}/drafts`와 응답 모델 (design 결정 1)
- [ ] 1.2 load_draft·상세 drafts에 sender AGENT 초안 (design 결정 2)
- [ ] 1.3 AGENT 초안에서 검증 에이전트 건너뛰기 (design 결정 3)

## 2. 화면

- [ ] 2.1 초안 없는 종류의 빈 편집기, "상담원 작성" 칩 (design 결정 4)
- [ ] 2.2 `jobs/export_openapi.py`, `npm run gen:api` (변경 add-api-response-models 결정 4)

## 3. 시험

- [ ] 3.1 `tests/acceptance/test_manual_draft.py` (design 결정 5)
- [ ] 3.2 `pytest` 전체 실행, `npm run build`
