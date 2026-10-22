# Design: 검증 에이전트

## Context

동기는 proposal.md의 Why를 본다. 따를 기준은 다음과 같다.

- 명세서 v1.5 FR-049(처리 1~9, 예외, AC-049-1~6), FR-024 처리 6(검토 표시 ⑤).
- 기술 명세서 v1.4: §2-1(하위 문의 그래프), §2-2 Q14 행, §2-3 verify_findings, §2-4 L8 호출 행, §3-1 L8 입력, §3-2 L8 검증 출력, §3-3 "검증은 지적만".
- 에이전트 설계서 v1.1: 3-5절(결정 표), 4-10절(지시문, 결과 모양, 코드 검사, 대역 없음, 실패).
- 7번 변경의 코드: `app/pipeline/graph.py`, `app/llm/drafts.py`.

## Goals / Non-Goals

**Goals**
- 그래프가 만든 초안마다 검증 결과를 붙인다(근거: FR-049 처리 1).

**Non-Goals**
- 저장, 화면, [다시 검증], 승인(proposal "범위 밖").

## Decisions

### 1. 지시문 (`prompts/l8_verify_v1.md`)

에이전트 설계서 4-10절 초안을 쓴다. `<customer_request>`가 나오는 세 곳(3번 OFF_TOPIC 문장, 안내 줄, 태그 줄)을 모두 `<customer_message>`로 바꾼다(근거: CLAUDE.md 규칙 5, config.yaml "고객 본문은 <customer_message> 안에만". 7번 변경 L4와 같은 처리, 개발_결정_기록 C-25를 L8로 넓힘). 자리표시 `{dept_reply_or_empty}`, `{gloss_body_or_empty}`는 `{dept_reply}`, `{gloss_body}`로 줄이고 비어 있으면 빈 글을 넣는다(근거: 4-10절. 이름 줄임은 구현 선택).

### 2. 호출 (`app/llm/verify.py`의 `verify_draft`)

| 항목 | 정한 것 | 근거 |
|---|---|---|
| 입력 | 언어 이름, 대역 언어 이름(Korean), 근거 문장(evidence_sentences), 근거 절(`[DOC_ID §절] 제목` + 본문), 조회값(item \| value \| unit \| source), 부서 회신(빈 글), 초안 본문, 대역 본문(없으면 빈 글) | 4-10절 입력, §3-1 L8. 근거 절·조회값의 줄 모양은 7번 L4와 같게(구현 선택) |
| 결과 모양 | `{"findings": [{"kind", "quote", "reason"}]}`, kind 열거형 4값 | §3-2 L8, 4-10절 |
| 호출 | `generate_json`(가리기, 30초, 1회 재시도). 모델은 다른 호출과 같은 `LLM_MODEL_SMALL`(`gemini-3.8-flash`) | CLAUDE.md 규칙 2, FR-049 처리 6·9, 에이전트 설계서 4-1 "L8은 등급을 나누지 않고 같은 모델"(추가 결정 가4). 소형 환경 변수를 쓰는 것은 구현 선택 |
| quote 확인 | quote가 초안 본문이나 대역 본문 안에 그대로 있어야 남긴다. 대역이 없으면 GLOSS_MISTRANSLATION 지적도 버린다 | §3-2 L8 "quote가 초안 또는 대역에 실제로 있는지", 4-10절 대역 없음. 앞뒤 공백을 빼고 보는 것과 대역 없을 때 버리는 것은 구현 선택 |
| 실패 | LlmError → 결과 error = 오류 종류, 지적 없음, 통과 아님 | FR-049 처리 7, 4-10절 저장 `{"error": ...}` |

### 3. 결과 객체 (`VerifyResult`)

{findings: list[VerifyFinding], gloss_checked: bool, error: str | None, checked_at_utc}. `passed_yn` = 오류 없음 그리고 지적 없음. `detail()`은 self_check.detail 모양({findings, gloss_checked} 또는 {error})을 낸다(근거: 에이전트 설계서 4-10절 저장, schema.sql eval.self_check passed_yn·detail·checked_at_utc, FR-049 출력 "검증 시각, 실패 여부". 객체로 두는 것은 구현 선택). `by_kind()`는 4항목마다 "문제 있음 / 문제 없음 / 확인 못 함"을 낸다(근거: FR-049 처리 3·출력 "항목별 검증 결과". 기술 명세서 §3-2는 지적 목록이라 둘을 함께 둠, 개발_결정_기록 C 항목). VerifyFinding은 5번 변경 상태 객체의 모델을 그대로 쓴다(근거: §2-3 verify_findings).

### 4. ⑤ 상태와 문구 (`VerifyResult.state`, `mark()`)

상태는 PASSED(지적 없음) / FOUND(지적 있음) / FAILED(실패)다. STALE(고친 뒤 검증 안 함)은 9번 변경이다(근거: 기술 명세서 §5-7, 에이전트 설계서 6-3절 ⑤ 행).

| 경우 | 문구 | 근거 |
|---|---|---|
| 지적 없음 | "⑤ 통과" | FR-049 처리 4 "없으면 ⑤는 통과" |
| 지적 있음 | "⑤ 걸림: {항목 이름들}" (뜻 다름 / 약속 표현 / 질문과 다름 / 대역 오역, 중복 없이 차례대로 ", "로 이음) | FR-049 처리 4, 4-10절 화면 이름. 여러 항목을 잇는 방식은 구현 선택 |
| 실패 | "⑤ 검증 못 함(실패)" | FR-049 처리 7 |
| 대역 없음 | 위 문구 뒤에 " (대역 없음: ④ 확인 못 함)" | 4-10절 "대역이 없을 때", 6-3절 ⑤ 행. 명세서 FR-049 예외 3행(제안)은 "⑤ 대역 없음: ④ 확인 못 함"이라 설계서 쪽을 따름(C 항목) |

### 5. 그래프

- gloss 노드 뒤에 verify 노드를 두고 초안마다 `verify_draft`를 부른다(근거: §2-1 "Q13 대역 → Q14 검증 → 끝").
- 근거 절은 reply 노드가 읽은 것을 그래프 상태 `sources`(하위 문의별)에 두고 다시 쓴다. 정보 요청 초안은 근거 절·조회값이 비어 있다(근거: §2-1 분기③ "예"는 Q8·Q9를 지나지 않음. 상태 칸은 구현 선택).
- 결과는 초안 객체 `verify`와 하위 문의 상태 `verify_findings`에 둔다(근거: §2-3). 실패면 `verify_findings`를 None으로 두는 것은 구현 선택이다.
- 검증이 실패해도 실행(run_status)은 SUCCESS로 둔다. 기준 문서는 L8 실패 때 실행 상태(SUCCESS / PARTIAL)를 정하지 않았다(구현 선택. FR-049 예외 2행 "초안은 보이고 … 승인은 막지 않음"에 맞춤, 개발_결정_기록 C 항목).

### 6. 시험

- 대역 Transport: AC-049-1(CSV1-000004 견적 초안에 "30 % de remise", 코드 검사 통과·⑤ 걸림: 약속 표현·quote 남음), AC-049-4(L8 두 번 시간 초과 → 초안 유지, ⑤ 검증 못 함, error LLM_TIMEOUT), AC-049-5(뜻이 다른 대역 → ⑤ 걸림: 대역 오역), AC-049-6(L8 지시문에 원래 이메일·전화번호 없음), 지어낸 quote 버림, 대역 없음.
- 실제 Gemini(키가 있을 때만): AC-049-1, AC-049-5. 초안과 대역은 시험에서 정해 넣고 `verify_draft`만 실제로 부른다(구현 선택). POL-ORDER §5에 "Volume discounts apply to larger quantities"가 있어 실제 모델이 PROMISE 대신 MEANING_MISMATCH로 볼 수도 있다. AC대로 "약속 표현"을 기대하고, 흔들리면 결정 기록에 남긴다.
- AC-049-1의 티켓은 팀 정답지 GS-076의 원래 티켓 번호가 문서에 없어, 같은 경우(견적, POL-ORDER §5 유효기간 30일)인 CSV1-000004를 쓴다(구현 선택).

## Risks / Trade-offs

- 모델이 문제를 놓치거나 지나치게 지적할 수 있다. 표시만 하고 막지 않으므로 상담원 판단에 맡긴다(근거: FR-049 처리 5, 가-6).
- 호출이 초안마다 1회 늘어 비용이 늘어난다(근거: 에이전트 설계서 표 "L8 약 2,000 토큰").
