# Tasks: 문의 이해

## 1. 준비

- [x] 1.1 `backend/pyproject.toml`에 `google-genai`, `.env.example`에 `LLM_MODEL_SMALL=gemini-3.8-flash`, `app/config.py`에 같은 설정을 더한다
- [x] 1.2 `prompts/` 지시문 4개를 만든다(design 결정 2). 확인: 에이전트 설계서 4-3·4-4절 초안과 글이 같고, 기준서 1-1·2장과는 design 결정 2에 적은 차이(GS 번호, K4 문장)만 있다

## 2. 언어 모델 호출 계층

- [x] 2.1 `app/llm/client.py` (design 결정 1). 확인: 스키마 밖 응답이나 시간 초과면 1회 다시 부른다

## 3. L1·L2와 검사

- [x] 3.1 `app/llm/understand.py` (FR-004·005·007, design 결정 3)
- [x] 3.2 `app/llm/extract.py` (FR-008, design 결정 4)

## 4. 처리 흐름 앞부분

- [x] 4.1 `app/pipeline/state.py`, `app/pipeline/understand.py` (design 결정 5)

## 5. 시험

- [x] 5.1 `backend/tests/acceptance/test_inquiry_understanding.py`에 AC-004-1~3, AC-005-1~3, AC-007-1~3, AC-008-1~4 시험을 만든다
- [x] 5.2 `pytest`를 실행해 앞 변경 시험과 이번 시험이 모두 통과하는지 확인한다(키가 없으면 언어 모델 시험은 건너뜀으로 보고). 결과: 52 통과, 18 건너뜀(키 없음)

## Workflow follow-up

- 시험이 통과하면 PR을 만들고 병합한 뒤 archive한다(조장 진행 방식, 개발_결정_기록 머리말).
