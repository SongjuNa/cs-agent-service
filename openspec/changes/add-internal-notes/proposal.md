# Proposal: 내부 메모 (add-internal-notes)

## Why
최신 목업의 문의 상세에는 상담원끼리 남기는 "내부 메모"가 있고, 접수함 줄에는 메모 개수가 붙는다. 저장소에는 메모 표도 API도 없다(GAP.md A-1 #8, B-1 #9). 팀 합의(2026-10-31)로 목업이 최신 기준이고, **새 표를 만들어도 된다는 허락을 받았다**(CLAUDE.md 규칙 4의 "먼저 묻기"를 사용자가 미리 허락, 나중에 정리 보고).

## What Changes
- **새 표 `svc.internal_note`**(note_id, ticket_id FK, body 1~2000자, author, created_at_utc, 색인 1개). 넣기만 한다.
- API 2개: `GET /tickets/{id}/notes`(시각순), `POST /tickets/{id}/notes`(201, 400: 빈 글·2000자 초과·상담원 미선택, 404: 없는 티켓). 작성자는 `X-Agent-Id`.
- 접수함 줄에 `memo_count`.
- 화면: 문의 상세 왼쪽 칸 아래 "내부 메모" 카드(목록 + 입력 + [메모 남기기]), 접수함 문의 칸에 "메모 n".
- **고객에게 보내지 않는다.** 메시지·초안 표와 섞지 않고, 언어 모델 호출 계층을 거치지 않는다.

## 범위 밖
수정·삭제, 하위 문의별 메모, 메모 검색, 멘션·알림.

## 이미 만들어진 DB에 반영하는 방법
`schema.sql`은 DB가 비어 있을 때만 실행되므로, 기존 DB에는 `docs/database/schema.sql`의 `svc.internal_note` 구간(CREATE TABLE, COMMENT, CREATE INDEX)을 한 번 실행한다. 데이터는 지우지 않는다.

## Impact
`docs/database/schema.sql`·`table-specification.md`(4-12), `backend/app/api/notes.py`, `schemas.py`, `main.py`, `db/inbox.py`, `openapi.json`, `api.gen.ts`, 화면 `MemoCard.tsx`·`TicketPage.tsx`·접수함, 시험 `test_internal_notes.py`·계약 시험(37 → 39)·SCR-03-AC-26.
