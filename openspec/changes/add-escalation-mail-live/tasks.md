# Tasks: 이관 메일 실제 발송·수신

## 1. 보내기 (BE 나송주)
- [x] 1.1 설정 `MAIL_ENABLED`·SMTP·Mailpit·C/S 주소·부서 도메인·확인 주기
- [x] 1.2 `app/mail/outbound.py`: 부서 주소, 요청 메일(제목 `[ESC:…]`, 가린 원문), SMTP 발송
- [x] 1.3 `escalate(mailer=…)`: 같은 트랜잭션 안에서 보내고 실제 결과로 `via_mail` 쓰기, 응답 `mail`
- [x] 1.4 docker compose Mailpit, `.env.example`

## 2. 받기 (BE 나송주)
- [x] 2.1 `app/mail/inbox.py`: Mailpit API 안 읽은 메일 읽기·읽음 표시
- [x] 2.2 `app/mail/replies.py`: 제목 표시·보낸 사람 검사, 인용문 떼기, `register_reply(via_mail=True)`
- [x] 2.3 스케줄러 `mail_poll` 작업, `POST /mail/poll`(연결 뒤 DEPT_REPLY 다시 처리)
- [x] 2.4 시연 `POST /mail/dept-reply-demo`(실제 SMTP 답장)

## 3. 화면 (FE 나송주)
- [x] 3.1 `GET /mail/config`, 이관 팝업 실제 주소·발송 안내·실패 알림
- [x] 3.2 이력 탭 [메일함 열기]·[지금 확인]·[부서 답장 보내기 (시연)], 꺼져 있으면 예전 화면

## 4. 시험과 마무리 (나송주)
- [x] 4.1 `test_escalation_mail_live.py` 11개(가짜 SMTP·메일함으로 보내기 → 답장 → 연결 → 다시 처리, 사칭·중복·늦은 답장·실패·꺼짐)
- [x] 4.2 실제 Mailpit + 서버로 확인: 이관 → 요청 메일 도착 → 메일 프로그램식 한국어 답장 → 5초 주기 확인으로 RECEIVED·IN_PROGRESS·DEPT_REPLY 실행
- [x] 4.3 계약(openapi.json, api.gen.ts), API 수 시험 46 → 49
- [x] 4.4 README "원본 이후 개인 고도화"
- [x] 4.5 시연 중 발견: 메일함에서 연 답장(읽음)을 놓침 → 읽음 대신 C/S 주소·`cs-linked` 태그로 고름, 시험 추가
