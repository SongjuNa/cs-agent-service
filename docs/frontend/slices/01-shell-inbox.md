# 슬라이스 1: 공통 틀(SCR-00) + 접수함(SCR-02)

4단계 첫 슬라이스(근거: 조장 4단계 지시 2026-10-29 "한 화면을 골라 명세 → 구현 계획 → 작업 목록 → 구현 → 실제 API 연결 → 수용 기준 확인"). 발표 흐름 ⓐ(접수)의 시작 화면이라 첫 번째로 고름. 브랜치 `feat/fe-shell-inbox`(로컬 전용, push 안 함).

## 1. 명세

- [SCR-00 공통 틀](../screens/SCR-00-shell.md), [SCR-02 접수함](../screens/SCR-02-inbox.md)
- 원칙: [principles.md](../principles.md). 부품은 `src/ui/`, 값은 `src/styles/tokens.css`
- 목업 배치 기준: v1.42 `updateShell`, `viewInbox` (브라우저에서 계산된 값을 재서 옮김)

## 2. 구현 계획

| 무엇 | 어디 | 어떻게 |
|---|---|---|
| 틀 | `src/app/AppShell.tsx`, `src/app/shell.css` | 목업 머리 막대(남색 64px, ONCE 글자 로고, 대메뉴 4개, 도움말·종), 왼쪽 메뉴 248px(프로필 + 메뉴 묶음 4개 + 접기), 경로 표시. 목업 아이콘은 `src/app/icons.tsx` |
| 상담원·부서·기준 시각 | `src/app/session.tsx` | 프로필을 누르면 뜨는 창(목업 `openMe`)에서 고름. 브라우저 저장소에 기억(principles §4). 요청 머리는 기존 `api.ts` 그대로 |
| 종 알림 | `src/app/Bell.tsx` | `GET /me/workload` risks를 TanStack Query로 읽음(5분 갱신). 1차 응답 경고 먼저, 남은 시간 오름차순, 12건 |
| 주소 나누기 | `src/App.tsx` | 기존 경로(/, /inbox, /intake, /my, /tickets/:id) 그대로. 명세가 아직 없는 메뉴는 "이 화면은 다음 슬라이스" 빈 상태 |
| 접수함 | `src/features/inbox/InboxPage.tsx`, `inbox.css`, `inboxQuery.ts` | 요약(칸막이 탭) → 필터 판 → 표(DataTable) → 쪽 넘김. 필터·정렬·쪽은 주소 쿼리(principles §4), 목록은 `useQuery(["inbox", {...}])`, 5분 갱신, 실패 시 이전 값 흐리게 + 띠 |
| 시험 | `frontend/e2e/*.spec.ts`, `playwright.config.ts` | Playwright로 실제 서버에 붙여 수용 기준 확인(조장 결정 2026-10-29). 실패 상태만 응답을 흉내 냄 |

기존 `InboxPage.tsx`(src 바로 아래)는 지운다. `lastInboxUrl`은 새 위치에서 내보낸다.

## 3. 작업 목록

- [x] 1. 목업 틀·접수함의 계산된 값 재기, 아이콘 뽑기
- [x] 2. 틀: 머리 막대, 왼쪽 메뉴, 프로필 창(부서·상담원·기준 시각), 경로 표시
- [x] 3. 종 알림
- [x] 4. 접수함: 요약·필터·검색·표·정렬·쪽 넘김·빈 상태·실패 상태
- [x] 5. 실제 API 연결 (vite 프록시 /api → 8000)
- [x] 6. Playwright 설치와 수용 기준 시험
- [x] 7. 수용 기준 확인 결과 기록 (아래 4절)

## 4. 수용 기준 확인

2026-10-29, 실제 API(localhost:8000, 데모 9건 접수 + W6 미해결 360건 재생 + 스냅샷 경고) 위에서 `npx playwright test` 13개 모두 통과. 목은 AC-7(목록 요청 실패)에만 `page.route`로 썼다.

| AC | 결과 | 비고 |
|---|---|---|
| SCR-00-AC-1 | 통과 | 명세 예시 이름 `QA_CLAIM_AGENT_01`이 명단(`/ref/agents`)에 없다. 명단의 QA_CLAIM 시연용 상담원(leo)으로 확인. **조장 확인 필요** |
| SCR-00-AC-2 | 부분 통과 | 틀이 보내는 요청(`/me/workload`)의 `X-Agent-Id`로 확인. 쓰기 요청(임시 저장)은 상세 슬라이스에서 시험 |
| SCR-00-AC-3 | 통과 | |
| SCR-00-AC-4 | 통과 | W6 재생 뒤 확인. CSV1-003951의 담당은 명단 이름 zara(운영진 ID → 명단 이름, C-131) |
| SCR-00-AC-5 | 통과 | |
| SCR-02-AC-1 | 통과(숫자는 조장 확인 중) | W6 재생 뒤 TS_LV 담당 67건 확인. 화면 "전체"는 70: 이관받은 2건(CSV1-003280, 003449, FR-029 처리 1)과 데모 접수 1건(CSV1-004004)이 더해짐. AC 문구 67과 처리 1이 어긋남 |
| SCR-02-AC-2 | 통과 | |
| SCR-02-AC-3 | 통과 | CSV1-000008 → CSV1-004003. 하위 1은 TS_ENERGY, 하위 2는 GCS_L1 접수함에 있다 |
| SCR-02-AC-4 | 통과 | |
| SCR-02-AC-5 | 통과 | |
| SCR-02-AC-6 | 통과 | |
| SCR-02-AC-7 | 통과 | 실패 상태만 흉내 냄 |
| SCR-02-AC-8 | 통과 | TS_LV 스냅샷 2쪽에서 확인. 상세의 버튼 이름은 아직 "← 목록으로"(상세 슬라이스에서 [접수함으로]로 바꿈) |

### 확인하며 알게 된 것

- 데모 9건은 원래 접수 시각(2025-10)을 그대로 써서 남은 시간이 −9000h대로 보이고, 경고 4종이 모두 붙는다. 화면 문제가 아니라 데이터 문제다.
- 경고는 주기 점검(스케줄러)이 만들어서, 스케줄러를 끈 채 띄우면 경고 열이 비어 있다. 시험 전에 경고 단계만 한 번 돌렸다(리마인드·자동 종료는 돌리지 않음).
- 목업을 따른 곳(구현 선택): 처리 상태를 배지 대신 글자로, 승인 대기 칩 이름 "승인 대기". 열 순서는 명세를 따름.
- 넣지 않은 것: 프로필 KPI 칸(목업에만 있고 명세에 없음), 빠른 검색(SCR-00-08, v1.42에 없음), 글자 크기·세션 시간·설정·로그아웃(D23), 도움말.

### W6 시연 데이터 재생 (2026-10-29 추가, 브랜치 `feat/demo-replay`)

- 결정: 조장 결정 2026-10-29(1안). `jobs/replay_demo.py` 하나만 CLAUDE.md 규칙 6의 예외로 정답 열(gold.ticket_gold)을 읽는다. 시연 데이터를 한 번 넣는 적재 작업이고, 서비스 실행 코드(backend/app)는 계속 gold.v_inputs만 읽는다.
- 근거: 기술 명세서 v1.4 §9 W6, 테이블 정의서 v1.3 "시연 데이터(W6)", 기능 요구사항 명세서 v1.5 그룹 5 데이터 사실, FR-035 처리 6.
- 상태 이력 순서는 채점 재생(`jobs/replay_gold.py`)과 같은 함수(`events_of`)를 쓴다.
- 결과: 360건, 상태 IN_PROGRESS 237 / ESCALATED 71 / WAITING_CUSTOMER 33 / NEW 19, 스냅샷 해결 SLA ON_TRACK 186 / AT_RISK 34 / BREACHED 140(문의마다 정답과 같음), 담당 TS_LV 67. 시험 `backend/tests/acceptance/test_demo_replay.py` 6개.
- 실행: `python -m jobs.replay_demo`(저장소 루트, backend 경로 포함). 이미 있는 번호는 건너뛴다.
- 백엔드 시험은 기준정보를 다시 적재하므로 시연 DB가 아닌 빈 DB(예: cs_agent_test)에서 돌린다.
