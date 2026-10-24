# Proposal: 이관 후보 표시 (add-escalation-candidates)

## Why

상담원은 이 문의를 전문 부서로 넘겨야 하는지, 넘긴다면 어디인지 판단해야 한다. 시스템이 고장 진단 후보의 현장 출동·교체 필요 표시와 긴급도로 배정 규칙의 이관 행을 찾아 "이관 후보"와 예상 이관 부서를 보여 주어야 한다(근거: 명세서 v1.5 FR-020 기능 설명). 팀 보충 이관 규칙 2개(반품 품질, 설치 P1)도 함께 본다(근거: FR-020 처리 5, 다-15). 이관 확정은 다음 변경(FR-033)의 [이관] 버튼이 하고, 이 기능은 표시만 하며 상태를 바꾸지 않는다(근거: FR-020 기능 설명, AC-020-4).

## What Changes

- **이관 후보 단계 Q9a (FR-020)**: 고장 진단(Q8a) 바로 뒤에서 모든 하위 문의에 대해 돈다(근거: 기술 명세서 v1.4 §2-1 흐름, §2 "Q8a와 Q9a는 정보 요청 여부와 상관없이 규칙 단계 바로 뒤", §5-6 "Q9a 노드").
  - 운영진 이관 행 3개(routing_rules.csv rule_source = ESCALATION)를 표에서 읽고 각 행의 조건 문구대로 판정한다: SAFETY 긴급도 → RT-ESC-DEFECT-SAFETY, 진단 1순위 교체 필요 → RT-ESC-DEFECT-RMA, 진단 1순위 현장 출동 필요 → RT-ESC-DEFECT-ONSITE. 여러 행이 맞으면 모두 둔다(근거: FR-020 처리 1·2, §5-6 표).
  - 팀 보충 이관 규칙 2개를 설정 파일 `config/escalation_rules_team.yaml`에서 읽는다: RT-ESC-TEAM-RETURN-QUALITY(반품 + 사유 단어 → QA_CLAIM), RT-ESC-TEAM-INSTALL-P1(설치 + P1 → FIELD_SVC)(근거: FR-020 처리 5, §5-6 팀 보충 이관 규칙, 조장 결정 2026-10-23 "설정 파일로 진행").
  - 출력: 후보마다 예상 이관 부서, rule_id, 이유, 운영진/팀 규칙 구분. 맞는 행이 없으면 "없음"과 FR-012의 이관 조건 문구(근거: FR-020 처리 3·4·출력).
  - 예외 3개: 진단 없음 → SAFETY 판정과 이관 조건만 / 이관 행 조회 실패 → 후보 없음, 실행 기록 / 부서가 다른 여러 행 → 모두(근거: FR-020 예외 처리 표).
  - 저장: 상태 객체 escalation_candidates와 실행 기록(agent_step.output_json, 단계 Q9a). 상태는 바꾸지 않는다(근거: §5-6 저장, AC-020-4).
- **티켓 상세 표시**: 문의 구역의 고장 진단 후보 아래에 "이관 후보: {부서} — {rule_id} ({이유})"(팀 규칙은 "팀 규칙" 표시), 없으면 "없음 — 이관 조건: {문구}". 근거 줄 "이관 후보". 버튼 없음(근거: FR-020 출력, 화면 정의서 v1 SCR-03 C-09, AC-024-1, 조장 결정 2026-10-23 기존 레이아웃 유지).

## Capabilities

### New Capabilities
- `escalation-candidates`: 하위 문의의 이관 후보(운영진 이관 행 3개 + 팀 규칙 2개) 판정과 표시.

## 범위 밖

- **이관 확정([이관] 버튼, ESCALATED)**: 다음 변경 24 add-escalation(근거: FR-033, 3순위_시작_전후비교.md §3 변경 순서).
- **팀 규칙의 DB 저장과 관리 화면**: 나중에 추가(근거: 조장 결정 2026-10-23, openspec/config.yaml).
- **보증·비불량 반품·P1이 아닌 설치 규칙**: 규칙을 두지 않는다(근거: FR-020 처리 6).
- **팀 정답지 재현율(AC-020-5)**: 팀 정답지 적재(W9)가 없어 tickets.csv로 대신 보고한다(근거: 결정 기록 C-3·C-137 선례, 구현 선택).

## Impact

- 새 파일: `config/escalation_rules_team.yaml`, `backend/app/rules/escalation.py`(규칙 판정), 시험 `backend/tests/acceptance/test_escalation_candidates.py`(근거: design 결정 1~4).
- 고치는 파일: `backend/app/pipeline/graph.py`·`state.py`·`runlog.py`(노드), `backend/app/db/store.py`(Q9a 기록), `backend/app/db/detail.py`(상세 응답·근거 줄), `frontend/src/DetailTabs.tsx`·`api.ts`, `backend/tests/acceptance/test_ticket_detail.py`(AC-024-1)(근거: design 결정 2~4).
- DB 구조는 고치지 않는다(근거: CLAUDE.md 규칙 4, §5-6 "ref 표에는 넣지 않는다").
