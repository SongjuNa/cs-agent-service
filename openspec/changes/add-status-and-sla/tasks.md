# Tasks: 상태 관리와 SLA 두 시계

## 1. 상태

- [x] 1.1 `app/status/transitions.py` 전이 함수·거부·동시 수정 (design 결정 1)
- [x] 1.2 처리 끝 PIPELINE_DONE, 발송 뒤 전이 (design 결정 2)
- [x] 1.3 `app/status/closing.py` 자동 종료 점검 (design 결정 3)

## 2. SLA와 상세

- [x] 2.1 `app/sla/clock.py` (design 결정 4)
- [x] 2.2 `GET /tickets/{id}`에 상태·SLA·이력 (design 결정 5)

## 3. 채점

- [x] 3.1 `jobs/replay_gold.py` scoring 재생 (design 결정 6)

## 4. 시험

- [x] 4.1 `tests/acceptance/test_status_sla.py`, 1순위 시험 기대값 고침 (design 결정 7)
- [x] 4.2 `pytest` 전체 실행
