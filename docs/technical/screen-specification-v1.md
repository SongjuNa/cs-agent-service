# 화면 정의서 v1 — 해외고객향 C/S 대응 AI Agent (핵심 MVP)

| 항목 | 내용 |
|---|---|
| 작성일 / 버전 | 2026-10-20 / v1 (팀 공유 전 초안, 조장 검토용) |
| 바탕 문서 | **화면 목록(핵심 MVP 기준) — 화면 정의서 작성용** `bootcamp/기획서/화면_목록_MVP_v1.md` (화면 4개 + 공통 1 + 팝업 9개, 화면마다 9개 항목) |
| 근거 문서(원본 파일명) | 기능 요구사항 명세서 v1.4 `기능_요구사항_명세서_v1.4.md` (FR-001·003·024·028·029·030·031·032·033·039·047) · 기술 명세서 v1.3 `기술_명세서_v1.3.md` (§5-7 검토 표시, §6-4 상태·SLA·스케줄러, §8-1 API, §8-2 화면 4개, §8-3 나의 업무 현황 값 출처) · 사용자 시나리오 v1 `사용자_시나리오_v1.md` · 화면 목업 3안 `bootcamp/mockup/화면목업_3안_2026-10-20/` · 디자인 가이드 `화면시안/LS_CI_디자인_가이드.md` |
| 데이터 출처 표기 | 화면에 보이는 값마다 "표.열" 또는 "파일.열"을 적었다. 서비스 표(ticket, sub_ticket, ticket_message, ticket_status_history, sla_alert, self_check, priority_adjustment, message_gloss)는 테이블 정의서, 규칙표는 `data/CS_AI_Agent_Training_Data_v1/ref/`의 CSV |
| 이 문서가 정하는 것 | 화면·팝업마다 ① 목적 ② 사용자 ③ 들어오는 길·나가는 길 ④ 영역과 요소(요소 ID) ⑤ 버튼·동작 ⑥ 상태 변형 ⑦ 보이는 데이터와 출처 ⑧ 근거 FR·AC ⑨ MVP 밖 요소. 레이아웃(사이드바형·상단막대형·분할형)은 정하지 않는다(목업 3안에서 고른다) |

---

## 0. 공통 규칙

### 0-1. 용어
**화면(SCR)** 주소가 있는 한 페이지. **팝업(P)** 화면 위에 뜨는 창, 부모 화면 ID 뒤에 붙인다. **영역** 화면 안의 큰 구역(H 머리, L 왼쪽, C 가운데, R 오른쪽, B 아래). **요소 ID** `SCR-03-C-04`처럼 화면-영역-번호. **상태 변형** 같은 화면이 상황(빈 목록, 처리 중, 오류)에 따라 다르게 보이는 것. **티켓** 고객 메일 1통, **하위 문의(요청)** 그 안에서 나눈 문의 1개(sub_ticket_id = `CSV1-000008-1`). 화면 글자는 기획서 표현(문의 상세·요청·처리 기한), 작은 회색 보조 글자와 이 문서의 출처 칸은 명세서·데이터 표현(ticket_id, sla_first_response_target_h)을 쓴다(화면 목록 §6-5).

### 0-2. 화면 목록 §6 "정의서를 쓰기 전에 정할 것" 반영
| # | 질문 | 이 정의서의 결정 | 근거 |
|---|---|---|---|
| 1 | 126시간 리마인드를 승인 대기 카드로 둘지, 자동 발송으로 둘지 | **자동 발송.** 스케줄러가 고정 문안으로 만들어 바로 SENT. 화면에는 이력 띠 "리마인드 자동 발송 {시각}"과 접수함·업무 현황의 "리마인드 발송됨" 표시만. 승인 대기 카드는 두지 않는다 | 기술 명세서 v1.3 §6-4 주기 점검 2, §3-1, FR-023·D29(조장 확인 2026-10-20: 고객에게 가는 것은 승인 발송과 리마인드뿐). 화면 목록 §6-1 기본안(승인 대기 카드)과 다르므로 조장 확인 필요 |
| 2 | 담당 상담원 저장 위치 | `sub_ticket.assignee_masked`. 요청 머리 `X-Agent-Id`로 "내 담당"을 거른다. 상담원을 고르지 않고 부서만 고르면 부서 전체 | 기술 명세서 §8-3, T43, D33 |
| 3 | 나의 업무 현황 영역 5개 중 MVP | **5개 모두** | FR-047 "조장 확인 3(2026-10-20): 영역 5개 모두" |
| 4 | 여유 시 관리자 대시보드 위치 | SCR-04에 "전체 보기" 스위치(화면 수 안 늘림). API는 `GET /dashboard/*` | 화면 목록 §6-4 기본안, 기술 명세서 §8-1 |
| 5 | 화면 이름 표기 | 그대로(0-1) | 화면 목록 §6-5 |

### 0-3. 공통 부품(기술 명세서 §8-2 "공통 부품을 먼저 만든다")
| 부품 ID | 이름 | 보이는 것 | 출처 |
|---|---|---|---|
| CP-1 상태 배지 | 하위 문의 상태 6개 | NEW 회색 테두리 / IN_PROGRESS 파랑 / WAITING_CUSTOMER 회색 / ESCALATED 보라 / RESOLVED 초록 / CLOSED 연회색 | sub_ticket.status |
| CP-2 SLA 두 시계 | 1차 응답 / 해결 | 각각 "목표 24h · 경과 3.5h · 남은 20.5h" + 상태색: ON_TRACK 초록, AT_RISK 노랑, BREACHED 빨강, MET 초록 체크, N/A 없음. 해결 시계는 WAITING_CUSTOMER 동안 "멈춤" 아이콘. 1차 응답에는 AT_RISK가 없다 | `inquiry_sla(as_of)` (fr_target, fr_elapsed, fr_status, res_target, res_elapsed, res_status, remaining_h). 소수 첫째 자리, 넘으면 음수 "−12.5h" |
| CP-3 "왜?" 팝오버 | 값 옆 작은 버튼 | 누르면 SCR-03-P1 | agent_step.output_json, 규칙 행 |
| CP-4 출처 링크 | 초안 안 `(DOC_ID §n.m)`과 숫자 | 누르면 SCR-03-P2 | sub_ticket.evidence_json, lookups |
| CP-5 초안 + 대역 편집기 | 왼쪽 편집 가능한 초안(고객 언어), 오른쪽 읽기 전용 대역(ko/en 전환), 자체 대조 불일치 위치 노란 강조 | ticket_message(DRAFT), message_gloss, self_check(DRAFT_CHECK) |
| CP-6 이관 사유 선택 | 11값 드롭다운 | escalation_reason 코드(ONSITE_REQUIRED, QUALITY_RETURN, RMA_REQUIRED, COMMERCIAL_TERMS, CAUSE_ANALYSIS, FW_UPDATE_FAILURE, SPEC_INTERPRETATION 등 정답지 값) | tickets.csv escalation_reason 고유값 |
| CP-7 검토 표시 줄 | 초안 카드 위 한 줄 | "검사 4개 통과" 또는 "② 걸림: 제조번호(serial_no) 없음" | `GET /tickets/{id}`의 review_marks (저장 안 함, §5-7) |
| CP-8 AI 제안 / 사람 확정 구분 | 파란 "AI 제안" 칩 / 초록 "상담원 조정·수정·입력" 칩 | 디자인 가이드 §7.2. 신뢰도 숫자는 쓰지 않는다(§7.4) | priority_adjustment, "상담원 수정" 표시 |

### 0-4. 공통 동작
- **시각**: 저장은 UTC, 표시는 "2026-04-20 17:55 UTC". 기준 시각(as_of)은 상단 막대에서 "실제 시각 / 스냅샷 2026-09-30 23:59 UTC" 전환.
- **자동 갱신**: 접수함·나의 업무 현황은 진입·새로고침 때와 5분마다. 문의 상세는 처리 중일 때만 2초마다 `GET /tickets/{id}`, 끝나면 멈춤(기술 명세서 §2-4).
- **상담원 식별**: 로그인 없음. 상단 막대의 이름·부서를 모든 요청 머리 `X-Agent-Id`, `X-Agent-Dept`에 싣는다(D23·D33). 브라우저에 기억.
- **읽기 실패**: 이전 값을 흐리게 유지하고 "불러오지 못함. 새로고침" 띠.
- **발송 관문**: 고객에게 가는 글은 모두 [승인·발송] → SCR-03-P7 발송 전 확인을 지난다(D32). 예외는 126h 리마인드뿐.

---

## SCR-00. 공통 상단 막대

| 항목 | 내용 |
|---|---|
| ① 목적 | 모든 화면 위에 떠서 "누가(상담원·부서), 언제(기준 시각) 보고 있는지"를 정하고 화면 사이를 옮긴다 |
| ② 사용자 | 전원 |
| ③ 길 | 항상 표시. 메뉴 4개: 접수함(SCR-02, 기본) / 나의 업무 현황(SCR-04) / 접수 시뮬레이터(SCR-01) / (여유 시) 운영 대시보드 |
| ⑧ 근거 | D23(로그인 대신 선택), D33(X-Agent-Id), 화면 목록 §2 SCR-00 |
| ⑨ MVP 밖 | 실제 로그인·권한. 운영 대시보드 메뉴(FR-034) |

④ 영역과 요소
| 요소 ID | 종류 | 표시 | 출처 | 동작 |
|---|---|---|---|---|
| SCR-00-01 | 로고·서비스 이름 | 로고 자리(승인된 에셋만, 가이드 §4) + 이름(R1 결정 뒤) | — | 누르면 접수함 |
| SCR-00-02 | 상담원 이름 | 자유 입력, 예 TS_LV_AGENT_09 | tickets.csv assignee_masked 132명 중 하나를 권장 | 바꾸면 접수함·업무 현황 다시 그림 |
| SCR-00-03 | 부서 선택 | 13개 드롭다운(코드 + 이름) | departments.csv dept_code, dept_name | 같음 |
| SCR-00-04 | 기준 시각 | "실제 시각" / "스냅샷 2026-09-30 23:59 UTC" 토글 + 현재값 | 설정 | 모든 조회의 as_of |
| SCR-00-05 | 메뉴 4개 | 접수함 / 나의 업무 현황 / 접수 시뮬레이터 / 운영 대시보드(비활성) | — | 화면 이동. 현재 화면 강조 |

⑥ 상태 변형: 이름·부서 미선택 → 접수함·업무 현황이 "상단에서 이름과 부서를 고르세요" 안내만 보임(FR-047 예외). 접수 시뮬레이터는 부서 없이도 열린다.

---

## SCR-01. 접수 시뮬레이터

| 항목 | 내용 |
|---|---|
| ① 목적 | 메일·채팅·전화·포털 연동 대신 시연·테스트 담당자가 문의를 입력해 티켓을 만들고 처리 흐름을 시작한다. 기본 동작은 "문의 번호로 불러오기"(FR-003) |
| ② 사용자 | 시연·테스트 담당자(상담원 업무 아님, FR-001 3) |
| ③ 길 | 상단 메뉴 → 접수 성공 시 SCR-03으로 이동(FR-001 처리 5). [목록으로] → SCR-02 |
| ⑧ 근거 | FR-001 (AC-001-1~4), FR-003 (AC-003-1~3), D25(미등록 고객 거부), D30(4,000건 전부 + 팀 정답지 문의 불러오기, 채점용 표시) |
| ⑨ MVP 밖 | 접수 경로별 입력 양식(FR-002), 외부 연계(FR-037) |

④ 영역과 요소
| 요소 ID | 종류 | 표시·입력 | 필수 | 검증 | 출처 |
|---|---|---|---|---|---|
| SCR-01-01 | 안내 띠 | "시연·테스트 담당자용 · 채널 연동 대체" | — | — | — |
| SCR-01-02 | [문의 번호로 불러오기] 버튼 | → SCR-01-P1 | — | — | — |
| SCR-01-03 | 채널 | 드롭다운 5값 | 필수 | EMAIL, CHAT, PHONE, WEB_FORM, PARTNER_PORTAL | tickets.csv channel |
| SCR-01-04 | 고객 | 검색 선택(ID·회사명·국가·등급) | 필수 | customers.csv에 있어야 함(D25) | `GET /ref/customers?q=` → customers.csv customer_id, company_masked, country, tier |
| SCR-01-05 | 제품 코드 | 검색 선택 23종 | 선택 | product_master.csv 23종. 비우면 본문에서 찾음(FR-008) | `GET /ref/products` |
| SCR-01-06 | 고객 언어 | 드롭다운 15값 | 필수 | ar, de, en, es, fr, id, it, ja, pl, pt, ru, th, tr, vi, zh | tickets.csv language |
| SCR-01-07 | 제목 | 한 줄 | 선택 | 저장만, 처리에 안 씀. 칸 옆 "처리에는 쓰지 않음" 보조 글 | inquiry_subject |
| SCR-01-08 | 본문 | 여러 줄 | 필수 | 1~2,000자, 공백만이면 거부 | inquiry_body |
| SCR-01-09 | 접수 시각 | 날짜·시각(UTC) | 선택 | 기본 지금, 과거 허용, 미래 거부 | received_at_utc |
| SCR-01-10 | 원본 표시 | "원본 CSV1-000017에서 불러옴" + 팀 정답지 문의면 "채점용 문의" 배지 | — | — | `GET /gold/tickets/{id}`의 gold_set |
| SCR-01-11 | [접수] 버튼 | `POST /tickets` | — | 항목별 오류를 칸 아래 표시 | — |
| SCR-01-12 | [비우기] | 폼 초기화 | — | — | — |

⑤ 동작: [접수] → 검증 → 성공 시 ticket_id를 받고 SCR-03으로 이동(처리 중 표시는 SCR-03 머리). 실패 시 칸별 오류.

⑥ 상태 변형
| 변형 | 보이는 것 |
|---|---|
| 빈 폼 | 기본값(채널 EMAIL, 시각 지금) |
| 불러오기로 채워진 폼 | 입력 6칸 채워짐, SCR-01-10 원본 표시, 제목·정답 칸은 비어 있음(AC-003-1) |
| 검증 오류 | "고객 ID를 찾을 수 없음", "제품 코드를 찾을 수 없음(모르면 비우세요)", "내용을 입력하세요", "접수 시각은 미래일 수 없음" |
| 접수 중 | 버튼 비활성 + 진행 표시 |
| 접수 실패 | "접수 실패: {사유}" (FR-036 실패 사유), 폼 유지 |

⑦ 데이터: 입력 열 6개만(channel, customer_id, product_code, language, inquiry_body, received_at_utc). 4,000건 전부와 팀이 만든 문의를 불러올 수 있다(D30. 화면 목록의 "학습용(train) 행만"은 v1.4에서 없어짐).

---

## SCR-02. 접수함

| 항목 | 내용 |
|---|---|
| ① 목적 | 내 부서의 끝나지 않은 하위 문의를 급한 순서로 보고 고른다. 상담원의 진입점이자 기본 화면 |
| ② 사용자 | 1차 상담원(13개 부서), 전문 부서 담당(이관된 건) |
| ③ 길 | 상단 메뉴(기본) → 행 클릭 → SCR-03 (AC-029-4). SCR-03 [목록으로] → 돌아올 때 필터·정렬·페이지 유지 |
| ⑧ 근거 | FR-029 (AC-029-1~5), FR-026·027 값 표시, FR-013, FR-031, FR-023, 기술 명세서 §8-1 `GET /tickets`, 뷰 v_inquiry_inbox |
| ⑨ MVP 밖 | 관리자 전체 보기(FR-034), 열 숨기기 설정 |

④ 영역과 요소
| 요소 ID | 영역 | 종류 | 표시 | 출처 |
|---|---|---|---|---|
| SCR-02-S1 | 요약 띠 | 숫자 4개 | 미해결 n / 경고 n / 승인 대기 n / 회신 대기 n (현재 필터 범위) | `GET /tickets` 건수 요약 |
| SCR-02-F1~F8 | 필터 | 칩·드롭다운 | 상태(6) / 우선순위(P1~P4) / 경고 종류(FR_AT_RISK, FR_BREACHED, RES_AT_RISK, RES_BREACHED) / 정보 요청 필요 / 승인 대기 초안 있음 / 복합 문의 / 채널(5) / 종료 포함 스위치 | 쿼리 status, priority, alert, needs_info, has_draft, composite, channel, include_closed |
| SCR-02-F9 | 검색 | 한 칸 | 문의 번호 또는 고객사 | q |
| SCR-02-T | 목록 표 | 하위 문의 1행 | 아래 열 13개 | v_inquiry_inbox |
| SCR-02-PG | 페이지 | 50건/쪽, 쪽 넘김 | | page, size=50 |

목록 표 열(FR-029 처리 2 순서. "자동 발송됨"은 없고 "승인 대기"를 더함)
| 열 | 표시 | 출처 |
|---|---|---|
| 1 문의 번호 | ticket_id, 복합이면 아래 작은 글 "복합 2건 중 1" | sub_ticket.ticket_id, seq, ticket.multi_yn |
| 2 접수 시각 | UTC | ticket.received_at |
| 3 채널 | 아이콘 + 코드 | ticket.channel |
| 4 고객사·등급 | COMPANY_… + 등급 칩(PLATINUM/GOLD/STANDARD) | customers.csv company_masked, tier |
| 5 제품 | product_code (마우스 올리면 product_name) | sub_ticket.product_code, product_master.csv |
| 6 유형 | category_code | sub_ticket.category_code |
| 7 긴급도 | urgency_flag. SAFETY·SITE_DOWN은 빨간 글자 | sub_ticket.urgency_flag |
| 8 우선순위 | 최종값 P1~P4 배지. 조정이면 "P3 (조정)" + CP-8 칩 | sub_ticket.priority_final, priority_adjustment |
| 9 상태 | CP-1. ESCALATED면 "→ {이관 부서}", 이관 부서 접수함에서는 "{원 부서}에서 이관됨" | sub_ticket.status, assigned_dept, escalated_to |
| 10 1차 응답 남은 시간 | "3.2h" / "−1.5h" / MET 체크 | inquiry_sla(as_of) |
| 11 해결 남은 시간 | 같음. 대기 중이면 "멈춤" | inquiry_sla(as_of).remaining_h |
| 12 경고 | 1차/해결 아이콘(노랑 위험, 빨강 위반) | sla_alert(cleared_at IS NULL) |
| 13 표시 3개 | "정보 요청 필요"(막는 항목 있음) / "승인 대기"(DRAFT 있음) / "리마인드 발송됨" | sub_ticket.missing_blocking_info, ticket_message(DRAFT), ticket_message(REMINDER SENT) |

⑤ 동작: 기본 정렬 = 경고 있음 → 우선순위 → 남은 시간 오름차순(FR-027 처리 5). 열 머리 클릭으로 정렬 변경. 필터·정렬·페이지는 브라우저에 기억. 행 클릭 → SCR-03. 5분마다 자동 갱신(갱신 때 선택 행 유지).

⑥ 상태 변형
| 변형 | 보이는 것 |
|---|---|
| 부서 미선택 | "부서를 선택하세요" |
| 빈 목록 | "처리할 문의가 없습니다" |
| 로딩 | 스켈레톤 행 |
| 읽기 실패 | 이전 목록 흐리게 + "목록을 불러오지 못함. 새로고침" |
| 복합 문의 | 하위 문의마다 한 행, 같은 ticket_id 묶음 표시. 담당 부서가 다르면 각 부서 접수함에 자기 행만 |
| 이관 부서에서 볼 때 | 상태 열 "{원 부서}에서 이관됨", 원 부서 접수함에도 남음(FR-033 처리 6) |
| SLA 미정 | 남은 시간 칸 "SLA 미정", 정렬 맨 아래 |
| 종료 포함 | RESOLVED·CLOSED 행이 연회색으로 추가 |

⑦ 확인 숫자(AC-029-1): 미해결 365건 재생 + 스냅샷 + TS_LV → 67건, 맨 위는 경고 있고 남은 시간 최소.

---

## SCR-03. 문의 상세 (시연의 중심, 1순위)

| 항목 | 내용 |
|---|---|
| ① 목적 | 한 문의의 전부: 고객이 보낸 것 → 시스템이 판단한 것과 근거 → 보낼 글(초안 + 대역) → 이력. 승인·발송·조정·이관·회신 입력이 모두 여기서 일어난다 |
| ② 사용자 | 1차 상담원, 전문 부서 담당(이관된 건, 회신 대리 입력) |
| ③ 길 | SCR-02·SCR-04 행 클릭, SCR-01 접수 뒤 자동 이동. [목록으로] → SCR-02. 팝업 P1~P8 |
| 정보 우선순위(R7, B-5) | 처음 열었을 때 눈에 먼저 들어오는 순서: ① 보낼 초안 + 대역 + 검토 표시 ② 왜 이 결과인가(근거) ③ 판단값 ④ 고객 원문 ⑤ 이력. 즉 R 영역과 C의 근거 영역이 펼쳐지고, L과 B는 접힌다. 레이아웃(탭 4개·세로 쌓기·분할)은 목업 3안에서 결정 |
| ⑧ 근거 | FR-030 (AC-030-1~5), FR-024 (AC-024-1~3), FR-039 (AC-039-1~4), FR-028 (AC-028-1·2), FR-031 (AC-031-1~5), FR-032 (AC-032-1·2·4·5), FR-033 (AC-033-1~4), FR-020 AC-020-3, FR-018, FR-015 AC-015-3, FR-013 AC-013-3. 기술 명세서 §8-1 `GET /tickets/{id}`, `/timeline`, `/runs` |
| ⑨ MVP 밖 | "진행 안내" 탭(FR-048), 유사 해결 사례 영역(FR-019, C 영역 진단 후보 아래), 실시간 자체 검사 경고(FR-045, 확인 표시 모음에 합쳐짐), 고객 원문 한국어 번역 토글 |

### ④ 영역 SCR-03-H 머리
| 요소 ID | 표시 | 출처 |
|---|---|---|
| H-01 | 문의 번호 ticket_id + "원본 CSV1-xxxxxx에서 불러옴" + "채점용 문의" 배지(팀 정답지 문의일 때) | ticket.ticket_id, source_ticket_id, gold_set |
| H-02 | 티켓 대표 상태 배지(CP-1) + 대표 SLA(CP-2) — 가장 급한 하위 문의 기준(D16) | v_ticket_summary |
| H-03 | 고객사·등급·국가, 채널, 고객 언어 | ticket.customer_id → customers.csv |
| H-04 | 처리 중 / 자동 처리 실패({단계}) / 완료 표시 | agent_run.status, failed_step |
| H-05 | 버튼: [목록으로] [다시 처리](`POST /tickets/{id}/reprocess`) | — |

### ④ 영역 SCR-03-L 고객이 보낸 것 (기본 접힘)
| 요소 ID | 표시 | 출처 |
|---|---|---|
| L-01 | 원문 inquiry_body(마스킹된 본문). 길면 접어서 "펼치기". 추출한 값(제품 코드, 제조번호, 에러 코드, 펌웨어 버전 등 32종)을 노란 밑줄로 강조, 마우스 올리면 항목 이름 | ticket.body_masked, provided_fields.span |
| L-02 | 제목(보조 글 "처리에는 쓰지 않음"), 채널, 고객 언어 / 본문 언어(다르면 "본문 언어 판정 불확실" 표시) | ticket.language, body_language, body_language_uncertain |
| L-03 | 전화 건이면 "영어 메모, 답장은 {language}" | ticket.channel = PHONE |
| L-04 | 고객 회신·부서 회신 본문(있으면 시각순, 원문 아래) | ticket_message(CUSTOMER_REPLY, ESCALATION_NOTE RECEIVED) |

### ④ 영역 SCR-03-C 시스템이 판단한 것 — 하위 문의마다 구역 1개 ("문의 1/2: FW_UPDATE")
| 요소 ID | 표시 | 출처 | 동작 |
|---|---|---|---|
| C-01 | 유형 category_code + 확신도 낮으면 "확신 낮음" 칩 | sub_ticket.category_code, category_confidence | "왜?" → P1(근거 문장). 직접 수정 드롭다운(10종) → "상담원 수정" 칩, Q2부터 재실행 |
| C-02 | 긴급도 urgency_flag + 근거 문장 요약 | sub_ticket.urgency_flag, urgency_evidence | 수정 가능(6값) → Q2부터 |
| C-03 | 우선순위: 규칙값 "P4 (PR-07)" / 최종값 "P3". 조정이면 "P4 → P3 (상담원 조정, 사유: …)" + CP-8 | priority_rule, priority_rule_id, priority_final, priority_adjustment | "왜?" → P1(규칙 판정 과정). [조정] → P3 |
| C-04 | 담당 부서 assigned_dept + 규칙 RT-… + 이관 조건 문구. ESCALATED면 "→ {이관 부서} ({사유}, {시각})" | sub_ticket.assigned_dept, routing_rule_id, escalation_condition, escalated_to | "왜?" → P1 |
| C-05 | 반품이면 반품 구분(불량/비불량/확인 필요) | return_kind | "확인 필요"면 [불량/비불량 선택] → Q4부터 |
| C-06 | SLA 두 시계(CP-2) + sla_id | sub_ticket.sla_id, fr_target_h, res_target_h, inquiry_sla(as_of) | 조정 뒤 "변경됨: 72/168h → 24/120h" |
| C-07 | 필수 항목 체크리스트: 항목 라벨마다 ✓ 제공(값) / 빠짐 / **막는 항목** 빨간 강조. 순서는 required_info.csv field_order | provided_fields, missing_info, missing_blocking_info, info_field_codebook.csv label | 상담원이 "받았음" 표시 → "상담원 입력" 칩, Q5부터 재실행 |
| C-08 | 고장 진단 후보(고장 계열만): 1순위 크게(원인·점검·조치·현장 출동·교체 필요·찾은 방법 EXACT/SYMPTOM), 2·3순위 접힘. "참고용, 초안에는 쓰지 않음" 보조 글. 모두 기준 미만이면 "관련성 낮음" | fault_candidates (agent_step.output_json), fault_catalog.csv | "왜?" → P1 |
| C-09 | 이관 후보: "이관 후보: QA_CLAIM — RT-ESC-DEFECT-RMA (교체)". 없으면 "없음 — 이관 조건: {문구}" | escalation_candidates | [이관] → P4 (기본값 이 부서) |
| C-10 | 근거 영역(접힌 목록): 맨 위 확인 표시 모음(확신 낮음, 판정 실패, 근거 없음, 반품 사유 확인 필요, 제품 미확정, 추출 실패, 자체 대조 불일치). 아래 단계 ①~⑧ 각 줄 "결과 — 근거(규칙 ID / 문서·절 / 표 값)" 펼치면 상세 | self_check(passed_yn = N), agent_step | 줄 클릭 → P1 |
| C-11 | 처리 기록 링크 "실행 기록 보기" (run, step 목록) | `GET /tickets/{id}/runs` | 펼침 |

### ④ 영역 SCR-03-R 보낼 것 (기본 펼침)
| 요소 ID | 표시 | 출처 | 동작 |
|---|---|---|---|
| R-00 | 탭 2개: **정보 요청** / **답변**. 복합이면 답변 탭 안에 하위 문의별 카드. "진행 안내" 탭은 비활성(여유 시) | ticket_message.message_type | 초안이 있는 탭이 기본 |
| R-01 | 초안 카드 머리: 종류, 대상 하위 문의(seq), 만든 시각, CP-7 검토 표시 줄 | review_marks | 걸린 번호 클릭 → 해당 요소로 이동 |
| R-02 | CP-5 편집기: 초안(고객 언어) + 대역(ko, en 전환). 인용 `(DOC_ID §n.m)`과 숫자는 CP-4 링크. 자체 대조 불일치 위치 노란 강조 | ticket_message(DRAFT).body, message_gloss, self_check DRAFT_CHECK | 편집 → [임시 저장] `PUT /messages/{id}` → 대역 다시 생성(이전 대역에 "이전 내용" 표시) |
| R-03 | 대역 없음일 때 "대역 없음(번역 실패)" + [다시 만들기] `POST /messages/{id}/gloss` | message_gloss 없음 | 승인은 막지 않음 |
| R-04 | 복합 문의 답변 카드 아래 "문의 상태 목록" 자동 문구 미리 보기(고객 언어 고정 문안, 하위 문의 수만큼 줄) | T5 상태 목록(T40 템플릿) | 읽기 전용 |
| R-05 | 버튼: [승인·발송] → P7 → `POST /messages/{id}/send` / [임시 저장] | — | 발송 뒤 카드가 "발송됨 {시각}"으로 바뀌고 읽기 전용 |
| R-06 | 초안이 없을 때 사유 + 빈 편집기: "막는 정보 요청 중"(정보 요청이 나간 상태) / "근거 없음 — 상담원 작성 필요" / "처리 중" / "초안 생성 실패 — 다시 처리" | self_check, agent_run | 빈 편집기에 직접 써서 승인 가능(P7 검사는 똑같이 지남) |
| R-07 | 카드 위 [이관] 버튼 → P4. IN_PROGRESS일 때만 활성 | sub_ticket.status | — |
| R-08 | 대체된 초안(superseded_at 있음) 접힌 목록 "이전 초안 n개" | ticket_message.superseded_at | 펼쳐 보기만 |

### ④ 영역 SCR-03-B 이력 띠 (기본 접힘)
| 요소 ID | 표시 | 출처 |
|---|---|---|
| B-01 | 시각순 한 줄 목록. 종류별 아이콘: 고객 문의 INQUIRY / 정보 요청 INFO_REQUEST / 답변 FINAL_REPLY / 고객 회신 CUSTOMER_REPLY / 이관 메모 ESCALATION_NOTE(SENT·RECEIVED) / "리마인드 자동 발송 {시각}"(보낸 쪽 SYSTEM) / 상태 변경(NEW→IN_PROGRESS …) / 경고 발생·해제 / 우선순위 조정 / 종료(시스템) | `GET /tickets/{id}/timeline` (ticket_message, ticket_status_history, sla_alert, priority_adjustment) |
| B-02 | 메시지 줄 펼치면 보낸 쪽·언어·본문·대역·"수정됨"(초안과 다르면) | ticket_message.sent_by, language, body, edited_yn, message_gloss |
| B-03 | 버튼: [고객 회신 입력] → P6 (항상) / [부서 회신 입력] → P5 (ESCALATED일 때만) | — |

### ⑤ 동작 요약
| 동작 | API | 결과 |
|---|---|---|
| 유형·긴급도·제품 수정 | `PATCH /sub-tickets/{id}` | Q2부터 재실행, "상담원 수정" 칩, 처리 중 표시 |
| 제공 항목 수정 | 같음 | Q5부터 |
| 반품 구분 선택 | 같음 | Q4부터 |
| 우선순위 조정 (P3) | `POST /sub-tickets/{id}/priority` | SLA 목표 재조회·덮어쓰기, 이력 1줄, 경고 재평가 |
| 이관 (P4) | `POST /sub-tickets/{id}/escalate` | ESCALATED, ESCALATION_NOTE SENT |
| 부서 회신 (P5) | `POST /sub-tickets/{id}/dept-reply` | IN_PROGRESS, RECEIVED 행. 그래프 재실행 없음 |
| 고객 회신 (P6) | `POST /tickets/{id}/replies` | WAITING_CUSTOMER/RESOLVED → IN_PROGRESS, Q1부터 재처리 |
| 임시 저장 | `PUT /messages/{id}` | 본문만 저장, 대역 재생성 |
| 승인·발송 (P7) | `POST /messages/{id}/send` | SENT, 전이(정보 요청 → WAITING_CUSTOMER, 답변 → 답한 하위 문의 RESOLVED), 1차 응답 시각(처음일 때) |
| 다시 처리 | `POST /tickets/{id}/reprocess` | 새 run, 이전 DRAFT는 superseded |

### ⑥ 상태 변형
| 변형 | 보이는 것 |
|---|---|
| 처리 중 | L 보임, C·R "처리 중" 진행 표시, 2초마다 갱신. 끝나면 자동으로 채워짐 |
| 자동 처리 실패 | H-04 "자동 처리 실패: {단계} — {사유}" + [다시 처리]. 실패한 하위 문의만 표시, 나머지 정상 |
| 단일 / 복합 | C 구역 1개 / n개, R 답변 탭 카드 n개, 접수함 "복합 n건 중 k" |
| 정보 요청 필요 | C-07 막는 항목 빨강, R 정보 요청 탭에 초안, 답변 탭 "막는 정보 요청 중" |
| 근거 없음 | R 답변 탭 "근거 없음 — 상담원 작성 필요", C-10 확인 표시, CP-7 ③ 걸림 |
| 대조 불일치 | R-02 노란 강조 + 불일치 목록, CP-7 ① 걸림, 발송 시 P7 경고 |
| 고객 회신 대기 | 상태 회색, CP-2 해결 시계 "멈춤", 이력에 정보 요청 SENT, 126h 뒤 리마인드 줄 |
| 이관됨 | 상태 보라, C-04 이관 정보, [이관] 비활성("이미 이관됨"), B-03 [부서 회신 입력] 활성 |
| 해결 | 상태 초록, 발송 카드 읽기 전용, [고객 회신 입력]은 활성(168h 안 재문의) |
| 종료 | 읽기 전용(버튼 전부 비활성), 머리에 "종료된 문의입니다"(CLOSED_NO_RESPONSE면 "무응답 종료") |
| 충돌·실패 | P8 |

### ⑦ 확인 사례(AC)
- AC-030-1 CSV1-000017: L 원문 + error_code 강조, C DEFECT·SITE_DOWN·P1(PR-02)·TS_LV·1h/24h·막는 항목 serial_no 강조, R 정보 요청 탭 영어 초안.
- AC-030-3 CSV1-000008: C 구역 2개(FW_UPDATE / MANUAL), R 답변 탭 카드 2개.
- AC-030-4 CSV1-000004: 정보 요청 탭 "막는 항목 없음", 답변 탭 프랑스어 초안 + 인용 + 조회값(520 USD, 4주).
- AC-039-1: 초안 옆 한국어 대역, 숫자·인용 원문과 같음.

---

## SCR-04. 나의 업무 현황 (상담원 대시보드)

| 항목 | 내용 |
|---|---|
| ① 목적 | 상단에서 고른 상담원이 "지금 내가 손대야 할 것"을 한 장에서 본다. 접수함이 순서라면 이 화면은 할 일과 위험 |
| ② 사용자 | 1차 상담원, 전문 부서 담당 |
| ③ 길 | 상단 메뉴 → 어느 목록이든 행 클릭 → SCR-03 (AC-047-6) |
| ⑧ 근거 | FR-047 (AC-047-1~7), FR-026·027, 기술 명세서 §8-1 `GET /me/workload?as_of=`, §8-3 값 출처, D31·D33·T43 |
| ⑨ MVP 밖 | "전체 보기" 스위치(관리자 운영 대시보드 FR-034: 전 부서 위험·위반, 부서별 미해결 건수, SLA 상태별 건수, 주간 품질 추이 FR-044 + [내려받기]) |

④ 영역과 요소 (영역 5개 모두 MVP)
| 요소 ID | 영역 | 표시 | 출처(기술 명세서 §8-3) |
|---|---|---|---|
| SCR-04-01 | 범위 띠 | "{상담원} · {부서} · 기준 {as_of}". 상담원 미선택이면 "부서 전체 기준" | X-Agent-Id, assignee_masked |
| SCR-04-T1~T4 | ① 숫자 타일 4개 | 승인 대기 초안 / 기한 위험·위반 / 고객 회신 대기 / 이관 회신 대기. 누르면 아래 목록으로 스크롤 | ticket_message(DRAFT, superseded_at NULL) / sla_alert(cleared_at NULL) / status = WAITING_CUSTOMER / status = ESCALATED |
| SCR-04-L1 | ② 기한 위험·위반 목록 | 열: 문의 번호(복합이면 순번), 고객사·등급, 우선순위, 상태, 경고 종류(FR_AT_RISK/FR_BREACHED/RES_AT_RISK/RES_BREACHED), 남은 시간(음수 허용). 남은 시간 오름차순 | sla_alert + inquiry_sla(as_of).remaining_h + v_inquiry_inbox |
| SCR-04-L2 | ③ 승인 대기 초안 목록 | 종류(정보 요청/답변), 하위 문의, 만든 시각, 확인 표시 유무(self_check N 있으면 노란 점). 우선순위 → 만든 시각 순 | ticket_message, self_check, sub_ticket.priority_final |
| SCR-04-L3 | ④-1 고객 회신 대기 목록 | 정보 요청 발송 뒤 경과 시간, 126h·168h 눈금 막대, "리마인드 발송됨" 표시 | ticket_message(INFO_REQUEST SENT, REMINDER) |
| SCR-04-L4 | ④-2 이관 회신 대기 목록 | 이관 부서, 이관 시각, 경과 시간 | sub_ticket.escalated_to, ticket_status_history(ESCALATE) |
| SCR-04-N | ⑤ 오늘 처리한 건수 | 발송 n · 이관 n · 조정 n (as_of 날짜, UTC) | ticket_message(SENT, sent_by), ticket_status_history(ESCALATE, changed_by), priority_adjustment(adjusted_by) |
| SCR-04-X | SLA 미정 | 목록에서 빼고 "SLA 미정 n건" 링크 | sub_ticket.sla_id IS NULL |

⑤ 동작: 상단 막대의 이름·부서·기준 시각을 바꾸면 다시 그린다. 5분마다 자동 갱신. 행 클릭 → SCR-03.

⑥ 상태 변형
| 변형 | 보이는 것 |
|---|---|
| 할 일 없음 | 영역별 빈 문구 "승인 대기 초안이 없습니다" 등, 타일 0 |
| 이름·부서 미선택 | "상단에서 이름과 부서를 고르세요" |
| 로딩 / 읽기 실패 | 스켈레톤 / 이전 값 유지 + "불러오지 못함. 새로고침" |
| 부서만 선택 | SCR-04-01 "부서 전체 기준", 숫자는 부서 전체 |

⑦ 확인 숫자: AC-047-1 미해결 365건 재생 + 스냅샷 + TS_LV → 기한 위험·위반 35(해결 AT_RISK 8 + BREACHED 26 + 1차 응답 위험 CSV1-003951 1, 2026-10-23 조장 결정 C-121). AC-047-3 CSV1-003578 130h 경과 → "리마인드 발송됨". AC-047-4 CSV1-000017 FIELD_SVC 이관 → 이관 회신 대기 목록.

---

## 팝업 9개

### SCR-01-P1. 시연용 문의 불러오기
| 항목 | 내용 |
|---|---|
| 여는 곳 | SCR-01-02 |
| 입력 | 문의 번호(필수). 운영진 데이터 "CSV1-" + 6자리, 팀 정답지 문의 번호 형식은 D30 뒤 |
| 버튼 | [불러오기] `GET /gold/tickets/{id}` / [닫기] |
| 결과 | 접수 폼의 6칸(channel, customer_id, product_code, language, inquiry_body, received_at_utc)이 채워지고 SCR-01-10 원본 표시. 제목·정답 칸은 비움 |
| 오류 문구 | "형식: CSV1-000000" / "문의를 찾을 수 없음"(404) |
| 근거 | FR-003 AC-003-1·2, D30 |

### SCR-03-P1. "왜?" 근거 상세
| 항목 | 내용 |
|---|---|
| 여는 곳 | C-01~C-04, C-08, C-10의 "왜?" |
| 보이는 것 | 값 종류에 따라: 유형·긴급도 → 분류 근거 문장(원문 발췌)·확신도 구간 / 우선순위 → 적용 규칙 행 원문("PR-02: urgency=SITE_DOWN 이고 Category ∈ {DEFECT, INSTALL, FW_UPDATE} → P1")과 판정 과정(PR-01 ✗, PR-02 ✓) / 부서 → routing_rules.csv 행 + 이관 조건 / 필수정보 → required_info.csv 행 / SLA → sla_policy.csv 행 / 진단 → fault_catalog.csv 행과 찾은 방법·점수 / 이관 후보 → ESCALATION 행과 켜진 조건 |
| 출처 | agent_step.output_json(priority_trace 등), ref 규칙표 원문(화면 표시용으로 원문 condition 유지, AC-030-2) |
| 버튼 | [닫기] |
| 근거 | FR-024 처리 2, AC-030-2, AC-024-1·3("없음(분류 실패)") |

### SCR-03-P2. 인용 절 본문 / 조회 값 출처
| 항목 | 내용 |
|---|---|
| 여는 곳 | R-02 초안의 인용 `(DOC_ID §n.m)` 또는 숫자 |
| 보이는 것 | 인용: 문서 ID·제목·절 번호·절 본문(`GET /chunks/{chunk_id}`), 점수. 숫자: 조회 항목·값·단위·출처("product_master.csv: INV-LSLV0075-S100", "product_spec_facts.csv: …/Overload capacity") |
| 오류 문구 | "본문 열기 실패"(인용 문자열만 표시) |
| 근거 | FR-024 처리 3, AC-024-2 |

### SCR-03-P3. 우선순위 조정
| 항목 | 내용 |
|---|---|
| 여는 곳 | C-03 [조정] |
| 입력 | 새 우선순위 P1~P4(필수, 현재값 제외), 사유 분류(고객 요청 / 영향 범위 재평가 / 기타, 필수), 사유 글(필수) |
| 미리 보기 | "SLA 목표 72/168h → 24/120h (SLA-MANUAL-STANDARD-P3)". 즉시 위반이 되면 빨간 경고 "이 조정으로 기한 위반 상태가 됩니다. 계속할까요?" |
| 버튼 | [조정] `POST /sub-tickets/{id}/priority` / [취소] |
| 결과 | priority_final 변경, SLA 목표 덮어쓰기, priority_adjustment 1행, 경고 재평가, C-03·C-06 갱신, 이력 1줄 |
| 오류 문구 | "현재와 같은 우선순위" / "조정 사유를 입력하세요" / "종료된 문의는 바꿀 수 없음" |
| 근거 | FR-028 AC-028-1·2, AC-027-5 |

### SCR-03-P4. 이관
| 항목 | 내용 |
|---|---|
| 여는 곳 | R-07 [이관] (IN_PROGRESS일 때만) |
| 입력 | 이관 부서(기본 = C-09 이관 후보 부서, departments.csv 13개), 이관 사유 코드(CP-6, 필수), 메모(선택) |
| 버튼 | [이관] `POST /sub-tickets/{id}/escalate` / [취소] |
| 결과 | ESCALATED, escalated_to, ESCALATION_NOTE SENT, 이관 부서 접수함에 표시. 이관 안내 초안은 여유 시(FR-048) |
| 오류 문구 | "이관 사유를 고르세요" / "이미 이관됨({부서})" / "같은 부서로는 이관할 수 없음" / "처리 중인 문의만 이관할 수 있음" |
| 근거 | FR-033 처리 1~6, AC-033-1·2 |

### SCR-03-P5. 전문 부서 회신 입력
| 항목 | 내용 |
|---|---|
| 여는 곳 | B-03 [부서 회신 입력] (ESCALATED일 때만) |
| 입력 | 회신 본문(필수), 회신 시각(기본 지금, 과거 허용, 이관 시각보다 앞이면 거부) |
| 버튼 | [저장] `POST /sub-tickets/{id}/dept-reply` / [취소] |
| 결과 | ESCALATION_NOTE RECEIVED(sender DEPT), ESCALATED → IN_PROGRESS. 그래프는 다시 돌지 않고 본문은 L-04·B에 참고로 표시 |
| 근거 | FR-033 처리 8, AC-033-3 |

### SCR-03-P6. 고객 회신 입력
| 항목 | 내용 |
|---|---|
| 여는 곳 | B-03 [고객 회신 입력] |
| 입력 | 회신 본문(필수, 2,000자), 회신 언어(기본 = 고객 언어), 회신 시각(기본 지금, 과거 허용, 미래 거부, 정보 요청 발송보다 앞이면 거부), 대상 하위 문의(복합에서 대기 중이 둘 이상일 때 체크박스, 기본 전부) |
| 버튼 | [입력] `POST /tickets/{id}/replies` / [취소] |
| 결과 | CUSTOMER_REPLY 저장, WAITING_CUSTOMER/RESOLVED → IN_PROGRESS, 대기 구간 닫힘, 대상 하위 문의 Q1부터 재처리 → 새 초안(정보 요청 "재요청" 표시 또는 답변). H-04 "처리 중" |
| 오류 문구 | "회신 내용을 입력하세요" / "회신 시각은 요청 발송 이후여야 합니다" / 종료된 문의면 "종료 후 회신으로 기록됨"(저장만) / 재처리 실패 "자동 처리 실패. 다시 처리" / 값 변화 없음 "제공 항목 변화 없음" |
| 근거 | FR-032 AC-032-1·2·4·5 |

### SCR-03-P7. 발송 전 확인 (모든 발송의 관문)
| 항목 | 내용 |
|---|---|
| 여는 곳 | R-05 [승인·발송] |
| 보이는 것 | 최종 본문에 자체 대조를 다시 한 결과와 검토 표시 4개(최신값). 걸린 것만 줄로: "근거 밖 인용/숫자 n곳: {목록}" / "막는 정보({항목 라벨})가 아직 없습니다" / "고객 언어(ja)와 본문 언어(en)가 다릅니다" / "안전·설비 정지 문의입니다". 걸린 것이 없으면 "검사 4개 통과 — 발송할까요?" |
| 버튼 | [발송] (걸린 것 없을 때) / [그래도 발송] (override_check = true, 선택이 기록됨) / [돌아가서 고치기] |
| 결과 | `POST /messages/{id}/send` → 409면 불일치 목록 표시 후 [그래도 발송] 활성. 성공 시 SENT, 전이, 1차 응답 시각(처음일 때), 카드 "발송됨 {시각}" |
| 오류 문구 | "내용을 입력하세요" / "이미 발송된 초안" / "종료된 문의입니다. 메시지만 기록됨" |
| 근거 | FR-031 처리 1·2, AC-031-3·5, §5-7 |

### SCR-03-P8. 충돌·실패 안내
| 항목 | 내용 |
|---|---|
| 여는 곳 | 저장·발송·조정·이관 요청이 실패했을 때 자동 |
| 문구 | "다른 사용자가 변경함. 새로고침"(충돌) / "자동 처리 실패: {단계} — {사유}. 다시 처리"(FR-036 사유) / "이미 발송된 초안" / "종료된 문의입니다" / "이미 이관됨({부서})" |
| 버튼 | [새로고침] / [다시 처리] / [닫기] |
| 근거 | FR-030·031·033 예외, FR-025 예외(충돌) |

---

## 부록 A. 화면 ↔ API 대응 (기술 명세서 §8-1)
| 화면·팝업 | 읽기 | 쓰기 |
|---|---|---|
| SCR-01 / P1 | `GET /ref/customers?q=`, `GET /ref/products`, `GET /gold/tickets/{id}` | `POST /tickets` |
| SCR-02 | `GET /tickets?dept=&status=&priority=&alert=&needs_info=&has_draft=&composite=&channel=&q=&include_closed=&page=&size=50&sort=` | — |
| SCR-03 | `GET /tickets/{id}`(review_marks 포함), `GET /tickets/{id}/timeline`, `GET /tickets/{id}/runs`, `GET /runs/{run_id}/steps`, `GET /chunks/{chunk_id}` | `PATCH /sub-tickets/{id}`, `POST /tickets/{id}/reprocess`, `PUT /messages/{id}`, `POST /messages/{id}/gloss` |
| P3 / P4 / P5 / P6 / P7 | — | `POST /sub-tickets/{id}/priority` / `/escalate` / `/dept-reply` / `POST /tickets/{id}/replies` / `POST /messages/{id}/send` |
| SCR-04 | `GET /me/workload?as_of=` | — |
| (여유 시) 운영 대시보드 | `GET /dashboard/alerts`, `/summary`, `/quality-trend` | — |
| 공통 | 요청 머리 `X-Agent-Id`, `X-Agent-Dept` | — |

## 부록 B. 시나리오 ↔ 화면 요소 (사용자 시나리오 v1 S1~S7)
| 시나리오 | 지나는 요소 |
|---|---|
| S1 ⓐ 저위험 정보 문의 | SCR-01 → SCR-03 R-01(검사 4개 통과) · R-02 CP-4 → P2 · R-05 → P7 → "발송됨" |
| S2 ⓑ 안전·설비 정지 | SCR-02 맨 위 P1 빨강 · SCR-04 T2·L1 경고 · SCR-03 C-07 serial_no · R 정보 요청 → P7 · C-09 FIELD_SVC → P4 → P5 |
| S3 ⓒ 필수 정보 누락 | SCR-03 C-07 막는 항목 · R 정보 요청 탭 → P7 · CP-2 멈춤 · B-01 리마인드 줄 · B-03 → P6 → R 답변 탭 · R-08 이전 초안 |
| S4 ⓓ 복합 문의 | SCR-02 두 줄 · SCR-03 C 구역 2개 · R 답변 카드 2개 · R-04 상태 목록 |
| S5 ⓔ 고장과 이관 | C-08 FLT-028 · C-09 QA_CLAIM → P4 · SCR-02(QA_CLAIM) 이관됨 행 · P5 · P7 숫자 경고 → 그래도 발송 |
| S6 ⓕ 사람의 조정 | C-03 [조정] → P3 미리 보기 24/120 · C-06 "변경됨" · B-01 조정 줄 |
| S7 막는 장면 | C-05 반품 구분 · R-06 "근거 없음" · R-02 노란 강조 · P7 "근거 밖 숫자" · P8 |

## 부록 C. 조장 확인이 필요한 것
1. ~~리마인드 표시 방식~~ **확정(조장, 2026-10-20)**: 기술 명세서 v1.3을 기본으로 따른다 → 스케줄러 자동 발송, 승인 대기 카드 없음. 화면 목록 §6-1 기본안과 목업 README의 "승인 대기 카드"는 이 결정으로 바뀐다.
2. ~~SCR-01 불러오기 범위~~ **확정(조장, 2026-10-20)**: tickets.csv의 data_split(train/valid/test) 행 구분은 쓰지 않는다. 불러오기 대상은 운영진 데이터 4,000건 전부 + 팀이 만든 문의(채점용 표시). 불러오기 기능 자체는 W5 재현과 AC-003의 전제라 유지한다.
3. **레이아웃**: 목업 3안(사이드바형 / 상단막대형 / 분할화면형) 중 하나. 이 정의서의 영역 ID(H·L·C·R·B)는 어느 안에도 그대로 붙일 수 있다.
4. **사유 분류 3값(P3)**: FR-028 제안값(고객 요청 / 영향 범위 재평가 / 기타). 데이터에 없음.
5. **CP-2 색·아이콘, CP-1 배지 색**: 디자인 가이드 §2 CI 색으로 바꿀지(현재는 기능 명세서의 초록·노랑·빨강·회색).
