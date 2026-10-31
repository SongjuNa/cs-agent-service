# Tasks: 접수함 내 담당·내 차례·검토 모드

## 0. 확인
- [x] 0.1 (팀 합의 2026-10-31: 목업이 최신 기준) 기본 정렬 변경(FR-029 처리 3)을 팀·조장이 받아들이는지
- [ ] 0.2 검토 모드 조건 확정, "검토 표시 걸림"·"분류 신뢰도"의 저장 위치 확인

## 1. 서버
- [x] 1.1 `rules/turn.py`: `turn_of`, `depth_of` 순수 함수 + 단위 시험
- [x] 1.2 `db/inbox.py`: `assignee`, `turn`, `me` 파라미터, `dept_replied`, 줄에 `turn`·`next_action`·`review_depth`, `counts.mine`·`turn_me`, 기본 정렬
- [x] 1.3 `api/tickets.py`, `schemas.py`, `openapi.json`, `api.gen.ts`
- [x] 1.4 `test_inbox.py` 확장, AC-029-1 조정

## 2. 화면 (SCR-02)
- [ ] 2.1 보기 범위(내 담당 / 팀 전체), 담당 상담원 필터
- [ ] 2.2 묶음 머리(내가 처리할 문의 / 기다리는 문의 / 처리 완료), 다음 행동 문구, 검토 모드 표시
- [ ] 2.3 부제 "지금 처리할 문의 n건", [다음 문의 처리 시작]
- [ ] 2.4 화면 시험, `npm run build`
