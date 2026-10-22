# Tasks: 초안 만들기

## 1. 준비

- [x] 1.1 `backend/pyproject.toml`에 `langgraph`, `openspec/config.yaml` 규칙 두 줄 따옴표
- [x] 1.2 `prompts/` 지시문 4개(design 결정 3·4·6). 확인: 에이전트 설계서 4-5·4-6·4-9절과 글이 같다(주석을 빼고, L4는 `<customer_message>` 태그와 데이터 안내 한 줄만 다름)

## 2. 초안과 대조

- [x] 2.1 `app/checks/draft_check.py` (design 결정 5)
- [x] 2.2 `app/llm/drafts.py` L3·L4·L7 (design 결정 2·3·4·6)

## 3. 그래프

- [x] 3.1 `app/pipeline/rules_step.py`, `app/pipeline/graph.py` (design 결정 1)

## 4. 시험

- [x] 4.1 `backend/tests/acceptance/test_drafts.py`에 AC-015-1~3, AC-021-1~3, AC-017-5, AC-038-4, AC-039-1·3, 길이 초과·날짜 대조 시험
- [x] 4.2 `pytest`

## Workflow follow-up

- 시험이 통과하면 PR을 만들고 병합한 뒤 archive한다(조장 진행 방식, 개발_결정_기록 머리말).
