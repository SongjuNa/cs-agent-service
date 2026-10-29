# Proposal: 근거 없을 때 상담원이 직접 쓰는 초안 (add-manual-draft)

## Why

티켓 상세의 "보낼 것" 탭에서 초안이 없는 종류는 이유를 보여 주고 빈 편집기에서 상담원이 직접 쓸 수 있어야 한다(근거: 명세서 v1.5 FR-030 처리 3 "초안이 없는 종류는 그 이유를 보여 주고, 빈 편집기에서 직접 쓸 수 있다"). 지금은 이유("근거 없음 — 상담원 작성 필요")만 보이고 쓸 곳이 없다(근거: `frontend/src/TicketDetailPage.tsx` noDraftText, `backend/app/db/store.py` load_draft는 sender SYSTEM·DEPT 초안만 읽음). 화면 정의서 v2 R-06도 "초안이 없을 때 사유 + 빈 편집기 … 빈 편집기에 직접 써서 승인 가능(P7 검사는 똑같이 지남)"이라고 정한다(근거: `docs/technical/screen-specification.md` R-06). FR-030은 2순위로 끝났지만 이 부분만 빠져 있어, 이 변경은 새 기능이 아니라 FR-030 처리 3을 채우는 일이다(근거: openspec/config.yaml 2순위 완료 목록. 착수는 조장 결정 2026-10-29 "FR 있는 것부터", 기록 위치: 프로젝트 스레드 "API 계약 고정하고 목업과 비교", 저장소 밖).

## What Changes

- **빈 초안 만들기**: 상담원이 [직접 작성]을 누르면 그 하위 문의에 INFO_REQUEST 또는 FINAL_REPLY DRAFT(sender AGENT, sent_by_name = X-Agent-Id, language = 티켓 언어)를 만든다(근거: FR-030 처리 3, schema.sql ticket_message_kind_combo "INFO_REQUEST, FINAL_REPLY … DRAFT … sender IN ('SYSTEM','AGENT')", 기술 명세서 v1.4 §8-1 머리 X-Agent-Id).
- **새 API**: `POST /sub-tickets/{sub_ticket_id}/drafts`(message_type, body). 기술 명세서 §8-1 API 목록에는 이 주소가 없다(구현 선택. §8-1에 행을 더할지 조장 확인).
- **임시 저장·승인은 지금 API 그대로**: [임시 저장]은 `PUT /messages/{id}`, [승인]은 `POST /messages/{id}/send`를 쓰고, SENT로 바꾸는 것은 승인 API뿐이다(근거: CLAUDE.md 규칙 3, FR-031 처리 1·4, 기술 명세서 §8-1 send 행).
- **승인 전 검사**: 직접 쓴 초안에도 FR-031 처리 2의 자체 대조와 예외 5행(막는 항목이 남은 답변)의 확인을 그대로 한다. 근거 후보가 없으므로 인용은 늘 근거 밖이고, 숫자는 조회값·부서 회신 숫자에 없으면 근거 밖이다. 걸리면 "확인 필요"가 뜨고 상담원이 "그래도 발송"으로 보낼 수 있다(근거: FR-031 처리 2·예외 5행·AC-031-3, 에이전트 설계서 v1.1 6-1절 "상담원이 직접 쓴 답도 발송 때 같은 검사를 받는다(확정, 가-6)", 화면 정의서 v2 R-06).
- **대역은 저장 때 만들고, 검증 에이전트는 부르지 않는다**: 임시 저장은 지금 PUT 그대로 "본문만 저장 → 대역 다시 만듦, ⑤ = 고친 뒤 검증 안 함"이다(근거: 화면 정의서 v2 R-05, 기술 명세서 v1.4 §8-1 PUT 행, FR-039 처리 4). 검증 에이전트는 시스템이 만든 초안만 대상이므로 자동으로 부르지 않는다(근거: FR-049 처리 8). FR-039 기능 설명은 대역 대상을 "시스템이 만든 초안"이라고 적어 R-05와 다르므로 조장 확인을 받는다.
- **화면**: 초안이 없을 때 이유 문구와 빈 편집기를 바로 보인다(버튼 없음). 첫 [임시 저장]에서 초안이 만들어지고, 그 뒤에는 다른 초안과 같은 편집기·[승인·발송]을 쓴다(근거: 화면 정의서 v2 R-06, FR-030 처리 3).

## Capabilities

### New Capabilities
- `manual-draft`: 상담원이 직접 쓰는 정보 요청·답변 초안.

## 범위 밖

- **직접 쓴 초안의 검증 에이전트 자동 실행**: 하지 않는다. [다시 검증] 버튼을 직접 쓴 초안에도 열지는 조장 확인(근거: FR-049 처리 8).
- **고객 언어와 본문 언어가 다를 때 경고(FR-031 처리 1)**: 이전 변경이 미룬 그대로 둔다(근거: 변경 add-ticket-detail-minimal C-44).
- **진행 안내(PROGRESS_NOTICE) 직접 작성**: 진행 안내는 여유 시 FR-048이다(근거: FR-030 처리 3 "진행 안내 탭은 FR-048(여유 시)을 만들 때 추가").

## Impact

- 새 파일: 시험 `backend/tests/acceptance/test_manual_draft.py`(근거: design 결정 5).
- 고치는 파일: `app/api/sub_tickets.py`(새 주소), `app/api/messages.py`(AGENT 초안의 임시 저장·발송에서 검증 에이전트 건너뛰기 확인), `app/db/store.py`(load_draft가 sender AGENT 초안도 읽음), `app/db/detail.py`(상세 drafts에 AGENT 초안 포함), `app/api/schemas.py`(응답 모델), 화면 `TicketDetailPage.tsx`·`api.ts`·`api.gen.ts`·`openapi.json`(근거: design 결정 1~4).
- DB 구조는 고치지 않는다. 쓰는 행 모양은 테이블 정의서 v1.3에 이미 있다(근거: CLAUDE.md 규칙 4, schema.sql ticket_message_kind_combo).
