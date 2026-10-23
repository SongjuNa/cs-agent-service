# Proposal: 티켓 상세 전체판 (add-ticket-detail-full)

## Why

티켓 상세는 시연의 중심 화면이다. 고객이 보낸 것, 시스템이 판단한 것과 근거, 보낼 글, 이력을 한 화면에서 보고 승인·조정·회신 입력 버튼도 여기서 누른다(근거: 명세서 v1.5 FR-030 기능 설명, 화면 정의서 v1 SCR-03 ① 목적). 1순위 최소판(SCR-03M)은 첫 하위 문의 하나의 판단값·근거와 초안만 보이고, "고객이 보낸 것"·"이력" 탭은 비활성이다(근거: 화면 정의서 v2 0-7절 1순위 최소판 표, 이 변경 전 `frontend/src/TicketDetailPage.tsx`). 상담원이 분류를 고치는 API와 실패가 아닌 티켓의 다시 처리도 없다(근거: 기술 명세서 v1.4 §8-1 PATCH /sub-tickets 행, 개발 결정 기록 C-85·C-98).

## What Changes

- **상세 묶음 더하기 (FR-030 처리 1·2)**: `GET /tickets/{id}`에 원문 본문·제목·보낸 사람 연락처, 하위 문의별 추출 값(위치 포함), "상담원 수정" 표시를 더한다(근거: FR-030 처리 1·6, 화면 정의서 v1 SCR-03-L L-01~L-04, 기술 명세서 §8-1 GET /tickets/{id} 행).
- **이력 API (FR-030 처리 4)**: `GET /tickets/{id}/timeline`이 메시지·상태 변경·경고 발생/해제·우선순위 조정을 시각순 한 줄 목록으로 돌려준다(근거: FR-030 처리 4, 기술 명세서 §8-1 timeline 행, 화면 정의서 v1 SCR-03-B B-01).
- **분류 직접 수정 (FR-030 처리 6, AC-030-5)**: `PATCH /sub-tickets/{id}`로 유형·긴급도·제품·반품 구분·받은 항목을 고치면 그 하위 문의를 새 실행(trigger AGENT_EDIT)으로 규칙 단계부터 다시 돌린다(근거: FR-030 처리 6, AC-030-5, 기술 명세서 §2-4 부분 재실행, §8-1 PATCH 행, 테이블 정의서 agent_run.trigger).
- **다시 처리 (FR-030 처리 5)**: `POST /tickets/{id}/reprocess`를 실패가 아닌 티켓에도 연다. 새 실행에서 이전 DRAFT는 superseded로 표시하고 발송한 메시지는 지우지 않는다(근거: FR-030 처리 5, 기술 명세서 §2-4 재처리 행, 화면 정의서 v1 SCR-03 H-05).
- **화면 (SCR-03)**: A안 탭 4개를 모두 켠다. 고객이 보낸 것(원문·추출 값 강조·연락처·회신), 시스템이 판단한 것(하위 문의마다 구역, 수정 드롭다운, [조정] 팝업, 실행 기록), 보낼 것(하위 문의별 초안 카드), 이력(시각순 목록, [고객 회신 입력] 팝업). 머리에 상태·SLA, [목록으로]·[다시 처리](근거: 화면 정의서 v1 SCR-03 H·L·C·R·B, P3·P6·P8, 화면 정의서 v2 0-7절·부록 B-2, FR-030 처리 1~5).

## Capabilities

### New Capabilities
- `ticket-detail`: 티켓 상세 전체판(상세 묶음 더하기, 이력, 분류 수정, 다시 처리, 화면).

## 범위 밖

- **고장 진단 후보·이관 후보(C-08·C-09)·[이관] 버튼·부서 회신 영역**: FR-018·020·033은 3순위다. 화면에 자리만 두고 "3순위"로 비활성(근거: openspec/config.yaml 3순위, FR-030 처리 2·3의 3순위 연결 지점, 화면 정의서 v1 SCR-03 C-08·C-09·R-07·B-03).
- **진행 안내 탭, 고객 원문 번역 토글, 유사 사례**(근거: FR-030 처리 3 "FR-048(여유 시)", 9번, 화면 정의서 v1 SCR-03 ⑨).
- **agent_feedback 기록**(FR-043 여유 시 4순위)(근거: 명세서 FR-043, 기술 명세서 §6-2 "MVP는 쓰지 않는다").

## Impact

- 새 파일: `backend/app/db/timeline.py`, `backend/app/db/edits.py`, 시험 `backend/tests/acceptance/test_ticket_detail_full.py`, 화면 `frontend/src/DetailTabs.tsx`(고객이 보낸 것·시스템이 판단한 것·이력 탭), `frontend/src/ActionPopups.tsx`(조정 P3·고객 회신 P6)(근거: design 결정 1~5).
- 고치는 파일: `backend/app/db/detail.py`, `backend/app/api/tickets.py`, `backend/app/api/sub_tickets.py`, `backend/app/db/store.py`, `backend/app/db/runs.py`, `backend/app/pipeline/reprocess.py`, `backend/app/pipeline/state.py`, `backend/app/pipeline/rules_step.py`, `frontend/src/TicketDetailPage.tsx`·`App.tsx`·`api.ts`·`Popups.tsx`·`InboxPage.tsx`·`styles.css`(근거: design 결정 1~5).
- DB 구조는 고치지 않는다. 상담원 수정 기록은 기존 열(agent_run.trigger AGENT_EDIT, agent_step.input_json, inquiry_field.source AGENT)에 둔다(근거: CLAUDE.md 규칙 4, schema.sql svc.agent_run·agent_step·inquiry_field).
