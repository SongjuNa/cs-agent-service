# 슬라이스 10: 상담원 도우미(SCR-10)

문서 근거로 묻고 출처가 붙은 답을 받는 도우미. 브랜치 `feat/add-agent-assistant`(`main`에서 갈라짐, 로컬 전용, push 안 함). 변경 `add-agent-assistant`(FR 번호는 임시 FR-초안-07, 요구사항 명세서 반영 여부는 팀 확인 필요).

## 1. 명세

- [SCR-10 상담원 도우미](../screens/SCR-10-assistant.md). 변경 `openspec/changes/add-agent-assistant/`
- 원칙: [principles.md](../principles.md). 부품은 `src/ui/`, 값은 `src/styles/tokens.css`
- 화면 모양은 목업의 도우미(ELLO)를 따랐고, 답의 내용·출처 규칙은 저장소의 기존 방식을 따랐다.
- 범위는 1단계(문서 근거 질의응답)만이다. 해결사례 함께 찾기, 지금 보는 문의 기준 질문, 번역은 하지 않는다.

## 2. 구현 계획

| 무엇 | 어디 | 어떻게 |
|---|---|---|
| 검색 | `backend/app/retrieval/docs_free.py` | 범위 제한 없는 문서 절 검색. 임베딩 유사도 + 질문에 든 오류 코드·버전·제품 코드가 절에 있으면 +0.2, 상위 5개. 제품 코드가 있으면 그 제품 + 정책 + 제품군 FAQ |
| 답 만들기 | `backend/app/llm/assist.py`, `prompts/l11_assist_v2.md` | `generate_json` 하나(호출 이름 Q15). 출처 번호 위조는 버리고, 출처 없는 답은 found=false, 답의 숫자가 쓴 출처에 없으면 notes. 실패하면 찾은 절만 돌려줌 |
| API | `backend/app/api/assist.py`, `schemas.py`, `main.py` | `POST /assist/ask`. 아무것도 저장하지 않음 |
| 화면 | `src/features/assistant/AssistantDock.tsx`, `assistant.css`, `app/AppShell.tsx`, `api.ts` | 오른쪽 아래 "도우미" 창. `useMutation`, 대화는 `useState`, 출처 칩은 기존 절 본문 팝업 재사용 |
| 시험 | `backend/tests/acceptance/test_agent_assistant.py`(9개), `test_api_contract.py`(36 → 37), `e2e/scr-10.spec.ts`(7개) | 아래 4절 |

## 3. 작업 목록

- [x] 1. 제안서·설계서·작업 목록(`openspec/changes/add-agent-assistant/`)
- [x] 2. 검색, 답 만들기, API, 응답 모델, 서버 시험 9개
- [x] 3. 화면 명세 SCR-10, 도우미 창, `api.gen.ts` 다시 만들기
- [x] 4. Playwright 수용 기준 시험
- [ ] 5. 팀 확인: 조장 승인, FR 번호, 호출 번호 중복 점검 (`tasks.md` 0.1~0.3)
- [ ] 6. 수동 품질 확인 기록 (`tasks.md` 4.1~4.2)

## 4. 수용 기준 확인

화면 시험 7개(AC 8개)는 **모두 목 응답**이다. 다른 슬라이스는 실제 API를 쓰지만, 이 화면은 답마다 Gemini를 부르므로 시험이 흔들리지 않게 `POST /api/assist/ask`와 절 본문을 `page.route`로 대신했다. 서버 쪽 동작(출처 검사, 가리기, 저장 안 함, 실패 시 절 목록)은 `test_agent_assistant.py`가 실제 DB로 확인한다. 실제 서버·실제 Gemini 연결은 아래 손으로 확인한 것으로 대신한다.

| AC | 시험 | 결과 |
|---|---|---|
| SCR-10-AC-1 | 도우미를 누르면 창이 열린다 | 통과 |
| SCR-10-AC-2·3 | 근거 있는 답에 출처 칩, 누르면 절 본문 | 통과 |
| SCR-10-AC-4 | 근거 없으면 "찾지 못했습니다", 칩 없음 | 통과 |
| SCR-10-AC-5 | 서버 오류 시 [다시 시도] | 통과 |
| SCR-10-AC-6 | 400이면 입력 칸 아래 문구, 보낸 글 유지 | 통과 |
| SCR-10-AC-7 | 이어 묻기 칩이 직전 대화와 함께 전송 | 통과 |
| SCR-10-AC-8 | [새 대화]로 목록 비움 | 통과 |

### 손으로 확인한 것 (2026-10-31, 실제 서버·실제 Gemini)

- 질문 14개를 돌려 답을 문서와 대조했다: 보증 기간, 변압기 보증 조건, RMA 절차, 환불 약속 여부, E.OC 원인과 조치 등은 출처와 조건을 지켜 답했고, 점심 메뉴·올해 매출·문서에 없는 주제(차단기 트리핑, 펌웨어 후 통신 끊김, 배송 지연 보상)는 "찾지 못했습니다"로 답했다(출처 없음).
- 브라우저에서 "E.OC 오류 코드 원인과 조치"를 물어 답, 출처 칩 5개, 이어 묻기 칩 3개가 나왔고, 출처 칩 누르기와 이어 묻기 칩 누르기가 동작했다.

### 확인하며 알게 된 것

- "과전류"처럼 오류 코드 없이 물으면 E.OC와 연결하지 못해 못 찾을 수 있다. 코드를 넣으면 찾는다. 고치려면 검색 점수 방식을 손봐야 하는데 이 변경 범위 밖이다.
- 프롬프트 v1은 E.OC 답에 RMA 요건을 모든 E.OC에 일반화했다. v2에서 조건을 그대로 두도록 고쳤다(v1 파일은 남김).
- 모델 이름의 숫자(예: iS7)가 "근거 밖 숫자"로 잘못 잡혀, 숫자 검사에서 모델 이름 속 숫자를 뺐다(시험 있음).
- 백엔드 전체 시험에서 실패 2개는 슬라이스 9에도 적힌 Gemini 실시간 시험(`test_ac_021_2_live`, `test_ac_005_1_categories[CSV1-000031-MANUAL]`)이다. 이 변경과 무관해 보인다. `main`에서 다시 돌려 본 것은 아니다.
- 목업 대비 배치 비교(`mockup-compare.mjs`)는 이 화면에서 돌리지 않았다.
