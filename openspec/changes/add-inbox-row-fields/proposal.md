# Proposal: 접수함 줄·건수 값 추가 (add-inbox-row-fields)

## Why

최신 목업의 접수함은 줄마다 문의 한 줄과 국가를 보이고, 위쪽에 새 문의·이관 건수와 "기한 초과 n · 기한 임박 n"을 보인다. `GET /tickets`는 이 값을 주지 않아 화면이 그릴 수 없다(근거: `GAP.md` A-1 #1·#2·#10·#11·#13). 팀 결정으로 목업이 최신 기준이다(2026-10-31).

## What Changes

- `InboxRow`에 `country`(`ref.customer.country`)와 `inquiry_subject`(`ticket.inquiry_subject`)를 더한다.
- `counts`에 `new`(NEW), `escalated`(ESCALATED), `breach`(1차 응답·해결 기한 초과 경고가 하나라도 있는 줄), `risk`(기한 임박 경고만 있는 줄)를 더한다. `breach + risk = alert`다.
- 건수는 기존 `counts`처럼 지금 걸린 필터가 적용된 줄을 센다.

## 범위 밖

- **한국어 요약 한 줄.** 목업의 요약은 AI가 만들어 저장하는 값이라 새 열과 모델 호출이 필요하다(CLAUDE.md 규칙 4: 사람에게 먼저 묻는다). 이번에는 고객이 쓴 제목(`inquiry_subject`, 원문 언어)을 대신 보인다.
- 담당 상담원 필터, 내 차례 정렬, 검토 모드, 다음 행동 문구는 다음 변경에서 한다.

## Impact

- 고치는 파일: `backend/app/db/inbox.py`, `backend/app/api/schemas.py`, `frontend/openapi.json`, `frontend/src/api.gen.ts`, 접수함 화면, 시험 `test_inbox.py`.
- DB 구조는 고치지 않는다(규칙 4). 기존 열을 읽을 뿐이다.
