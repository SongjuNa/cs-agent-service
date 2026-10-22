# Tasks: 근거 문서 검색과 숫자 조회

## 1. 준비

- [x] 1.1 `.env.example`과 `app/config.py`에 `EMBEDDING_MODEL=gemini-embedding-2`를 더한다
- [x] 1.2 `jobs/load_reference.py`가 ref.doc_chunk를 먼저 비우게 한다

## 2. 색인 (W2)

- [x] 2.1 `app/retrieval/chunking.py` (design 결정 1)
- [x] 2.2 `app/llm/embed.py` (design 결정 2). 확인: 실패하면 1회 다시 부른다
- [x] 2.3 `jobs/build_doc_index.py` (design 결정 3). 확인: 정답 절이 모두 청크로 있다

## 3. 검색과 조회

- [x] 3.1 `app/retrieval/search.py` (FR-016, design 결정 4)
- [x] 3.2 `app/retrieval/numbers.py` (FR-017, design 결정 5)
- [x] 3.3 `app/pipeline/evidence.py` (design 결정 6)

## 4. 시험

- [x] 4.1 `backend/tests/acceptance/test_evidence_lookup.py`에 W2 확인 2개, AC-016-1~3, AC-017-1~3 시험을 만든다
- [x] 4.2 `pytest`를 실행해 앞 변경 시험과 이번 시험이 모두 통과하는지 확인한다

## Workflow follow-up

- 시험이 통과하면 PR을 만들고 병합한 뒤 archive한다(조장 진행 방식, 개발_결정_기록 머리말).
