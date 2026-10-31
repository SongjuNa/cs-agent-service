# 추적표: 요구사항 → 화면 명세 → 구현 → 시험 (프론트엔드 SDD 5단계)

작성 2026-10-29. "이 요구사항이 어디에 구현되고 어떻게 검증됐는가"를 한눈에 보는 표다.
화면 시험은 `frontend/e2e/scr-NN.spec.ts`(Playwright, 실제 API), 백엔드 시험은 `backend/tests/acceptance/`(pytest)에 있다.
화면 명세의 수용 기준 번호(SCR-NN-AC-n)가 화면 시험 이름 앞에 그대로 붙어 있어, 번호로 찾으면 된다.

## 1. 수용 기준 덮음 (화면별)

| 화면 | 명세 | 수용 기준 | 화면 시험으로 확인 | 덮지 않은 것 |
|---|---|---|---|---|
| SCR-00 공통 틀 | [SCR-00](screens/SCR-00-shell.md) | 5 | 5 | |
| SCR-01 접수 시뮬레이터 | [SCR-01](screens/SCR-01-intake-simulator.md) | 6 | 6 | |
| SCR-02 접수함 | [SCR-02](screens/SCR-02-inbox.md) | 12 | 12 | |
| SCR-03 티켓 상세 | [SCR-03](screens/SCR-03-ticket-detail.md) | 23 | 23 | AC-22·23은 `scr-03-head.spec.ts` |
| SCR-04 나의 업무 현황 | [SCR-04](screens/SCR-04-my-work.md) | 8 | 8 | |
| SCR-05 전화 상담 | [SCR-05](screens/SCR-05-phone.md) | 6 | 6 | |
| SCR-06 운영 대시보드 | [SCR-06](screens/SCR-06-ops-dashboard.md) | 6 | 0 | 6개 모두. 목업 화면으로 두기로 함(2026-10-29 조장 결정) |
| SCR-07 고객 관리 | [SCR-07](screens/SCR-07-customers.md) | 4 | 4 | |
| SCR-08 기준정보 보기 | [SCR-08](screens/SCR-08-reference.md) | 4 | 4 | |
| SCR-09 접수 이력 | [SCR-09](screens/SCR-09-case-search.md) | 3 | 3 | |
| SCR-10 상담원 도우미 | [SCR-10](screens/SCR-10-assistant.md) | 8 | 8 | 전부 목 응답으로 확인(Gemini 호출 때문). 실제 연결은 [슬라이스 10](slices/10-assistant.md)의 손으로 확인한 것 |
| 합계 | | 85 | 79 | SCR-06 6개 |

- 목(흉내 낸 응답)은 오류·빈 상태 시험에만 썼다: SCR-01-AC-4, SCR-02-AC-7, SCR-03-AC-5·7·12·20, SCR-05-AC-6, SCR-08-AC-1("색인 없음" 문서가 시연 DB에 없음). SCR-10은 8개 모두 목(답마다 Gemini를 부름).
- AC가 아닌 화면 시험 2개: SCR-08 「왜?」 → [규칙표에서 보기], SCR-09 티켓 상세 → [접수 이력에서 보기].
- SCR-03-AC-19는 5단계에서 "일부"를 풀었다. ② 탭의 비슷한 해결사례(3건 이하, 팀 정답지 사례 없음)를 000017 사본에서 본다.

## 2. 요구사항 → 화면 → 구현 → 시험

구현 경로는 `frontend/src/` 아래. 백엔드 시험은 같은 요구사항의 API·처리를 본다.

| 요구사항 | 내용 | 화면·요소 | 구현 컴포넌트 | 화면 시험 | 백엔드 시험 |
|---|---|---|---|---|---|
| D23·D33 | 상담원 고르기, 요청 머리 | SCR-00 | `app/AppShell.tsx`, `app/session.tsx` | SCR-00-AC-1·2·3·5 | test_agent_roster |
| FR-027 | SLA 위험 경고(종 알림) | SCR-00 종 | `app/Bell.tsx` | SCR-00-AC-4 | test_sla_alert |
| FR-001 | 문의 접수 | SCR-01 | `features/intake/IntakePage.tsx` | SCR-01-AC-2·3·4·6 | test_intake_simulator |
| FR-003 | 시연용 티켓 불러오기 | SCR-01 불러오기 | `features/intake/IntakePage.tsx` | SCR-01-AC-1 | test_intake_simulator |
| FR-006 | 복합 문의 나누기 | SCR-01 ③, SCR-02 유형, SCR-03 문의 칸 | `IntakePage.tsx`, `features/inbox/InboxPage.tsx`, `ticket/SystemTab.tsx` | SCR-01-AC-5, SCR-02-AC-3, SCR-03-AC-3 | test_compound_inquiry |
| FR-029 | 접수함 | SCR-02 | `features/inbox/InboxPage.tsx` | SCR-02-AC-1~8 | test_inbox |
| FR-030 | 티켓 상세 | SCR-03 탭 ①~④ | `ticket/TicketPage.tsx`, `CustomerTab.tsx`, `SystemTab.tsx`, `SendTab.tsx`, `HistoryTab.tsx`, `HeadCard.tsx` | SCR-03-AC-1·2·3·21 | test_ticket_detail_full |
| FR-024 | 근거 표시 | SCR-03 ② 「왜?」(P1), ③ 인용 | `ticket/Popups.tsx`, `ticket/DraftCard.tsx` | SCR-03-AC-2·5·6 | test_ticket_detail |
| FR-039 | 초안 대역 | SCR-03 ③ | `ticket/DraftCard.tsx` | SCR-03-AC-4·11·12 | test_drafts, test_ticket_detail |
| FR-049 | 검증 에이전트 | SCR-03 ③ 검토 표시 ⑤ | `ticket/DraftCard.tsx`, `ticket/Popups.tsx` | SCR-03-AC-7·11 | test_verification |
| FR-031 | 초안 수정·승인·발송 | SCR-03 ③, P7·P8 | `ticket/DraftCard.tsx`, `ticket/Popups.tsx` (P7·P8) | SCR-03-AC-8·9·10 | test_ticket_detail, test_status_sla |
| FR-028 | 우선순위 조정·SLA 재계산 | SCR-03 P3 | `ticket/ActionPopups.tsx` | SCR-03-AC-13·14 | test_priority_override |
| FR-033 | 이관 처리 | SCR-03 P4, 부서 회신 | `ticket/ActionPopups.tsx`, `ticket/DeptWriter.tsx` | SCR-03-AC-15·16 | test_escalation, test_dept_reply |
| FR-032 | 고객 회신 입력 | SCR-03 P6 | `ticket/ActionPopups.tsx` | SCR-03-AC-17·18 | test_customer_reply |
| FR-019 | 유사 해결사례 | SCR-03 ② "비슷한 해결사례", SCR-09 | `ticket/SystemTab.tsx`, `features/cases/CaseSearchPage.tsx` | SCR-03-AC-19, SCR-09 연결 시험 | test_similar_cases |
| R-06 (add-manual-draft) | 근거 없음 → 직접 작성 | SCR-03 ③ | `ticket/SendTab.tsx` | SCR-03-AC-20 | test_ticket_detail_full |
| FR-047 | 나의 업무 현황 | SCR-04 | `features/mywork/MyWorkPage.tsx` | SCR-04-AC-1~8 | test_my_work |
| FR-050 | 통화 받아쓰기·메모 초안 | SCR-05 | `features/phone/PhonePage.tsx` | SCR-05-AC-1~6 | test_call_transcription |
| FR-034, FR-초안-05 | 운영 대시보드 | SCR-06 | 목업 화면(구현 안 함) | 없음 | 없음 |
| FR-초안-01 | 고객 관리 | SCR-07 | `features/customers/CustomersPage.tsx` | SCR-07-AC-1~4 | test_customer_views |
| FR-초안-02 | 문서 보기 | SCR-08 문서 관리 | `features/reference/ReferencePages.tsx` (DocsPage) | SCR-08-AC-1·4 | test_reference_views |
| FR-초안-03 | 제품 보기 | SCR-08 제품 관리 | `ReferencePages.tsx` (KnowledgePage) | SCR-08-AC-2 | test_reference_views |
| FR-초안-04 | 규칙·부서 보기 | SCR-08 규칙·부서·기타 | `ReferencePages.tsx` (KnowledgePage), `ui/DataTable.tsx` 강조 | SCR-08-AC-3, 「왜?」 연결 시험 | test_reference_views |
| FR-초안-06 | 해결사례 직접 검색 | SCR-09 | `features/cases/CaseSearchPage.tsx` | SCR-09-AC-1~3 | test_case_search |
| FR-초안-07 (임시) | 상담원 도우미(문서 근거 질의응답) | SCR-10 | `features/assistant/AssistantDock.tsx`, `app/AppShell.tsx` | SCR-10-AC-1~8 | test_agent_assistant |

화면에 직접 보이지 않는 요구사항(FR-004·005·007·008 문의 이해, FR-016·017 근거 검색, FR-018 고장 진단, FR-020 이관 후보, FR-023 리마인드, FR-025·026 상태·SLA, FR-036 실행 로그, FR-038 가리기, 규칙 엔진)은 백엔드 시험에서만 확인한다. 화면은 그 결과 값을 그대로 보이는지만 본다(SCR-03-AC-1).

## 3. 목업과 나란히 비교

`frontend/scripts/mockup-compare.mjs`가 화면마다 목업 v1.42와 구현 화면을 같은 크기(1440×900, 첫 화면)로 찍어 한 장에 붙인다. 목업 파일은 저장소에 없어 경로를 넘긴다.

```
cd frontend
MOCKUP=<목업 html 경로> OUT=<저장 폴더> node scripts/mockup-compare.mjs
```

2026-10-29 결과(11장). 값과 문구는 기준 문서를 따르므로 목업과 달라도 정상이다. 아래는 **배치**만 본 것이다.

| 화면 | 배치 | 눈에 띈 차이 |
|---|---|---|
| 공통 틀 | 맞음 | 왼쪽 메뉴: 처음 비교에서 구현이 모든 묶음을 한꺼번에 보였다. 조장 결정(2026-10-29 "목업처럼 맞춥니다")으로 위 탭(접수·지식 관리 등)의 묶음 하나만 보이게 고쳤다. 상단 막대의 글자 크기·세션·로그아웃 단추는 없음(로그인 없음 D23) |
| SCR-01 접수 시뮬레이터 | 맞음 | 입력 카드 너비는 목업과 같다(둘 다 820px. 처음 비교 때 "구현이 더 넓다"고 본 것은 잘못 봄). 고객 언어 칸이 더 있어 카드가 길다(명세) |
| SCR-02 접수함 | 맞음 | 요약 탭 → 거르기 상자 → 표 순서 같음 |
| SCR-03 티켓 상세 | 맞음 | 머리 카드 → 경고 띠 → 탭 4개 같음. 원문 옆 한국어 번역 칸은 없음(Q1) |
| SCR-04 나의 업무 현황 | 맞음 | 숫자 줄 → 탭 같음. 처리 실적 차트는 없음(Q2), 기한 위험·위반 탭이 있음(Q3) |
| SCR-05 전화 상담 | 다름(명세대로) | 목업은 실시간 통화, 구현은 통화 뒤 녹음 올리기 흐름(Q7). 왼쪽 대화·오른쪽 판단·필수 정보 나눔은 같음 |
| SCR-07 고객 관리 | 맞음 | 등급 요약 → 검색 상자 → 표 같음. "미해결 문의 있는 고객만" 칸은 없음 |
| SCR-08 기준정보(문서·규칙·제품·부서) | 맞음 | 탭 → 검색 → 표 같음. [표 올리기]는 없음(SCR-08-AC-4) |
| SCR-09 접수 이력 | 맞음 | 안내 띠 → 거르기 상자 → 표 같음. 제외 단추·참고 횟수 없음(Q8) |
| SCR-06 운영 대시보드 | 비교 안 함 | 목업 화면으로 둠 |

## 4. 전체 시험 결과 (2026-10-29)

- 화면 시험 전체 실행(`cd frontend && npx playwright test`): 66개 모두 통과(6.7분, 실제 API·실제 Gemini). 그 뒤 SCR-03-AC-19를 둘로 나눠(인용 쪽은 시연 티켓, ② 탭은 000017 사본 A) 바뀐 묶음 5개를 다시 돌려 통과. 지금 화면 시험은 67개다.
- 상태를 바꾸는 시험은 정답지 문의 사본을 새로 접수하므로 시연 DB에 티켓이 쌓인다(접수함 TS_LV 수가 늘어남). 시연 전에 정리한다.
- 백엔드 시험: 364 통과, 1 건너뜀, 2 실패(앞 슬라이스부터 흔들리는 Gemini 실시간 시험 test_ac_021_2_live, test_ac_005_1_categories[CSV1-000031-MANUAL]).
