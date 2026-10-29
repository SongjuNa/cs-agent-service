# Design: API 응답 모양을 계약에 적기

## Context

서버는 FastAPI(파이썬 웹 서버 틀)이고, FastAPI는 라우터 함수에 `response_model`을 주면 그 모양을 `/openapi.json`에 싣는다(근거: 기술 명세서 v1.4 §1 서버 행). 지금은 27개 모두 `-> dict` 또는 `-> list[dict]`이라 응답 모양이 없다(근거: `bootcamp/frontend-sdd/openapi_2026-10-29.json`). 화면 타입은 `frontend/src/api.ts`가 서버 코드(`backend/app/db/detail.py` 등)를 보고 손으로 옮긴 것이다(근거: 구현 선택 C-45).

## Goals / Non-Goals

- 목표: 27개 API의 200 응답 모양이 계약에 있고, 화면 타입은 계약에서 만든다.
- 목표 아님: 응답 값·상태 코드를 바꾸는 것, 새 API, 오류 응답 모양.

## Decisions

### 1. 모델 위치와 이름 (`backend/app/api/schemas.py`)

| 항목 | 정한 것 | 근거 |
|---|---|---|
| 파일 | 응답 모델은 `backend/app/api/schemas.py` 한 곳. 요청 모델(TicketIn 등)은 지금 자리에 둔다 | 구현 선택 |
| 이름 | 화면 타입 이름을 그대로 쓴다(Inbox, InboxRow, Detail, SubTicket, Draft, Workload …). 생성 타입과 손 타입을 1:1로 맞추기 위해 | 구현 선택, `frontend/src/api.ts` |
| 열 이름 | 응답 열 이름은 지금 코드가 돌려주는 이름 그대로(테이블 정의서 v1.3 열 이름) | CLAUDE.md 규칙 4 |
| 대상 | §8-1 API 목록의 27개 전부 | 기술 명세서 v1.4 §8-1 |

### 2. 동작을 바꾸지 않는 장치

| 위험 | 막는 법 | 근거 |
|---|---|---|
| 모델에 없는 값이 응답에서 빠짐(FastAPI는 response_model에 없는 값을 버린다) | 모든 모델에 `extra="allow"`(적지 않은 값도 그대로 내보냄) | 구현 선택 |
| 실제 값과 종류가 달라 서버 오류(500)가 남 | 값이 매번 다른 곳(실행 단계 출력, 규칙 행, 검사 detail, 「왜?」 값)은 `dict[str, Any]`로 두고, 비어 있을 수 있는 칸은 모두 `None` 허용 | 구현 선택 |
| 숫자 종류 | DB numeric(남은 시간 등)은 지금처럼 숫자로 나간다(FastAPI 기본 변환과 같음) | 구현 선택 |
| 오류 응답 | 400·404·409는 지금처럼 HTTPException·JSONResponse 그대로. response_model은 200에만 적용됨 | 구현 선택 |

### 3. 모양이 정해지지 않은 값

`evidence_rows[].why`, `diagnosis`, `escalation`, `runs/{id}/steps`의 input_json·output_json, `timeline` 항목의 나머지 칸은 종류마다 칸이 다르다(근거: `backend/app/db/detail.py` `_evidence_rows`, `backend/app/db/timeline.py`). 공통 칸만 이름을 적고 나머지는 `extra="allow"`로 둔다(구현 선택).

### 4. 화면 타입 생성

| 항목 | 정한 것 | 근거 |
|---|---|---|
| 도구 | openapi-typescript(계약 → TypeScript 타입). 호출 코드는 지금 `api.ts`의 `call()`을 그대로 쓴다 | 구현 선택 |
| 계약 사본 | `frontend/openapi.json`을 저장소에 둔다. 서버를 켜지 않고도 화면을 빌드하게 | 구현 선택 |
| 명령 | `backend`에서 계약을 뽑는 `jobs/export_openapi.py`, `frontend`에서 `npm run gen:api` | 구현 선택 |
| `api.ts` | 응답 interface를 `api.gen.ts`의 `components["schemas"]["…"]` 별칭으로 바꾼다. 화면 파일(InboxPage.tsx 등)의 import는 그대로 | 구현 선택 |
| C-45 | "타입은 손으로" → "응답 타입은 OpenAPI에서 생성"으로 바꾼다. 개발_결정_기록.md 수정은 조장 전후 비교 승인 뒤 | 구현 선택, 조장 작업 방식(전후 비교) |

### 5. 시험 (`backend/tests/acceptance/test_api_contract.py`)

| 시험 | 확인하는 것 | 근거 |
|---|---|---|
| AC-contract-1 | `/openapi.json`의 모든 경로·메서드 200(또는 201·202) 응답이 이름 있는 스키마를 가리킨다 | 구현 선택 |
| AC-contract-2 | `frontend/openapi.json`이 서버가 지금 내는 계약과 같다 | 구현 선택 |
| AC-contract-3 | 기존 인수 시험 전체가 그대로 통과한다(응답 값이 바뀌지 않음) | CLAUDE.md 규칙 7 |

## Risks / Trade-offs

- `extra="allow"`라 모델에 빠진 칸이 있어도 시험이 못 잡는다. 대신 응답이 줄지는 않는다. 화면이 쓰는 칸은 `api.ts`와 대조해 모두 이름을 적는다(구현 선택).
- 기존 인수 시험은 PostgreSQL이 있어야 돈다(근거: `backend/tests/conftest.py`). 이 환경에서 DB를 띄우지 못하면 AC-contract-1·2만 돌리고 그렇게 보고한다(구현 선택).
