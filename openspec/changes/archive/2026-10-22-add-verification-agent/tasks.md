# Tasks: 검증 에이전트

## 1. 준비

- [x] 1.1 `prompts/l8_verify_v1.md` (design 결정 1). 확인: 에이전트 설계서 4-10절과 글이 같다(`<customer_request>` 세 곳을 `<customer_message>`로, 자리표시 두 개 이름 줄임만 다름)

## 2. 검증

- [x] 2.1 `app/llm/verify.py` `verify_draft`, `VerifyResult`(passed_yn, by_kind, state, mark) (design 결정 2·3·4)
- [x] 2.2 `app/llm/drafts.py` 초안 객체에 verify 칸, `app/pipeline/graph.py` verify 노드 (design 결정 5)

## 3. 시험

- [x] 3.1 `backend/tests/acceptance/test_verification.py`에 AC-049-1·4·5·6, 지어낸 quote, 대역 없음 시험
- [x] 3.2 `pytest`

## Workflow follow-up

- 시험이 통과하면 PR을 만들고 병합한 뒤 archive한다(조장 진행 방식, 개발_결정_기록 머리말).
