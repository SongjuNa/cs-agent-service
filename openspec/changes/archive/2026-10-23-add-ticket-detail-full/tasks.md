# Tasks: 티켓 상세 전체판

## 1. 서버

- [x] 1.1 상세 묶음 더하기(원문·연락처·추출 값·상담원 수정·다시 처리 가능) (design 결정 1)
- [x] 1.2 `GET /tickets/{id}/timeline` (design 결정 2)
- [x] 1.3 `PATCH /sub-tickets/{id}`와 규칙 단계부터 다시 돌기(AGENT_EDIT) (design 결정 3)
- [x] 1.4 다시 처리를 실패가 아닌 티켓에도, 이전 초안 superseded (design 결정 4)

## 2. 화면

- [x] 2.1 탭 4개, 머리·[목록으로]·[다시 처리], 하위 문의 구역, 수정·조정·회신 입력 팝업, 이력 (design 결정 5)

## 3. 시험

- [x] 3.1 `tests/acceptance/test_ticket_detail_full.py` (design 결정 6)
- [x] 3.2 `pytest` 전체 실행, `npm run build`
