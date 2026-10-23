# Tasks: 처리 실행 로그

## 1. 기록

- [x] 1.1 `app/pipeline/runlog.py`, `app/llm/client.py` 호출 알림 (design 결정 1)
- [x] 1.2 `app/db/store.py` 단계 열과 실패 견딤, `graph.py` 노드 감싸기 (design 결정 1·2)
- [x] 1.3 `app/db/runs.py`, 시작 때 닫기, 매일 보존 (design 결정 3·5)
- [x] 1.4 조회 API, "왜?" 단계, 시작 사유, 대역·검증 API 사용량 (design 결정 4)

## 2. 시험

- [x] 2.1 `tests/acceptance/test_run_log.py` (design 결정 6)
- [x] 2.2 `pytest` 전체 실행
