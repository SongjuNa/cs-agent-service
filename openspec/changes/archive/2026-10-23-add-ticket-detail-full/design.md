# Design: 티켓 상세 전체판

## Context

- 명세서 v1.5 FR-030(AC-030-1~5), FR-005 예외·AC-005-3, FR-010 AC-010-3, FR-013 AC-013-3, FR-028(조정 팝업), FR-032(회신 입력 팝업), FR-035 처리 7, FR-036 처리 5·7.
- 기술 명세서 v1.4 §2-2 노드 목록, §2-4 재처리·부분 재실행 행, §8-1 GET /tickets/{id}·timeline·PATCH /sub-tickets·reprocess 행, §8-2 티켓 상세 행.
- 화면 정의서 v1 SCR-03(H·L·C·R·B, ⑤ 동작 요약, ⑥ 상태 변형), SCR-03-P3·P6·P8. 화면 정의서 v2 0-7절(A안 탭 4개), 부록 B-2·B-3.
- schema.sql svc.ticket(inquiry_subject, contact_*), svc.inquiry_field(span_start·span_end·source), svc.agent_run(trigger AGENT_EDIT), svc.agent_step(input_json), svc.sub_ticket.version.

## Decisions

### 1. 상세 묶음 더하기 (`backend/app/db/detail.py`)

| 더하는 값 | 내용 | 근거 |
|---|---|---|
| ticket.inquiry_subject, inquiry_body | 원문 그대로(가리지 않음) | FR-030 처리 1, SCR-03 L-01·L-02, §7 "원문은 상담원 화면에" |
| ticket.contact_name·email·phone | 보낸 사람 연락처 원문 | FR-030 처리 1(v1.5 가-7), §8-1 상세 행 |
| sub_tickets[].fields | 추출 값 목록(field, label, value_raw, value_norm, span_start, span_end, source) | FR-030 처리 1 "추출한 값 강조", SCR-03 L-01 provided_fields.span, schema.sql inquiry_field |
| sub_tickets[].edits | 상담원이 고친 항목 → {from, to, by, at}(가장 최근 것) | FR-030 처리 6 "상담원 수정 표시", AC-030-5 |
| sub_tickets[].product_name | 제품 이름 | SCR-03 C 구역(제품 드롭다운 표시), 구현 선택 |
| can_reprocess | 처리 중이 아니고 종료(CLOSED)만 남은 티켓이 아니면 참 | SCR-03 H-05, ⑥ 종료 "버튼 전부 비활성", 구현 선택 |

- 강조 위치: span이 있으면 그 위치, 없으면 원문에서 value_raw를 찾아 강조한다(근거: SCR-03 L-01, 1순위 추출은 span을 채우지 않음 — schema.sql 열은 있고 `app/llm/extract.py`가 값만 냄. 찾기는 구현 선택).

### 2. 이력 (`backend/app/db/timeline.py`, `GET /tickets/{id}/timeline`)

- 한 줄 = {at, kind, seq, ...}. kind: MESSAGE(SENT·RECEIVED 메시지), STATUS(상태 변경), ALERT_RAISED, ALERT_CLEARED, PRIORITY(조정)(근거: FR-030 처리 4, §8-1 timeline 행, SCR-03 B-01, schema.sql ticket_message·ticket_status_history·sla_alert·priority_adjustment).
- 리마인드는 sender SYSTEM, notice_transition REMINDER인 메시지로 "리마인드 자동 발송 {시각}"이 된다(근거: FR-030 처리 3, FR-023, SCR-03 B-01).
- 시각 오름차순, 같은 시각이면 종류 순서 고정(STATUS → MESSAGE → PRIORITY → ALERT)(근거: SCR-03 B-01 "시각순 한 줄", 같은 시각 순서는 구현 선택).
- 없는 티켓이면 404 "티켓을 찾을 수 없음"(근거: FR-030 예외 1행).

### 3. 분류 직접 수정 (`PATCH /sub-tickets/{id}`, `backend/app/db/edits.py`, `pipeline/reprocess.py`)

- 입력: category_code, urgency_flag, product_code, return_kind, received_fields([{field, value}]), expected_version. 하나 이상 있어야 한다(근거: §8-1 PATCH 행 "유형·긴급도·제품·반품 구분·제공 항목", FR-025 예외 2행 충돌, 모양은 구현 선택).
- 검사: 값은 ref 표(inquiry_category, urgency, product, info_field)에 있어야 하고, 반품 구분은 DEFECT·NON_DEFECT이며 유형이 RETURN일 때만, 받은 항목은 그 문의의 필수 항목이어야 한다. 틀리면 400 "{항목} 값이 올바르지 않음"(근거: schema.sql 외래 키·CHECK, SCR-03 C-01·C-02·C-05·C-07, 문구는 구현 선택).
- 거부: 없는 문의 404, 처리 중 409 "처리 중", 종료(CLOSED) 409 "종료된 문의는 바꿀 수 없음", version이 다르면 409 "다른 사용자가 변경함. 새로고침"(근거: FR-030 예외 2·4행, SCR-03-P3 오류 문구, SCR-03-P8).
- 저장: version + 1, 받은 항목은 inquiry_field(source AGENT) 행, 새 실행 agent_run(sub_ticket_id = 그 문의, trigger AGENT_EDIT)을 응답 전에 연다(근거: §2-4 재처리 "새 run", 테이블 정의서 agent_run.trigger·inquiry_field.source, 17번 다시 시도와 같은 방식).
- 다시 돌기: 첫 노드를 `reuse`로 바꿔 끼운다. 언어 모델을 부르지 않고 그 문의의 지금 값(유형·긴급도·근거 문장·제품·추출 항목)에 고친 값을 얹어 상태를 만들고 규칙 단계(Q2~Q6)부터 초안(Q7 또는 Q8~Q14), 복합이면 T5까지 돈다(근거: FR-030 처리 6 "규칙 단계(그룹 2)를 다시 돌린다", §2-4 부분 재실행, AC-010-3·AC-013-3).
- §2-4는 반품 구분이면 Q4부터, 제공 항목이면 Q5부터라고 하지만 규칙 단계는 같은 입력에 같은 값을 내므로 모두 Q2부터 돌려도 결과가 같다. 하나로 둔다(C-108)(근거: §2-4 부분 재실행 행, 구현 선택).
- 고친 기록: 그 실행의 Q2 단계 input_json에 {"agent_edit": {항목: {from, to}}, "by", "at"}로 남긴다. 상세의 edits는 그 문의의 AGENT_EDIT 실행에서 읽는다(근거: schema.sql agent_step.input_json, CLAUDE.md 규칙 4 새 열 없음, 구현 선택).
- 고친 유형·긴급도는 sub_ticket 열에 남으므로 뒤의 고객 회신 재처리도 그 값을 쓴다. 고른 반품 구분은 규칙(Q4)이 다시 판정하지 않는다(근거: §2-4 고객 회신 재처리 "T2는 다시 부르지 않음", FR-012, 구현 선택).
- 유형을 고치면 "확신 낮음"·"분류 실패" 표시를, 긴급도를 고치면 "긴급도 판정 실패" 표시를 뗀다(근거: FR-005 처리 4, FR-024 확인 표시, 구현 선택).
- 우선순위는 조정(FR-028)이 있으면 조정값을 그대로 둔다(근거: FR-011 예외 3행, C-69).

### 4. 다시 처리 (`POST /tickets/{id}/reprocess`)

- 처리 중이 아니면 언제나 새 RETRY 실행을 연다. 모든 하위 문의가 CLOSED면 409 "종료된 문의입니다"(근거: FR-030 처리 5, §2-4 "횟수 제한 없음", SCR-03 H-05·⑥ 종료, SCR-03-P8 문구).
- 저장 때 접수(INTAKE)가 아닌 모든 실행은 그 문의의 이전 SYSTEM DRAFT(정보 요청·답변)를 superseded로 표시한다. SENT 메시지는 그대로 둔다(근거: §2-4 재처리 행, FR-030 처리 5 "이미 발송한 메시지는 지우지 않는다", C-85·C-98 해소).
- 다시 처리로 하위 문의 수가 줄면 이전 하위 문의 행은 남는다(행을 지우지 않는 저장 규칙). 남은 행은 실행이 없어 상세에 이전 결과로 보인다(C-96 유지, 근거: §6-2 저장 규칙).
- 버튼 이름: 실패면 "다시 시도", 아니면 "다시 처리"(근거: AC-001-4, SCR-03 H-05, C-98).
- 다시 처리는 T2부터 다시 돌지만 상담원이 고친 유형·긴급도·제품·반품 구분과 "받았음" 항목은 언어 모델의 새 판정 위에 다시 덮는다(`reprocess.keep_agent_edits`). 상담원이 고친 뒤 다시 처리를 누르면 그 수정이 반영되어야 하기 때문이다(근거: FR-030 처리 5·6, 구현 선택, C-112).

### 5. 화면 (`frontend/src/TicketDetailPage.tsx` 외)

| 영역 | 내용 | 근거 |
|---|---|---|
| 머리 | 문의 번호·원본·채점용, 대표 상태 배지 + 대표 SLA, 고객사·등급·국가·채널·언어, 처리 상태, [목록으로](마지막 접수함 주소로), [다시 처리]/[다시 시도] | 화면 정의서 v1 SCR-03 H-01~H-05, schema.sql v_ticket_summary, 화면 정의서 v2 부록 B-3 |
| 고객이 보낸 것 | 원문(추출 값 노란 밑줄, 마우스 올리면 항목 이름, 길면 접힘), 제목("처리에는 쓰지 않음"), 채널, 고객 언어/본문 언어, 전화 건 안내, 연락처, 고객 회신 본문 | FR-030 처리 1, SCR-03 L-01~L-04, 예외 5행 |
| 시스템이 판단한 것 | 하위 문의마다 구역 "문의 k/n: 유형" + 상태·SLA 두 시계, 수정 드롭다운(유형 10·긴급도 6·제품·반품 구분), 필수 항목 "받았음", "상담원 수정" 칩, [조정](P3), 기존 근거 줄(고친 유형·긴급도 줄은 첫 근거가 "상담원 수정: 이전 → 새 값", C-117), 실행 기록(runs·steps) | FR-030 처리 2·6, SCR-03 C-01~C-07·C-10·C-11, P3 |
| 보낼 것 | 정보 요청·답변 탭, 하위 문의마다 초안 카드(기존 카드), 초안이 없으면 사유, 이전 초안 접힘. 진행 안내 탭과 [이관]은 "3순위·여유 시"로 비활성 | FR-030 처리 3, SCR-03 R-00·R-06·R-07·R-08 |
| 이력 | timeline 목록(종류 기호, 메시지는 펼치면 본문·보낸 쪽·언어·수정됨), [고객 회신 입력](P6) | FR-030 처리 4, SCR-03 B-01~B-03, P6 |
| 처리 중 | 고객이 보낸 것과 이력만 보이고 나머지 "처리 중", 2초마다 다시 읽기 | FR-030 예외 2행, §8-2 |
| 종료 | "종료된 문의입니다"(무응답 종료면 "무응답 종료"), 버튼 비활성 | 화면 정의서 v1 SCR-03 ⑥ 종료 |
| 충돌·실패 | 409·실패는 P8 "다른 사용자가 변경함. 새로고침" 등 | SCR-03-P8, FR-030 예외 4행 |
| 없는 번호 | 접수함으로 되돌리고 "티켓을 찾을 수 없음" | FR-030 예외 1행 |

- 기본 탭은 "보낼 것"이다(근거: 화면 정의서 v2 0-7절).
- [목록으로]는 접수함이 마지막으로 쓴 주소(필터·정렬·쪽)를 브라우저 세션에 두고 쓴다(근거: SCR-02 ③ "돌아올 때 필터·정렬·페이지 유지", 구현 선택).

### 6. 시험 (`backend/tests/acceptance/test_ticket_detail_full.py`)

- AC-030-1: CSV1-000017 → 원문과 강조할 error_code 값, DEFECT·SITE_DOWN·P1(PR-02)·TS_LV·1h/24h·막는 항목 serial_no, 정보 요청 영어 초안(근거: AC-030-1).
- AC-030-2: 우선순위 "왜?" 재료에 PR-02 규칙 행과 긴급도 근거 문장(근거: AC-030-2).
- AC-030-3: CSV1-000008 → 하위 문의 2개, 각자 근거 문장, 답변 초안이 하위 문의별(근거: AC-030-3).
- AC-030-4: CSV1-000004 → 막는 항목 없음, 프랑스어 답변 초안, 조회값 520 USD·4주(근거: AC-030-4).
- AC-030-5: 유형을 바꿔 저장 → "상담원 수정", 우선순위·부서·필수 항목·SLA 목표가 새 유형으로(근거: AC-030-5).
- 그 밖: AC-013-3(받은 항목 → 막는 항목 빠짐), AC-010-3(제품 선택 → 부서·필수 항목 채워짐), 충돌 409, 처리 중·종료 409, 다시 처리의 superseded, 다시 처리가 상담원 수정을 이어 받음(C-112), timeline 순서·종류, 없는 번호 404(근거: FR-030 처리 5·예외, AC-010-3, AC-013-3, §8-1).
- 화면은 `npm run build`와 브라우저 확인(근거: 17·18번과 같은 방식, 구현 선택).

## Risks / Trade-offs

- C-108: §2-4는 반품 구분 Q4부터, 제공 항목 Q5부터라고 나누지만 모두 Q2부터 돈다. 규칙 단계는 결정적이라 결과가 같다(근거: §2-4 부분 재실행, `app/pipeline/rules_step.py`).
- C-109: 추출 값 위치(span)를 1순위 추출이 채우지 않아 원문에서 값을 찾아 강조한다. 못 찾으면 강조 없이 목록에만 보인다(근거: SCR-03 L-01, schema.sql inquiry_field.span_start).
- C-110: 상담원 수정 기록을 새 열 없이 AGENT_EDIT 실행의 Q2 단계 input_json에 둔다. agent_feedback(FR-043)은 여유 시 기능이다(근거: CLAUDE.md 규칙 4, 테이블 정의서 agent_feedback).
- C-111: 3순위 자리(고장 진단 후보, 이관 후보, [이관], 부서 회신 영역)는 "3순위"로 비활성 자리만 둔다(근거: openspec/config.yaml, FR-030 처리 2·3).
- C-112: [다시 처리]는 처음(T2)부터 다시 돌지만 상담원이 고친 값은 이어 받는다. 나눔이 달라져 그 하위 문의가 없어지면 이어 받을 곳이 없다(근거: FR-030 처리 5·6, 구현 선택).
- C-113: 복합 문의 중 일부만 종료(CLOSED)여도 [다시 처리]는 열린다. 종료된 하위 문의의 값도 새 실행 결과로 다시 써지고 새 초안이 생길 수 있다(상태는 그대로). 모든 하위 문의가 종료일 때만 409다(근거: SCR-03 ⑥ 종료, 구현 선택).
- C-114: 정보 기다림(WAITING_CUSTOMER) 중 상담원이 "받았음"을 눌러 막는 항목이 없어져도 상태는 바꾸지 않는다. 상태 전이는 고객 회신·발송만 한다(근거: FR-028 전이 표, FR-030 처리 6, 구현 선택).
- C-115: PATCH의 expected_version은 빠져도 받는다(FR-028 상태 API와 같이 선택 값). 화면은 늘 보낸다(근거: 기술 명세서 §8-1, FR-030 예외 4행, 구현 선택).
- C-116: 이력 목록의 메시지에는 한국어 풀이를 붙이지 않는다. 풀이는 보낼 것 탭의 초안 카드에만 있다(근거: FR-030 처리 4, SCR-03 B-02 "대역", 구현 선택).
- C-117: 상담원이 고친 유형·긴급도는 근거 줄 C-01·C-02의 첫 근거와 "왜?"에 "상담원 수정"으로 보인다(근거: FR-030 처리 6 "상담원 수정 표시", SCR-03 C-01·C-02, 구현 선택).