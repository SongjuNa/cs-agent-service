# Proposal: 담당 변경 (add-reassign)

## Why
최신 목업의 접수함 선택 막대에는 "내가 맡기"와 "담당자 변경…"이 있고, 바꾼 기록이 이력에 남는다. 저장소에는 담당을 바꾸는 API가 없다(GAP.md A-1 #12, B-1 #11, F "문의 배정 관리"). 팀 합의(2026-10-31)로 목업이 최신 기준이고, **새 표를 만들어도 된다는 허락을 받았다**(규칙 4).

## What Changes
- **새 표 `svc.assignment_history`**(from, to, 바꾼 사람, 시각). 넣기만 한다. 접수 때 자동 배정은 남기지 않는다.
- API `POST /sub-tickets/assign` { sub_ticket_ids[≤200], assignee } + 머리 `X-Agent-Id`. 한 번에 여러 문의(하나여도 같은 주소). 응답 `moved[]`, `skipped[{sub_ticket_id, reason}]`.
  - 담당은 **그 문의를 맡은 부서(담당 부서 또는 이관받은 부서) 명단**의 사람만. 종료된 문의, 이미 그 사람 담당, 다른 부서 사람, 없는 문의는 건너뛰고 사유를 돌려준다. 나머지는 바뀐다.
  - 400: 선택 없음·200건 초과·상담원 미선택·명단에 없는 이름. 문의 줄을 잠그고 한 트랜잭션에서 바꾼다.
- 이력(`GET /tickets/{id}/timeline`)에 `ASSIGNEE` 종류.
- 화면: 접수함 선택 막대에 [내가 맡기]·[담당자 변경…]·[변경], 이력 탭에 "담당 변경 A → B".

## 범위 밖 (다음 변경)
- 일괄 우선순위 조정(기존 단건 API 조합), 문의 배정 관리 화면(부서·상담원·사유로 거르기), 문서 안 검색.
- 자동 재배정, 부하 분산, 휴가 처리.

## 이미 만들어진 DB에 반영하는 방법
`schema.sql`의 `svc.assignment_history` 구간(CREATE TABLE·COMMENT·CREATE INDEX)을 한 번 실행한다. 데이터는 지우지 않는다.

## Impact
`docs/database/schema.sql`·`table-specification.md`(4-13), `backend/app/api/assign.py`, `db/timeline.py`, `schemas.py`, `main.py`, `openapi.json`, `api.gen.ts`, 접수함·이력 화면, 시험 `test_reassign.py`(3개)·계약 시험(39 → 40)·SCR-02-AC-13.
