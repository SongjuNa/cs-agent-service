# Tasks: 접수함 줄·건수 값 추가

- [x] 1.1 `db/inbox.py`: 줄에 `country`, `inquiry_subject`, counts에 `new`, `escalated`, `breach`, `risk`
- [x] 1.2 `api/schemas.py`: `InboxRow`, `InboxCounts`
- [x] 1.3 `jobs/export_openapi.py`, `npm run gen:api`
- [x] 2.1 시험 `test_inbox.py::test_counts_new_escalated_breach_risk`, 계약 시험
- [x] 3.1 접수함 화면: 문의 제목 칸, 국가, 새 문의 칩, 회신 대기·이관 요약, 부제의 기한 초과·임박 (SCR-02)
- [x] 3.2 화면 시험, `npm run build`
- [ ] 4.1 팀 확인: 한국어 요약 한 줄을 만들지(새 열 필요, 규칙 4)
