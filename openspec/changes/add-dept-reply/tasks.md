# Tasks: 부서 회신과 예외 부서 메일

## 1. 서버

- [x] 1.1 회신 등록·예외 부서 메일 검사 `app/status/dept_reply.py` (design 결정 1·3)
- [x] 1.2 회신 뒤 다시 처리: 첫 노드, 답변 경로, L4 v3, Q11·L8 부서 회신 (design 결정 2)
- [x] 1.3 `POST /sub-tickets/{id}/dept-reply`, `POST /sub-tickets/{id}/dept-mail`, 발송·임시 저장의 DEPT 초안 (design 결정 1·3)
- [x] 1.4 상세 응답 dept_replies·dept_mails·writer (design 결정 4)

## 2. 화면

- [x] 2.1 "보낼 것" 탭의 부서별 작성 영역, "부서 회신" 영역, 이력 탭 자리 표시 떼기 (design 결정 4)

## 3. 시험

- [x] 3.1 `tests/acceptance/test_dept_reply.py` (design 결정 5)
- [x] 3.2 `pytest` 전체 실행, `npm run build`
