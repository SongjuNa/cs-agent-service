# Proposal: 이관 메일 (add-escalation-mail)

## Why
최신 목업의 이관 팝업에는 "이관 요청을 메일로도 보내기"(받는 곳·제목·내용 미리보기)가 있고, 이력에 "메일 발송/수신"이 남으며, 부서가 메일로 답장하면 회신이 문의에 자동 연결되는 흐름을 [회신 메일 도착 (시연)]으로 보여 준다(GAP.md B-1 #8). 저장소에는 부서에 보내는 메모(`ESCALATION_NOTE` 발송)와 부서 회신(`ESCALATION_NOTE` 받음)이 이미 있지만 "메일로 오갔는지"는 기록하지 않는다. 팀 합의(2026-10-31)로 목업이 최신 기준이고 새 열·표를 만들어도 된다는 허락을 받았다(규칙 4).

## What Changes
- **새 열 `svc.ticket_message.via_mail`**(boolean, 기본 false; scoring 정의에도 같은 열). **새 표는 없다.** 이관 메모·부서 회신이 이미 `ticket_message`에 있어서 그 글이 메일로 오갔다는 표시만 더한다.
- `POST /sub-tickets/{id}/escalate`에 `send_mail`(기본 false): 켜면 부서에 보낸 메모가 `via_mail`로 남는다.
- `POST /sub-tickets/{id}/dept-reply`에 `via_mail`(기본 false): 부서가 메일로 회신한 것으로 기록한다. **메일 회신은 화면에서 고른 부서와 달라도 받아들인다**(메일 스레드가 부서를 가리키므로). 메일이 아니면 예전처럼 이관받은 부서만 가능(403 유지).
- 이력(`/tickets/{id}/timeline`) 메시지 줄에 `via_mail`.
- 화면: 이관 팝업에 "메일로도 보내기"(처음부터 켜짐)와 미리보기, 이력에 "이관 요청 메일 발송"·"회신 메일 수신", 기다리는 동안 [회신 메일 도착 (시연)] 버튼.

## 범위 밖 / 정직한 한계
- **실제 메일 발송·수신 연동은 없다.** 목업과 같이 "화면 예시"이고, 화면에도 그렇게 적는다. [회신 메일 도착 (시연)]은 부서가 메일로 답장한 것처럼 회신 본문을 자동으로 넣어 기존 회신 처리(다시 처리 포함)를 돌린다.
- 메일 제목·받는 곳은 저장하지 않고 화면이 티켓 번호·사유·부서 이름으로 만든다.
- 부서별 메일 주소(`ref.department`에 열 없음), 첨부, 메일 본문 파싱.

## 이미 만들어진 DB에 반영하는 방법
```sql
ALTER TABLE svc.ticket_message ADD COLUMN IF NOT EXISTS via_mail boolean NOT NULL DEFAULT false;
ALTER TABLE scoring.ticket_message ADD COLUMN IF NOT EXISTS via_mail boolean NOT NULL DEFAULT false;
```

## Impact
`schema.sql`·`table-specification.md`, `status/escalation.py`·`dept_reply.py`, `api/sub_tickets.py`, `db/timeline.py`, `openapi.json`, `api.gen.ts`, 이관 팝업·이력 탭·티켓 페이지, 시험 `test_escalation_mail.py`(3개)·SCR-03-AC-28.
