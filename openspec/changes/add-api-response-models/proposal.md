# Proposal: API 응답 모양을 계약에 적기 (add-api-response-models)

## Why

화면 쪽 타입을 서버 계약(OpenAPI, 서버가 자동으로 만드는 API 설명서)에서 만들려면 응답 모양이 계약에 있어야 한다(근거: 기술 명세서 v1.4 §1 기술 스택 표 "OpenAPI 문서가 자동으로 나와 화면 쪽 타입을 생성할 수 있다"). 그런데 지금 API 27개는 응답을 모양이 정해지지 않은 dict(이름과 값을 아무렇게나 담는 묶음)로 돌려주어, `/openapi.json`의 응답 칸이 9개는 비어 있고 18개는 "아무 객체"로만 나온다(근거: 2026-10-29 main에서 뽑은 `bootcamp/frontend-sdd/openapi_2026-10-29.json`). 그래서 화면 타입은 `frontend/src/api.ts`에 손으로 옮겨 적었고(근거: 구현 선택 C-45, `openspec/changes/archive/2026-10-22-add-ticket-detail-minimal/design.md`), 서버가 바뀌면 화면이 틀린 것을 실행해 봐야 안다. 조장이 2026-10-29 응답 모델을 붙이기로 정했다(근거: 구현 선택, 프로젝트 스레드 "API 계약 고정하고 목업과 비교" 2026-10-29 결정).

## What Changes

- **응답 모델**: API 27개마다 응답 모양을 Pydantic 모델(파이썬에서 값의 이름과 종류를 적어 두는 틀)로 적고 `response_model`로 계약에 싣는다(근거: 기술 명세서 v1.4 §1 서버 행 "Pydantic v2", §8-1 API 목록).
- **동작은 바꾸지 않는다**: 돌려주는 값·상태 코드·오류 모양은 그대로다. 모델에 적지 않은 값도 버리지 않는다(근거: 구현 선택, design 결정 2).
- **화면 타입 자동 생성**: `frontend/openapi.json`(계약 사본)에서 `frontend/src/api.gen.ts`를 만들고, `api.ts`의 응답 타입을 생성 타입으로 바꾼다. C-45를 바꾼다(근거: 기술 명세서 v1.4 §1, 구현 선택 design 결정 4).
- **계약 시험**: 모든 API의 200 응답에 이름 있는 모양이 있는지, 계약 사본이 서버와 같은지 시험한다(근거: CLAUDE.md 규칙 7, design 결정 5).

## Capabilities

### New Capabilities
- `api-contract`: 서버 API의 응답 모양을 계약에 적고, 화면 타입을 그 계약에서 만든다.

## 범위 밖

- **새 API·새 화면**: 목업(ONCE 목업 v1.41)에만 있는 화면 16개와 고객 원문 번역·유사 사례·직접 작성은 다른 변경이다(근거: openspec/config.yaml "여유 시 기능은 만들지 않는다", 범위 결정 대기).
- **오류 응답(400·404·409) 모양**: 이번에는 200 응답만 적는다(근거: 구현 선택).
- **저장소 반영**: 로컬 브랜치 `feat/api-response-models`에서만 하고 push·PR 하지 않는다(근거: 조장 지시 2026-10-29 00:42).

## Impact

- 새 파일: `backend/app/api/schemas.py`, `backend/tests/acceptance/test_api_contract.py`, `frontend/openapi.json`, `frontend/src/api.gen.ts`(근거: design 결정 1·4·5).
- 고치는 파일: `backend/app/api/*.py`(라우터 9개에 `response_model`), `frontend/src/api.ts`, `frontend/package.json`(생성 명령)(근거: design 결정 1·4).
- DB 구조는 고치지 않는다(근거: CLAUDE.md 규칙 4).
