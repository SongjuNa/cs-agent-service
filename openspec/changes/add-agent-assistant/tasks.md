# Tasks: 상담원 도우미 (근거 기반 질의응답)

## 0. 시작 전

- [ ] 0.1 조장 승인(새 범위, 2026-10-29 결정과 다름). 승인 근거를 proposal에 적는다
- [ ] 0.2 `근거_점검표.md`의 "확인 필요" 항목을 채운다(호출 번호 L11, 가짜 transport, 숫자 검사 재사용, 기준 점수)
- [ ] 0.3 FR 번호를 정한다(임시: FR-초안-07). 요구사항 명세서에 올릴지 정한다

## 1. 서버

- [x] 1.1 `retrieval/docs_free.py`: 범위 제한 없는 문서 검색 (design 결정 2) (코드 작성, 시험 전)
- [x] 1.2 `prompts/l11_assist_v2.md` (design 결정 3) (코드 작성, 시험 전)
- [x] 1.3 `llm/assist.py`: `generate_json` 호출, 출처 번호 코드 검사, 실패 대체 (design 결정 3) (코드 작성, 시험 전)
- [x] 1.4 `api/assist.py`: `POST /assist/ask`, 입력 검증, 응답 모델 (design 결정 1) (코드 작성, 시험 전)
- [x] 1.5 `main.py` 라우터 등록, `api/schemas.py` 응답 모델 (코드 작성, 시험 전)

## 2. 화면

- [x] 2.1 `docs/frontend/screens/SCR-10-assistant.md` 작성, `SCR-00` 한 줄 추가 (design 결정 4)
- [x] 2.2 `jobs/export_openapi.py`, `npm run gen:api`로 `api.gen.ts` 갱신 (변경 add-api-response-models 결정 4)
- [x] 2.3 `features/assistant/`: 창, 말풍선, 출처 칩, 추천 질문 (design 결정 4)
- [x] 2.4 `AppShell.tsx`에 떠 있는 버튼 연결, 출처 칩 → P2 팝업

## 3. 시험

- [x] 3.1 `tests/acceptance/test_agent_assistant.py` 8개 작성, 8개 통과(시험용 DB) (design 결정 5)
- [x] 3.2 화면 시험 `frontend/e2e/scr-10.spec.ts` 7개 통과(모델 호출·절 본문은 목, Gemini 호출 없음)
- [x] 3.3 `npm run build` 통과, `pytest` 전체 실행(370개 통과). 실패 4개 중 계약 개수 시험은 36→37로 고침. 나머지 3개(계약 복사본 일치 1, 실제 Gemini를 부르는 시험 2)는 재실행으로 확인 필요

## 4. 검증

- [ ] 4.1 실제 문서로 질문 10개를 넣어 보고, 근거 없는 질문에서 지어내지 않는지 확인한다
- [ ] 4.2 한국어 질문의 검색 품질을 확인하고 낮으면 보고한다 (design Risks)
