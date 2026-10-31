# Proposal: 상담원 도우미 (근거 기반 질의응답) (add-agent-assistant)

> **초안.** 저장소 밖에서 쓴 제안서다. 조장 승인과 팀 검토 뒤에 `openspec/changes/add-agent-assistant/`로 옮긴다. `근거_점검표.md`의 "확인 필요" 항목을 먼저 채운다.

## Why

상담원은 티켓을 처리하다가 문서·사양·정책을 빨리 찾아야 한다. 지금은 문서 화면(SCR-08)에서 직접 찾거나 접수 이력(SCR-09)에서 사례를 검색해야 한다. 목업(상담원 도우미 ELLO)은 질문을 쓰면 문서와 사례를 찾아 문장으로 답하고 출처를 붙이는 대화창이다. 이 프로젝트의 검색 재료(문서 절 색인, 해결사례 색인, 언어 모델 호출 계층)는 이미 있으므로, 그 위에 **근거 안에서만 답하는 질의응답**을 얹는다. 팀 합의로 만든다(2026-10-30, 팀원 동의. 조장 승인 확인 필요).

여유 시 기능은 FR-019와 FR-034만 만든다는 2026-10-29 결정(`openspec/config.yaml`)에 없는 기능이므로, 이 제안서가 새 범위를 요청한다.

## What Changes

- **질문 `POST /assist/ask`**: 상담원이 질문을 보내면 문서 절을 찾고(근거: `backend/app/retrieval/search.py`의 `ref.doc_chunk` 임베딩 검색 방식), 찾은 절 **안에서만** 한국어로 답하고 출처를 붙인다. 근거에 없으면 "찾지 못했습니다"라고 답한다(근거: 에이전트 설계서의 "근거 밖 내용 금지" 원칙, 확인 필요).
- **출처**: 답에 쓴 문서 절의 `chunk_id`, 문서 번호, 절 번호, 제목을 함께 돌려준다. 화면에서 누르면 기존 `GET /chunks/{chunk_id}`로 절 본문을 연다(근거: SCR-03 P2와 같은 길).
- **저장하지 않는다**: 대화 기록은 서버에 남기지 않는다. 이어 묻기는 화면이 직전 대화를 같이 보낸다(근거: CLAUDE.md 규칙 4 새 표 금지, 변경 add-case-search의 "검색 기록 저장 안 함"과 같은 이유).
- **상담원 참고용**: 답은 화면에만 보이고 초안·메시지·고객 발송에 쓰이지 않는다(근거: CLAUDE.md 규칙 3, FR-019 "고객에게 가는 글의 근거로 쓰지 않음"과 같은 원칙).
- **화면**: 오른쪽 아래 떠 있는 도우미 창(임시 번호 SCR-10). 질문 입력, 답 말풍선, 출처 칩, 이어 묻기 추천. 모든 화면에서 열 수 있다(근거: 목업 ELLO, 구현 선택).

## Capabilities

### New Capabilities
- `agent-assistant`: 상담원이 문서 근거로 질문하고 출처가 붙은 답을 받는 API와 화면.

## 범위 밖 (이번 변경에서 하지 않는다)

- **해결사례 함께 찾기(2단계)**: `GET /cases` 색인(`retrieval/cases.py`)을 답의 근거에 더하는 것은 다음 변경으로 미룬다(근거: 일정, 한 번에 하나씩).
- **지금 보는 문의 기준 질문, 한국어 번역(3단계)**: 문의 내용을 프롬프트에 넣는 일은 `<customer_message>` 규칙(규칙 5)과 개인정보 가리기 점검이 더 필요하다. 다음 변경으로 미룬다.
- **대화 기록 저장, 고객에게 보내기, 초안에 붙이기**: 하지 않는다(근거: 규칙 3·4).
- **고객 포털 챗봇**: 별개다. "우리 시스템 밖, 목업 화면으로 둔다"(2026-10-29 조장 답)가 그대로다.

## Impact

- 새 파일: `backend/app/api/assist.py`, `backend/app/llm/assist.py`, `prompts/l11_assist_v2.md`, `backend/app/retrieval/docs_free.py`(범위 제한 없는 문서 검색), 화면 `frontend/src/features/assistant/`, 시험 `backend/tests/acceptance/test_agent_assistant.py`(근거: design 결정 1~5).
- 고치는 파일: `app/main.py`(라우터 등록), `app/api/schemas.py`(응답 모델), 화면 `App.tsx`·`app/AppShell.tsx`·`api.ts`·`api.gen.ts`·`openapi.json`, 화면 명세 `docs/frontend/screens/`(SCR-10 추가, SCR-00 한 줄)(근거: design 결정 4).
- DB 구조는 고치지 않는다(근거: CLAUDE.md 규칙 4).
- 언어 모델 호출이 늘어난다: 질문 1개당 임베딩 1회 + 답 생성 1회(근거: design 결정 2·3).
