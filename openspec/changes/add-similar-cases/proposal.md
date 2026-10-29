# Proposal: 유사 해결사례 검색 (add-similar-cases)

## Why

고장 계열 문의에서 과거 해결사례 가운데 비슷한 것을 찾아 상담원에게 보여 주면, 상담원이 원인과 조치를 빨리 짐작할 수 있다(근거: 명세서 v1.5 FR-019 기능 설명). FR-019는 여유 시 기능이지만 2026-10-29 조장 결정으로 지금 만든다(근거: CLAUDE.md "여유 시 기능은 FR-019 유사 해결사례 검색과 FR-034 운영 대시보드만 만들고", openspec/config.yaml). 목업(ONCE v1.41)의 티켓 상세 "유사 사례"와 접수 이력 화면이 이 기능을 쓴다(근거: 갭 목록 문서 2026-10-29, 저장소 밖).

## What Changes

- **새 처리 단계 Q8b**: 고장 진단(Q8a) 뒤에 둔다. 유형이 DEFECT·INSTALL·WARRANTY·FW_UPDATE·RETURN인 하위 문의에서만 돈다(근거: FR-019 처리 1, 기술 명세서 v1.4 §4-7 "Q8a 뒤 Q8b", AC-019-2).
- **검색**: 문의 본문의 뜻과 제품·에러 코드로 해결사례를 찾아 비슷한 순으로 3건까지 고른다(근거: FR-019 처리 2 "3건(제안)").
- **뺄 사례**: 팀 정답지 문의(eval.gold_set.source_ticket_id)에서 나온 사례는 색인에 넣지 않는다(근거: FR-019 처리 3, D30, 기술 명세서 §4-7). 시연에서 운영진 문의를 불러오면 그 문의 자신의 해결사례(같은 ticket_id)가 1순위로 나오므로, 결과에서 ticket.source_ticket_id와 같은 사례도 뺀다(근거: resolution_cases.csv 800건 모두 tickets.csv의 resolution_case_id와 1:1 연결, 예 CSV1-000017 → RC-0006. 구현 선택).
- **자료 보관**: 해결사례와 그 벡터는 고장 사전처럼 파일 캐시(Git에 올리지 않음)와 서버 메모리에 둔다. 새 표를 만들지 않는다(근거: 조장 결정 2026-10-23 고장 사전 방식, CLAUDE.md 규칙 4·6. 기술 명세서 §4-7은 "색인 표는 ref에 둔다"라고 적어 다르므로 조장 확인 대기).
- **기록**: 찾은 사례 ID와 점수를 실행 기록 Q8b 단계의 output_json에 남긴다(근거: FR-019 처리 5, §4-7 출력).
- **초안에 넣지 않음**: 해결사례는 답변 초안(L4) 입력에 넣지 않고 인용하지도 않는다(근거: FR-019 기능 설명 "고객에게 가는 글의 근거로는 쓰지 않는다", AC-019-3, openspec/config.yaml 설계 원칙 5).
- **화면**: 티켓 상세 "시스템이 판단한 것" 탭의 하위 문의 구역에 "비슷한 해결사례" 3건(사례 ID, 원인, 조치, 결과)을 보인다. 없으면 "비슷한 사례 없음", 실패하면 "사례 검색 실패"(근거: FR-019 출력·예외 표. 목업은 "보낼 것" 탭 아래에 두어 다르며, FR 출력 "가운데 칸"을 따른다).

## Capabilities

### New Capabilities
- `similar-cases`: 고장 계열 하위 문의의 유사 해결사례 검색과 표시.

## 범위 밖

- **접수 이력 화면의 사례 검색(상담원이 직접 검색어를 넣는 화면)**: FR-019는 티켓 처리 중 자동 검색만 정한다(근거: FR-019 처리·출력). 목업의 접수 이력 화면은 FR 초안으로 따로 묻는다.
- **FR-046 few-shot과 같은 색인 공유**: FR-046은 만들지 않으므로, 임베딩 모델만 문서 청크와 같게 쓴다(근거: FR-019 처리 4, §4-7 "문서 청크와 같은 임베딩 모델", openspec/config.yaml).

## Impact

- 새 파일: `jobs/build_case_index.py`(적재), `backend/app/retrieval/cases.py`(검색), `backend/app/pipeline/similar.py`(Q8b 노드), 시험 `backend/tests/acceptance/test_similar_cases.py`(근거: design 결정 1~5).
- 고치는 파일: `app/pipeline/graph.py`·`reprocess.py`(노드 자리), `app/pipeline/runlog.py`·`app/db/store.py`(Q8b 기록), `app/db/detail.py`·`app/api/schemas.py`(상세 응답), 화면 `DetailTabs.tsx`·`api.ts`·`api.gen.ts`·`openapi.json`(근거: design 결정 3~4).
- DB 구조는 고치지 않는다. 실행 기록 agent_step의 step_name에는 CHECK가 없어 Q8b를 그대로 쓴다(근거: CLAUDE.md 규칙 4, schema.sql agent_step).
