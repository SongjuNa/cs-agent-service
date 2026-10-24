# Design: 이관 후보 표시

## Context

routing_rules.csv의 이관 행은 3개이고, 모두 문의 유형 DEFECT, primary_dept가 "(제품군 기술지원)"(DB에서는 NULL), escalation_condition이 "DEFECT 조치 유형 = RMA / ONSITE / SAFETY"다(근거: routing_rules.csv RT-ESC-DEFECT-RMA/ONSITE/SAFETY, schema.sql ref.routing_rule 주석 "원본 '(제품군 기술지원)' → NULL"). 조건 문구는 코드에 박지 않는다(근거: FR-020 처리 1, §5-6). 이관 행 조건용 조건 표는 테이블 정의서에 없다(근거: schema.sql, 우선순위만 priority_rule_urgency·priority_rule_category가 있음). 팀 보충 이관 규칙 2개는 설정 파일에 두기로 했다(근거: §5-6 "설정 파일 config/escalation_rules_team.yaml. ref 표에는 넣지 않는다", 조장 결정 2026-10-23). 고장 진단 후보는 변경 22가 상태 객체 fault_candidates에 둔다(근거: openspec/specs/fault-diagnosis).

## Decisions

### 1. 판정 (`backend/app/rules/escalation.py`, `config/escalation_rules_team.yaml`)

| 항목 | 정한 것 | 근거 |
|---|---|---|
| 운영진 행 읽기 | ref.routing_rule에서 rule_source = ESCALATION 행을 읽는다. escalation_condition의 "조치 유형 = X"의 X가 켜졌을 때 후보. 행의 category(DEFECT)로 문의 유형을 좁히지 않는다. 진단을 받는 INSTALL·WARRANTY도 출동·교체 표시로 후보가 켜진다 | FR-020 처리 1·2(유형 제한 없음), §5-6 "켜지는 조건" 표, 구현 선택 C-144·C-149 |
| X의 뜻 | SAFETY = urgency_flag SAFETY, RMA = 진단 1순위 replace_required, ONSITE = 진단 1순위 onsite_required. 이유 표시 SAFETY / 교체 / 현장 출동 | §5-6 표 "켜지는 조건"·"이유 표시" |
| 팀 규칙 | 설정 파일의 rule_id, category, return_reason_words 또는 priority, escalation_dept, escalation_reason. 반품 사유는 L2 영어 사유(return_reason)를 소문자로 바꿔 단어 포함을 본다(§5-6 "§5-3과 같은 방식(소문자, 단어 포함)"). 반품 문의는 고장 진단 대상이 아니라 이 규칙만 본다(FR-020 처리 5). 우선순위는 Q3 규칙값 priority_final | FR-020 처리 5, §5-6 팀 규칙 표, 보충_이관_규칙_v1_20261022.md 4장, 구현 선택 C-145 |
| 이관 사유 코드 | 후보마다 escalation_reason 코드(RMA → RMA_REQUIRED, ONSITE → ONSITE_REQUIRED, SAFETY → SAFETY, 팀 규칙은 파일 값)를 함께 남긴다. 다음 변경의 [이관] 팝업 기본값용 | schema.sql escalation_reason 11값, 구현 선택 C-146 |
| 여러 행 | 맞은 것을 모두 둔다(운영진 행 → 팀 규칙 순) | FR-020 처리 2, 예외 3행 |
| 없음 | 후보 없음 + FR-012가 기록한 escalation_condition 문구 | FR-020 처리 4, §5-3 6번 |
| 진단 없음 | 고장 계열인데 진단 후보가 없으면 SAFETY 판정만 하고 표시 "진단 없음 — 이관 조건만 표시" | FR-020 예외 1행 |
| 조회 실패 | 표나 설정 파일을 못 읽으면 후보 없음, 표시 "이관 규칙을 읽을 수 없음", 실행 기록 Q9a를 FAILED로 | FR-020 예외 2행, 구현 선택(C-141과 같은 모양) |

- 이 모듈은 규칙 코드라 언어 모델 호출 계층을 import하지 않는다(근거: CLAUDE.md 규칙 1, 설계 원칙 2).
- 설정 파일 위치와 읽기는 반품 단어 목록과 같은 방식(`app.config.REPO_ROOT / "config"`)이다(근거: `app/rules/routing.py` RETURN_WORDS_FILE, docker-compose `./config:/config`).

### 2. 처리 흐름 (`graph.py`, `state.py`, `runlog.py`, `store.py`)

- 노드 `escalate`를 diagnose 뒤, info_request 앞에 둔다. 모든 하위 문의에 대해 돈다(근거: §2-1 흐름 "Q8a → Q9a", §2 "정보 요청 여부와 상관없이").
- 상태 객체: escalation_candidates와 escalation 결과(후보·조건 문구·표시)(근거: §5-6 저장). EscalationHint의 rule_id, dept, reason은 기존 필드이고(근거: state.py, §2-3), reason_code(C-146)와 team(팀 규칙 표시, FR-020 처리 5 "팀 규칙으로 표시", 구현 선택 C-152)을 더한다.
- 실행 기록: 노드 시간은 단계 Q9a. 저장할 때 Q8a 뒤(없으면 Q6 뒤)에 Q9a 행 하나 — output_json = {escalation_candidates, escalation_condition, notes}(근거: §5-6 저장 "agent_step.output_json", FR-036 처리 2).
- sub_ticket의 escalated·escalated_to·escalation_reason과 상태는 건드리지 않는다(근거: AC-020-4, FR-020 기능 설명 "상태를 바꾸지 않는다").

### 3. 상세 응답과 화면 (`detail.py`, `DetailTabs.tsx`)

- `GET /tickets/{id}`의 하위 문의마다 `escalation` = 마지막 실행의 Q9a 결과(근거: 기술 명세서 §8-1 "하위 문의별 결과(진단 후보·이관 후보 포함)").
- 근거 줄 "⑩ 이관 후보": 부서별 한 줄 "{부서} — {rule_id} ({이유}), {rule_id} ({이유})"(같은 부서의 행은 한 줄에 모은다), 팀 규칙이면 "(팀 규칙)", 없으면 "없음 — 이관 조건: {문구}". 진단 없음·규칙 읽기 실패 표시는 그 아래에 함께 보인다(근거: FR-020 출력, 예외 1~3행, 구현 선택 C-150). "왜?"는 Q9a 단계와 맞은 규칙 행(운영진 행은 ref.routing_rule 행, 팀 규칙은 설정 파일 행)(근거: 화면 정의서 v1 C-09·P1 "이관 후보 → ESCALATION 행과 켜진 조건", AC-024-1).
- 문의 구역에 이관 후보 줄을 고장 진단 후보 아래에 둔다. 부서별 한 줄, 팀 규칙 표시, 버튼 없음(근거: FR-020 출력 "버튼 없음", 예외 3행 "부서별 한 줄씩", 조장 결정 2026-10-23 기존 레이아웃 유지).

### 4. 시험 (`tests/acceptance/test_escalation_candidates.py`)

- AC-020-1·2·6·7·8: 운영진 데이터 문의 CSV1-000202, CSV1-000007, CSV1-000229, CSV1-000200, CSV1-000133을 접수 API로 처리(대역 언어 모델이 L1·L2 값을 냄)(근거: tickets.csv, AC-020-1·2·6·7·8).
- AC-020-3: CSV1-000017을 진단이 실패하게 해(진단 후보 없음) 처리 → "없음 — 이관 조건: {RT-LV_BREAKER-DEFECT 문구}"와 표시 "진단 없음 — 이관 조건만 표시"(근거: AC-020-3, FR-020 예외 1행, 구현 선택). AC-020-3 괄호의 "AC-012-1의 FIELD_SVC 조건"은 데이터(RT-LV_BREAKER-DEFECT escalation_dept = QA_CLAIM)와 다르다. 이 변경 전부터 있던 차이라 시험은 표의 문구를 그대로 비교한다.
- AC-020-4: 후보가 켜진 문의의 상태가 ESCALATED가 아니고 escalated가 false(근거: AC-020-4).
- AC-020-6: 대역 L2가 본문의 반품 사유를 return_reason으로 낸다. 정답 CSV1-000229는 missing_info에 return_reason이 있지만 본문에 "Reason: …"이 있다(근거: tickets.csv, 구현 선택 C-151).
- AC-020-5: tickets.csv의 이관된 행에서 정답 값(유형·긴급도·우선순위·에러 코드로 정확 진단·본문의 반품 사유 단어)으로 판정 함수를 불러 정답 escalated_to가 후보 부서에 있는 비율을 출력한다. 정답 열을 읽는 시험 코드다(근거: AC-020-5, CLAUDE.md 규칙 6 예외, 구현 선택 C-147).
- AC-024-1: 기존 시험에 이관 후보 줄을 더한다(근거: AC-024-1).
- 판정 함수의 예외(조회 실패, 여러 행)를 함수 단위로 본다(근거: FR-020 예외 표).

## Risks / Trade-offs

- 팀 규칙의 우선순위는 Q3 규칙값이다. 상담원이 P1로 조정한 설치 문의는 다시 처리하기 전까지 팀 규칙이 켜지지 않는다(구현 선택 C-145).
- AC-020-5 첫 측정(에러 코드 정확 진단만 씀): 이관 685건 중 136건(0.199). SAFETY 4/4, 반품 품질 69/106, 교체 27/94, 현장 출동 28/162, 설치 P1 8/30. 정확 진단이 있는 교체·현장 출동 이관은 52/84. 상업 조건·원인 분석·펌웨어 등은 FR-020 규칙이 다루지 않는 사유다(근거: 시험 출력, FR-020 처리 6).
- 증상 검색 진단은 1순위 후보의 표시를 쓰므로, 관련성 낮은 후보에서도 교체·출동 후보가 켜질 수 있다. 명세서대로 "1순위"를 쓴다(근거: FR-020 입력 "진단 후보 1순위", C-148).
