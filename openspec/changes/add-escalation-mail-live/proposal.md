# Proposal: 이관 메일 실제 발송·수신 (add-escalation-mail-live)

> 팀 프로젝트 종료 뒤 개인 고도화(나송주, 2026-11). 원본 `add-escalation-mail`은 메일이 오갔다는 **표시만** 남기는 시안이었다.

## Why
`add-escalation-mail`은 이관 팝업의 "메일로도 보내기"를 켜도 메일을 보내지 않고 `via_mail` 표시만 남겼고, 부서 회신은 [회신 메일 도착 (시연)] 버튼으로 흉내 냈다(제안서 "범위 밖 / 정직한 한계"). 이관받은 부서가 이 시스템을 열지 않고 메일로만 일한다는 목업의 전제를 실제로 동작하게 만든다.

## What Changes
- **보내기**: 이관할 때 `send_mail`이고 메일 연동(`MAIL_ENABLED`)이 켜져 있으면 부서 메일함으로 SMTP 메일을 보낸다.
  - 받는 곳은 부서 코드로 만든 주소(`qa_claim@<MAIL_DEPT_DOMAIN>`). **표·열은 바꾸지 않는다**(설정 하나).
  - 제목에 `[ESC:<하위 문의 번호>]`를 넣는다. 본문에 문의 요약, C/S 메모, 문의 화면 링크, 개인정보를 가린 고객 원문, 회신 방법.
  - 보내기는 이관과 **같은 트랜잭션 안**에서 이관 메모를 쓰기 직전에 한다. 발송한 메모(SENT)는 고칠 수 없으므로(`guard_ticket_message`), `via_mail`은 실제로 보냈는지에 맞춰 처음부터 쓴다. 실패해도 이관은 확정하고 응답 `mail.sent=false`·오류를 준다.
- **받기**: 받은 메일함(Mailpit API)을 `MAIL_POLL_SECONDS`(기본 30초)마다 확인한다(`POST /mail/poll`로 바로 확인도 가능).
  - 연결 조건: C/S 메일함으로 왔고, 제목에 `[ESC:…]`가 있고, **보낸 사람이 그 문의를 이관받은 부서 메일함**일 때만(사칭 방지).
  - 인용문(`>` 줄, "On … wrote:", "…님이 작성:", Original Message)을 떼고 남은 글을 기존 [회신 등록](`register_reply`, `via_mail=True`)으로 넘긴다. 상태 전이·실행 로그·다시 처리(DEPT_REPLY)는 화면 회신과 같다.
  - 처리했든 건너뛰었든 `cs-linked` 태그를 붙여 두 번 보지 않는다. "읽음" 상태는 쓰지 않는다(사람이 메일함에서 열기만 해도 읽음이 되어 답장을 놓침). 건너뛴 까닭은 응답·서버 로그에 남긴다.
- **시연**: `POST /mail/dept-reply-demo`는 부서 메일 프로그램 대신 부서 주소로 **실제 SMTP 답장**을 보낸다. 연결은 다른 메일과 똑같이 받기가 한다.
- **화면**: 이관 팝업은 실제 받는 주소와 "실제로 발송됨" 안내, 발송 실패 알림. 이력 탭은 [메일함 열기]·[지금 확인]·[부서 답장 보내기 (시연)]. 연동이 꺼져 있으면 예전 화면 그대로.
- **실행 환경**: docker compose에 Mailpit(웹 8025, SMTP 1025) 추가. 메일은 밖으로 나가지 않는다.

## API
`GET /mail/config`, `POST /mail/poll`, `POST /mail/dept-reply-demo`. `POST /sub-tickets/{id}/escalate` 응답에 `mail`(to, subject, sent, error).

## 범위 밖
- 실제 회사 메일(Microsoft Graph·Gmail API, IMAP) 연결. `Inbox`·`Sender` 인터페이스를 갈아 끼우면 된다.
- 첨부, HTML 본문 해석, 스레드 헤더(In-Reply-To)로 찾기. 지금은 제목 표시로만 찾는다.
- 고객에게 가는 메일은 이 변경과 무관하다(여전히 발송 기록만, CLAUDE.md 규칙 3).

## Impact
`app/mail/`(새 패키지: outbound·inbox·replies), `app/api/mail.py`(새), `status/escalation.py`(mailer 훅), `api/sub_tickets.py`, `api/deps.py`(Mail 의존성), `config.py`, `scheduler.py`, `main.py`, `schemas.py`, `docker-compose.yml`, `.env.example`, `openapi.json`·`api.gen.ts`, 이관 팝업·이력 탭, 시험 `test_escalation_mail_live.py`(11개), 계약 시험 API 수 46 → 49.
