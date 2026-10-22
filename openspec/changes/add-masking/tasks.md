# Tasks: 개인정보 가리기

## 1. 가리는 함수

- [ ] 1.1 `backend/app/masking/mask.py`에 `mask_text`, `mask_fields`, `MaskingError`를 만든다(design 결정 1~3). 확인: AC-038-1·2·4·6 문장을 넣으면 design 결정 3의 값이 나온다
- [ ] 1.2 `backend/app/masking/__init__.py`에서 세 이름을 내보낸다. 확인: `from app.masking import mask_text`가 된다

## 2. LLM 입력 입구

- [ ] 2.1 `backend/app/llm/inputs.py`에 `CONTACT_FIELDS`, `LlmInput`, `prepare_llm_input`을 만든다(design 결정 4). 확인: 연락처 항목이 있으면 `MaskingError(kind="VALIDATION")`가 난다

## 3. 시험

- [ ] 3.1 `backend/tests/acceptance/test_masking.py`에 AC-038-1, 2, 3, 4, 5, 6 시험과 예외 보조 시험을 만든다(design 결정 5). 확인: 시험 이름에 AC 번호가 들어 있다
- [ ] 3.2 `pytest`를 실행해 앞 변경의 시험(W7, W1, W3)과 이번 시험이 모두 통과하는지 확인한다

## Workflow follow-up

- 시험이 통과하면 브랜치를 올리고 PR을 만든다(진행 방식은 기준 문서가 아니라 조장 지시 2026-10-22: 승인은 propose에서만, main 병합은 팀 승인 뒤 조장이 한다(CLAUDE.md 작업 방식)).
- PR 병합 뒤 `/opsx:archive`.
