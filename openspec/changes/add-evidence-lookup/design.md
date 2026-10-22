# Design: 근거 문서 검색과 숫자 조회

## Context

동기는 proposal.md의 Why를 본다. 따를 기준은 다음과 같다.

- 명세서 v1.5 FR-016, FR-017의 처리, 예외, 완료 기준.
- 기술 명세서 v1.4: §1-2·§1-5(임베딩 모델, 환경 변수), §2-2(Q8·Q9 행), §2-3(doc_candidates, lookups), §2-4(시간 상한), §4-1~4-5(문서 사실, 청크, 검색 방식, 검색 절차, 색인 저장), §5-5(숫자 표 조회), §9 W2.
- schema.sql의 ref.document, ref.doc_chunk, ref.product, ref.product_spec, ref.firmware_release.
- 5번 변경의 `app/llm/client.py`(호출 계층)와 `app/pipeline/state.py`(상태 객체).

## Goals / Non-Goals

**Goals**
- 107개 문서를 청크로 나눠 ref.doc_chunk에 넣고, 4,000건 정답 절이 모두 청크로 있는지 확인한다(근거: §9 W2).
- 하위 문의 하나에서 근거 후보 최대 5개와 조회값 묶음을 만든다(근거: §2-2 Q8·Q9 "근거 후보 ≤ k개").

**Non-Goals**
- 기준 점수와 "관련성 낮음", DB 저장, 화면, 다국어 임베딩 비교(proposal "범위 밖").

## Decisions

### 1. 청크 나누기 (`app/retrieval/chunking.py`)

| 항목 | 정한 것 | 근거 |
|---|---|---|
| 읽을 문서 | ref.document의 path(docs/doc_index.csv와 같음)를 DATA_DIR 아래에서 읽는다 | schema.sql ref.document.path |
| 머리말 | 첫 `---`부터 다음 `---`까지(문서 정보)와 `#` 제목 줄은 청크에 넣지 않는다 | 구현 선택(§4-2는 `##`·`###`만 청크로 정함. 데이터상 첫 `##` 앞에는 머리말·안내 줄·제목뿐) |
| 머리글 | `## 3. 제목` → 절 번호 "3", `### 3.1 제목` → "3.1", `## Q3. 제목` → "Q3". 번호 뒤 점은 뗀다 | §4-2 청크 ID 예 `TG-ACB-AS-2000§3.1`, `FAQ-DRIVE§Q3`. tickets.csv reference_section 값 꼴("3.1", "4") |
| 본문 | 머리글 다음 줄부터 다음 `##`·`###` 머리글 전까지. 앞뒤 빈 줄은 뗀다. 하위 절이 바로 시작하는 `##` 82개는 본문이 비고, 임베딩 입력은 제목뿐이다. 그대로 둔다(정답 절 "3" 같은 값이 있어서) | §4-2. 빈 청크를 두는 것은 구현 선택 |
| 꼬리표 | doc_type, product_code, family는 ref.document에서 복사 | §4-2 꼬리표, schema.sql ref.doc_chunk |
| 임베딩 입력 | `"{문서 제목} > {절 번호} {절 제목}\n{본문}"`. 문서 제목은 ref.document.title(doc_index.csv) | §4-2 "청크 앞에 문서 제목과 절 제목을 붙여 임베딩". 제목 출처는 구현 선택 |

### 2. 임베딩 호출 (`app/llm/embed.py`)

| 항목 | 정한 것 | 근거 |
|---|---|---|
| 모양 | `embed_texts(embedder, call_name, texts) -> list[list[float]]`. 실제 전송은 `Embedder`(embed 하나)가 하고 Gemini용은 `GeminiEmbedder`다 | 5번 변경의 Transport와 같은 방식(구현 선택) |
| 가리기 | 보내기 전에 모든 글을 `prepare_llm_input`에 통과시킨다 | CLAUDE.md 규칙 2 |
| 시간·재시도 | 1회 30초, 실패하면 1회 다시. 두 번 실패하면 `LlmError` | FR-016 예외 2행 "1회 재시도". 30초는 §2-4 언어 모델 기준을 임베딩에도 쓰는 구현 선택 |
| 모델 | `EMBEDDING_MODEL`(기본 `gemini-embedding-2`). 차원은 모델 기본값 | §1-2 "차원은 W2 시작 때 모델 기본값으로 고정", §1-5 |
| 묶음 | 색인할 때는 한 번에 여러 글을 보낸다(묶음 크기 100) | 구현 선택 |

### 3. 색인 작업 (`jobs/build_doc_index.py`)

- 순서: 청크를 만든다 → 임베딩을 채운다 → ref.doc_chunk를 비우고 넣는다(구현 선택. 다시 만드는 시점은 §4-5 "문서가 바뀔 때만").
- 키가 없으면 `--no-embed`로 청크만 넣을 수 있다. 이때 embedding은 비어 있고 검색은 "검색 실패"가 된다(구현 선택).
- 끝에 W2 확인을 돌린다. 4,000건 정답의 (reference_doc_id, reference_section) 쌍 중 청크가 없는 것을 세어, 하나라도 있으면 넣지 않고 실패로 끝낸다(근거: §9 W2 완료 확인). 이 확인은 정답 열을 읽는다. jobs/는 서비스(app/)가 아니라 적재·확인 작업이고 서비스 코드는 이 함수를 부르지 않는다(CLAUDE.md 규칙 6. jobs/를 규칙 6의 예외로 보는 것은 결정 기록 C 항목).
- `jobs/load_reference.py`는 기준정보를 지우기 전에 ref.doc_chunk를 먼저 비운다(proposal Impact, 구현 선택).

### 4. 문서 검색 (`app/retrieval/search.py`)

`search_evidence(conn, embedder, query_en, category_code, product_code, product_family, exact_terms) -> EvidenceResult(candidates, flags)`.

| 단계 | 동작 | 근거 |
|---|---|---|
| 범위 | product_code가 있으면 그 제품 청크 + POL + 그 제품군 FAQ. 없으면 POL + (제품군이 있으면) FAQ와 "제품 문서 미검색" | FR-016 처리 1·예외 1행, §4-4 1번 |
| 우선 종류 | TECH_SPEC·COMPLIANCE→DS, DEFECT→TG, INSTALL→IG·TG, FW_UPDATE→RN, MANUAL→IG·TG·RN·DS·MG, QUOTE·ORDER_LEAD→POL, RETURN→POL, WARRANTY→POL | §4-4 2번 표 |
| 정책 우선 문서 | QUOTE·ORDER_LEAD는 POL-ORDER, RETURN은 POL-RETURN, WARRANTY는 POL-WARRANTY를 먼저 검색한다 | §4-4 2번 표 "(POL-ORDER 우선)". 우선 문서 → 우선 종류 → 범위 전체의 3단계로 넓히는 것은 구현 선택 |
| 넓히기 | 앞 단계의 후보가 비었을 때만 다음 단계로 넓힌다 | §4-4 2번 "결과가 없거나 모두 기준 미만이면". 기준 점수(T27)가 없어 "없을 때"만 본다 |
| 유형이 없음 | 우선 종류 없이 범위 전체 | 구현 선택(5번 변경의 "분류 실패") |
| 점수 | 코사인 유사도(1 − pgvector `<=>` 코사인 거리) + 0.2 × (error_code나 current_fw 문자열이 청크 본문에 있으면 1) | §4-4 3번 |
| 상위 k | 5 | §4-4 4번 |
| 근거 없음 | 후보가 비면 "근거 없음" | §4-4 5번 |
| 검색 실패 | 질문 임베딩이 두 번 실패하거나 범위의 청크에 임베딩이 없으면 후보 없음 + "검색 실패" + "근거 없음" | FR-016 예외 2행 |

후보 모양은 상태 객체의 DocCandidate{chunk_id, doc_id, section_no, title, score}다(근거: §2-3). FR-016 출력의 "절 본문"은 DocCandidate에 칸이 없어, 쓰는 쪽(L4·L8·화면)이 chunk_id로 ref.doc_chunk.text를 읽는다(구현 선택. 상태 객체에 본문 칸을 둘지는 결정 기록 C 항목). 문의 순번은 하위 문의 상태의 seq다.

### 5. 숫자 조회 (`app/retrieval/numbers.py`)

`lookup_numbers(conn, category_code, product_code, received_at, quantity, current_fw, doc_candidates, required_date) -> NumbersResult(lookups, firmware, flags)`. 언어 모델을 부르지 않는다.

| 유형 | 조회 | 출처 | 근거 |
|---|---|---|---|
| QUOTE, ORDER_LEAD | list_price_usd(USD), std_lead_time_weeks(weeks), moq. 수량이 있으면 합계 = 단가 × 수량 | `product_master.csv`, 행 식별자 product_code | FR-017 처리 1, §5-5 |
| TECH_SPEC, COMPLIANCE | 근거 후보의 (doc_id, section_no)와 같은 product_spec 행. 없으면 그 제품의 모든 사양 행 + "사양 항목 선택 필요"(표시 문구는 구현 선택). 사양 행이 하나도 없으면 "표에 없음" | `product_spec_facts.csv`, `{product_code}/{attribute}` | FR-017 처리 2·예외 4행, §5-5, §2-2 Q9 실패 |
| FW_UPDATE, MANUAL(RN 근거가 있을 때) | release_date ≤ 접수일 중 가장 늦은 버전. 고객 버전과 비교해 "업데이트 안내"/"이미 최신"을 조회값 fw_verdict로 둔다. 고객 버전이 없으면 판정은 비움(구현 선택) | `firmware_history.csv`, `{product_code}/{fw_version}` | FR-017 처리 3·출력, §5-5 SQL |
| WARRANTY | warranty_months(months) | `product_master.csv` | §5-5 |

- MANUAL의 "릴리스노트 요청"은 근거 후보에 RN 문서 절이 있는 경우로 본다(구현 선택).
- 사양 attribute를 정하는 입력 중 "요청 사양 항목명"(FR-017 입력)은 L2 코드북 32개에 없는 값이라 이번에는 근거 후보만 쓴다(결정 기록 C 항목).
- 할인가·납기 가산은 계산하지 않는다(근거: §5-5, D14).
- 버전 비교는 점으로 나눈 숫자 묶음으로 한다("3.10" > "3.9")(근거: §5-5).
- 예외: product_code 없음 → "제품 확인 필요", has_firmware가 아닌 FW_UPDATE → "펌웨어 없는 제품 — 분류 재검토", 접수일 이전 버전 없음 → "접수 시점 최신 없음"(근거: FR-017 예외 1~3행).
- 요청 납기(required_date)가 접수일 + 표준 납기 주 수보다 빠르면 "요청 납기 < 표준 납기"를 표시한다(근거: FR-017 예외 5행. 접수일에 주 수를 더해 비교하는 것은 구현 선택).
- 조회값 모양은 상태 객체의 LookupValue{item, value, unit, source_table, source_key}다(근거: §2-3). 항목 이름(list_price_usd, line_total_usd, std_lead_time_weeks, moq, fw_latest_at_intake, warranty_months, 사양은 attribute)은 구현 선택이다.

### 6. 처리 흐름 연결 (`app/pipeline/evidence.py`)

`add_evidence(conn, embedder, state) -> TicketState`: 하위 문의마다 검색과 조회를 돌려 doc_candidates, lookups, flags를 채운다. 제공 항목의 quantity와 current_fw, error_code를 넘긴다(근거: §2-2 Q8·Q9 입력). required_date도 넘긴다(근거: FR-017 예외 5행). query_en이 없으면(분류 실패) 근거 문장을 검색문으로 쓴다(구현 선택).

### 7. 시험

- 대역 임베딩: 글자를 단어로 나눠 고정 크기 벡터에 세는 결정적인 함수. 이것으로 색인을 만들어 AC-016-1~3과 검색 규칙을 시험한다(구현 선택). 실제 임베딩 시험은 `GEMINI_API_KEY`가 있을 때만 돈다.
- AC-016-1·2는 우선 종류·우선 문서 규칙으로 결과가 정해지므로 대역 임베딩으로 확인할 수 있다.
- W2 확인 시험은 gold.ticket_gold의 정답 열을 읽는다(CLAUDE.md 규칙 6의 시험 예외).
- 숫자 조회 시험(AC-017-1~3)은 언어 모델 없이 돈다. 제품 코드·접수 시각은 gold.v_inputs에서 읽고, 수량·고객 버전은 AC 문장의 값을, 유형은 명세서 AC-005-1의 값(CSV1-000004 QUOTE, CSV1-000008 FW_UPDATE)을 넣는다. CSV1-000004는 요청 납기 2025-10-28이 접수일 + 4주(10-29)보다 빨라 "요청 납기 < 표준 납기"가 함께 켜지는 것이 맞다.

## Risks / Trade-offs

- 시험은 같은 개발 DB의 ref.doc_chunk를 대역 벡터로 다시 만든다(기준정보를 다시 넣을 때도 색인이 지워진다). 실제 색인은 시험 뒤 `jobs/build_doc_index.py`로 다시 만들어야 한다(이 변경을 마칠 때 결정 기록 C 항목으로 남긴다).
- 기준 점수가 없어 관련 없는 절도 후보 5개 안에 들어갈 수 있다. 팀 정답지 채점 뒤 T27로 정한다(근거: §4-4 5번).
