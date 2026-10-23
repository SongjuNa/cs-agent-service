# Tasks: 고객 회신 입력과 메시지 이력

## 1. 회신

- [x] 1.1 `app/db/replies.py` 회신 저장·전이 (design 결정 1)
- [x] 1.2 `app/pipeline/reprocess.py`, graph.py 첫 노드 바꿔 끼우기 (design 결정 2)
- [x] 1.3 store.py 회신 결과 저장 (design 결정 3)

## 2. API

- [x] 2.1 `POST /tickets/{id}/replies` (design 결정 5)
- [x] 2.2 상세 API 메시지 이력·재요청·재문의 (design 결정 4)

## 3. 시험

- [x] 3.1 `tests/acceptance/test_customer_reply.py` (design 결정 6)
- [x] 3.2 `pytest` 전체 실행
