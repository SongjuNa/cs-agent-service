# Tasks: 기준정보·정답지 적재

## 1. 준비

- [x] 1.1 `.env.example`에 `DATA_DIR`를 추가하고, `app.config`가 이 값을 읽게 한다. 확인: 값이 없을 때 기본값 `data/CS_AI_Agent_Training_Data_v1`이 쓰인다

## 2. 기준정보 적재 (W1)

- [x] 2.1 `jobs/load_reference.py`를 만든다(design 결정 3·4). 확인: 빈 DB에서 실행하면 오류 없이 끝난다
- [x] 2.2 `backend/tests/test_data_load.py`에 W1-1, W1-2, W1-3, W1-4 시험을 만든다. 확인: 네 시험이 통과한다

## 3. 정답지 적재 (W3)

- [x] 3.1 `jobs/load_gold.py`를 만든다(design 결정 5). 확인: 빈 gold에서 실행하면 오류 없이 끝난다
- [x] 3.2 같은 시험 파일에 W3-1, W3-2 시험을 만든다. 확인: 두 시험이 통과한다

## 4. 안내

- [x] 4.1 README에 데이터 위치와 적재 명령을 추가한다. 확인: 빈 DB(`docker compose down -v` 후)에서 README 순서대로 실행해 본 명령만 적혀 있다

## 5. 시험

- [x] 5.1 `pytest`를 실행해 뼈대 시험(W7-1, W7-2)과 이번 시험(W1-1~W1-4, W3-1~W3-2)이 모두 통과하는지 확인한다

## Workflow follow-up

- 시험이 통과하면 브랜치 `feat/load-reference-and-gold`를 올리고 PR을 만든다(조장 결정 2026-10-22: 승인은 propose에서만).
- PR 병합 뒤 `/opsx:archive`.
