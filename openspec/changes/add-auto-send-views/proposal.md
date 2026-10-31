# Proposal: 자동 발송 화면 연동 (add-auto-send-views)

## Why

변경 add-auto-send(PR #83)가 서버와 규칙 화면을 만들었다. 이 변경은 최신 목업(합의된 기준)의 나머지 화면을 맞춘다: 접수함 "자동 처리", 상세의 사후 검수, 나의 업무 현황 "AI 자동 처리", 운영 대시보드의 AI 비중.

## What Changes

- 접수함 `GET /tickets`: `auto=true` 필터, 줄 `auto_state`(NONE·PENDING·REVIEWED), `counts.auto`·`counts.auto_pending`. 사후 검수 전은 `turn=ME`, `next_action=REVIEW_AUTO`로 내 차례에 남는다(`rules/turn.py`와 SQL을 함께 고침).
- 상세 `GET /tickets/{id}`: 하위 문의에 `auto_state`.
- `GET /dashboard/summary`: `auto {sent, reviewed, human, total}`. `GET /me/performance`: `auto {sent, pending}`.
- 화면: 접수함 [자동 처리] 단추와 줄 표시, 상세 [사후 검수 완료], 나의 업무 현황 카드, 운영 대시보드 카드·막대.

## 규칙·DB

- 새 표·열 없음(auto_review는 add-auto-send에서 추가됨). 새 엔드포인트 없음.
- 자동 발송 메시지의 식별은 `sender='SYSTEM' AND sent_by_name='AI_AUTO'`(add-auto-send와 같다).

## 시험

`backend/tests/acceptance/test_auto_send_views.py`(차례·필터·검수·집계), e2e SCR-12-AC-4·5.
