# Proposal: 해결사례 직접 검색 (add-case-search)

## Why

목업(ONCE v1.41)의 접수 › 접수 이력 화면은 상담원이 검색어를 넣어 과거 해결사례를 찾는 화면이다. FR-019는 티켓 처리 중 자동 검색만 정하므로, 직접 검색은 FR 초안 06으로 적었고 조장이 승인했다(근거: 목업 기능 FR 초안 문서 "정하실 것 1 → 승인", 2026-10-29, 저장소 밖, 변경 add-similar-cases 범위 밖). FR-019의 색인을 그대로 쓰므로 새 표가 필요 없다(근거: 변경 add-similar-cases 결정 1, 조장 결정 2026-10-29 파일 캐시).

## What Changes

- **검색 `GET /cases`**: 검색어(q, 증상·원인 글), 에러 코드, 제품 코드, 유형으로 해결사례를 찾는다. 에러 코드가 같은 사례를 먼저 두고, 그다음 뜻이 가까운 순으로 20건까지 돌려준다(근거: FR-019 처리 2 "본문 의미와 제품·에러 코드", 구현 선택 20건).
- **사례 상세 `GET /cases/{case_id}`**: 증상, 처음 가설, 원인, 진단 방법, 조치, 교체 부품, 현장 방문, 결과, 해결 시간, 재발 방지, 요약을 돌려준다(근거: resolution_cases.csv 열, 변경 add-similar-cases 결정 1 색인 열을 이 열까지 늘림).
- **뺄 사례**: 팀 정답지 문의의 사례는 색인에 없으므로 나오지 않는다(근거: FR-019 처리 3, D30).
- **상담원 참고용**: 결과는 화면에만 보이고 초안 입력·인용에 쓰지 않는다(근거: FR-019 기능 설명, AC-019-3).
- **화면**: 접수 › 접수 이력에 검색 칸과 결과 표, 사례 상세 패널. 결과의 원래 티켓 번호는 표시만 하고 링크하지 않는다(svc에 없을 수 있음)(근거: 목업 viewSimilar, 구현 선택).

## Capabilities

### New Capabilities
- `case-search`: 상담원이 직접 넣는 검색어로 해결사례를 찾는 API와 화면.

## 범위 밖

- **검색 기록 저장**: 새 표가 필요하므로 하지 않는다(근거: CLAUDE.md 규칙 4).

## Impact

- 새 파일: `backend/app/api/cases.py`, 화면 `CaseSearchPage.tsx`, 시험 `backend/tests/acceptance/test_case_search.py`(근거: design 결정 1~3).
- 고치는 파일: `app/retrieval/cases.py`·`jobs/build_case_index.py`(add-similar-cases가 만든 파일, 색인 열 늘림), `app/main.py`, `app/api/schemas.py`, 화면 `App.tsx`·`api.ts`·`api.gen.ts`·`openapi.json`(근거: design 결정 1~3).
- DB 구조는 고치지 않는다(근거: CLAUDE.md 규칙 4).
