# Tasks: 티켓 상세 최소판

## 1. 저장

- [x] 1.1 `app/db/store.py` 접수 저장·결과 저장 (design 결정 1·2)
- [x] 1.2 `app/pipeline/graph.py`가 저장에 필요한 값(required_info, 단계 결과)을 남김

## 2. API

- [x] 2.1 `app/db/detail.py` 상세 묶음·검토 표시 (design 결정 3·4)
- [x] 2.2 `app/api/deps.py`, `tickets.py`, `chunks.py`, `messages.py`, `main.py` (design 결정 5·6)
- [x] 2.3 `jobs/run_tickets.py` (design 결정 8)

## 3. 화면

- [x] 3.1 `frontend/` Vite + React + TS, SCR-03M과 팝업 4개 (design 결정 7)

## 4. 시험

- [x] 4.1 `backend/tests/acceptance/test_ticket_detail.py` (design 결정 9)
- [x] 4.2 `pytest`, `npm run build`, 화면 확인

## Workflow follow-up

- 시험이 통과하면 PR을 만들고 병합한 뒤 archive한다(조장 진행 방식, 개발_결정_기록 머리말).
