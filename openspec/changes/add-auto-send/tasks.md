# Tasks: 자동 발송

## 1. 서버 (PR 1)
- [ ] 1.1 새 표 `auto_setting`·`auto_review`, `ticket_message` CHECK 변경(schema.sql, table-specification, D32 문구)
- [ ] 1.2 `rules/autosend.py` 판정(순수 함수) + 단위 시험
- [ ] 1.3 `status/autosend.py` 실행(`auto=True` 발송)·사후 검수, 처리 끝 연결
- [ ] 1.4 `GET·PUT /auto-rules`, `POST /sub-tickets/{id}/auto-review`, 계약 재생성
- [ ] 1.5 서버 시험(판정·실행·꺼짐·검수·설정)
- [ ] 1.6 자동 처리 규칙 화면 SCR-12

## 2. 화면 (PR 2, add-auto-send-views)
- [ ] 2.1 접수함 `auto` 필터·`auto_state`·"자동 처리" 탭, turn·next_action `REVIEW_AUTO`
- [ ] 2.2 상세: 자동 발송 표시·[사후 검수 완료]
- [ ] 2.3 나의 업무 현황 "AI 자동 처리" 카드
- [ ] 2.4 운영 대시보드 "AI 자동 처리율"·"AI와 사람 비중"

## 3. 보고
- [ ] 3.1 팀 보고: 규칙 3·4·D32 변경, 기본값 켜짐, 실제 메일 연동 시 먼저 끌 것
