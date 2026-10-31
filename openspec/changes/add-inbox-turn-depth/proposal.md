# Proposal: 접수함 내 담당·내 차례·검토 모드 (add-inbox-turn-depth)

## Why

최신 목업의 접수함은 "내 담당 / 팀 전체" 보기, 내가 처리할 문의를 위로 묶는 정렬, 줄마다 "다음 행동" 문구, 검토 모드(상세·일반·빠른)를 보인다. 서버가 이 값을 주지 않아 화면이 그릴 수 없다(근거: `GAP.md` A-1 #3·#4·#5·#6). 팀 결정으로 목업이 최신 기준이다(2026-10-31). 규칙은 목업 `lib/progress.ts`(turnOf·actionOf)와 `lib/depth.ts`(assess)에 있다.

## What Changes

- **담당 필터**: `GET /tickets?assignee=` (담당 상담원 이름으로 거른다). 줄의 `assignee_masked`는 이미 있다.
- **내 차례**: 줄마다 `turn`(`ME`·`DEPT`·`CUSTOMER`·`DONE`)과 `next_action`(코드). 필터 `turn=`.
- **검토 모드**: 줄마다 `review_depth`(`DEEP`·`NORMAL`·`QUICK`).
- **기본 정렬**: 내 차례 → 기다리는 문의(부서·고객) → 완료 순, 각 묶음 안은 지금 정렬(경고 → 남은 시간 → 접수 시각).
- **건수**: `counts.mine`(요청한 상담원의 담당 미해결 줄 수), `counts.turn_me`.
- 규칙 코드는 `backend/app/rules/turn.py`에 둔다. 언어 모델 호출 계층을 import하지 않는다(CLAUDE.md 규칙 1).

## 범위 밖

- 새 열·표(규칙 4). 모두 기존 열과 메시지 이력에서 계산한다.
- 일괄 담당 변경(재배정) API. 다음 변경 `add-ticket-reassign`에서 한다(담당 변경 이력이 필요해 설계가 따로다).
- 검토 모드 입력 중 "검토 표시 ①②③ 걸림", "AI 분류 신뢰도 낮음": 저장 위치를 확인하지 못했다. 1차는 저장된 값만 쓰고 없으면 빼며, 확인 후 2차로 더한다.
- 한국어 요약 한 줄(add-inbox-row-fields 범위 밖 항목과 같다).

## Impact

- 고치는 파일: `backend/app/db/inbox.py`, 새 `backend/app/rules/turn.py`, `backend/app/api/tickets.py`(쿼리 파라미터), `schemas.py`, `openapi.json`, `api.gen.ts`, 접수함 화면, 화면 명세 SCR-02, 시험.
- 기본 정렬이 바뀌어 **FR-029 처리 3과 AC-029-1("맨 위는 경고가 있고 남은 시간이 가장 적다")이 달라진다.** 요구사항 명세서 쪽 확인이 필요하다.
