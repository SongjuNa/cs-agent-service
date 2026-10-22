# Design: 프로젝트 뼈대

## Context

동기는 proposal.md의 Why를 본다. 따를 기준은 세 가지다.

- 기술 명세서 v1.4 §1-2(기술 스택), §1-5(컨테이너·포트·환경 변수).
- 테이블 정의서 v1.3과 `docs/database/schema.sql`. 이 SQL은 한 트랜잭션이다.
- 프로젝트 구조 1순위 판 2장(폴더 구조).

## Goals / Non-Goals

**Goals**
- `docker compose up` 명령 하나로 db와 api가 뜬다.
- 다음 변경들이 코드를 넣을 폴더가 정해져 있다.

**Non-Goals**
- 기능 코드, 표별 읽기·쓰기 코드, 언어 모델 호출 코드.

## Decisions

### 1. 폴더 구조

```
cs-agent-service/
├── docker-compose.yml        db, api
├── .env.example
├── .gitignore
└── backend/
    ├── Dockerfile
    ├── pyproject.toml
    ├── app/
    │   ├── main.py           FastAPI 앱 (기능 API 없음)
    │   ├── config.py         환경 변수 읽기
    │   ├── api/  pipeline/  llm/  rules/  retrieval/  checks/  masking/  db/
    │   │                      각 폴더에는 __init__.py만 둔다
    └── tests/
        ├── conftest.py
        └── test_service_runtime.py   W7-1, W7-2
```

- 8개 폴더의 역할은 프로젝트 구조 1순위 판 2장과 같다. 폴더마다 빈 `__init__.py` 하나만 둔다. 이 파일은 파이썬이 폴더를 "모듈 묶음(패키지)"으로 알아보게 하는 표시일 뿐 기능 코드가 아니다.
- `tests/rules/`, `tests/acceptance/`는 그 시험을 처음 쓰는 변경에서 만든다.

### 2. DB 초기화: 공식 이미지의 초기화 폴더를 쓴다

- 이미지: `pgvector/pgvector:pg16`(PostgreSQL 16에 pgvector가 들어 있는 공식 이미지).
- `docs/database/schema.sql`을 복사하지 않고 그대로 연결(마운트)해서 `/docker-entrypoint-initdb.d/10_schema.sql`로 보이게 한다. 이 이미지는 데이터 폴더가 비어 있을 때만 이 폴더의 파일을 이름 순서대로 한 번 실행하고, 오류가 나면 멈춘다.
- 이유: SQL을 한 곳(docs/database/schema.sql)에만 두기로 한 결정(프로젝트 구조 1순위 판)을 지킨다. 다른 방법인 "api가 시작할 때 SQL 실행"은 이미 만든 DB에 다시 실행하면 실패하므로 택하지 않았다.
- 표를 다시 만들려면 데이터 볼륨을 지운다: `docker compose down -v`.

### 3. DB 계정은 하나

- api와 시험 모두 docker-compose가 만드는 관리 계정(`POSTGRES_USER`) 하나로 접속한다(조장 결정 2026-10-22).
- schema.sql이 만드는 `cs_service` 역할은 이번에 쓰지 않는다.

### 4. 환경 변수 (.env.example)

| 이름 | 쓰는 곳 | 근거 |
|---|---|---|
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | db 컨테이너 | 이미지가 요구 |
| `DATABASE_URL` | api, 시험 | 기술 명세서 §1-5 |
| `GEMINI_API_KEY` | 지금은 읽기만, 쓰는 곳 없음 | 기술 명세서 §1-5. 값은 비워 둔다 |

§1-5의 나머지(`LLM_MODEL_*`, `EMBEDDING_MODEL`, `LOG_FULL_LLM_IO`, `LLM_MAX_CONCURRENCY`, `SCHEDULER_INTERVAL_SEC`)는 그것을 쓰는 변경에서 추가한다.

### 5. 파이썬 라이브러리

- 실행: `fastapi`, `uvicorn`(서버 실행기), `pydantic-settings`(환경 변수를 Pydantic으로 읽기), `psycopg[binary]`(PostgreSQL 접속).
- 시험: `pytest`, `httpx`(FastAPI 시험용 요청).
- LangGraph, Gemini 라이브러리는 처음 쓰는 변경에서 넣는다.
- Python 3.11(기술 명세서 §1-2). `backend/Dockerfile`은 `python:3.11-slim`에서 시작한다.

### 6. 시험 실행 방법

- W7-1: `DATABASE_URL`로 접속해 스키마별 표 수를 센다.
- W7-2: FastAPI 시험 도구(TestClient)로 `/docs`를 부른다. 서버를 따로 띄우지 않아도 된다. 실제 컨테이너 확인은 README 명령으로 한 번 해 본다(tasks 3).

## Risks / Trade-offs

- [DB를 이미 한 번 띄운 사람은 schema.sql이 바뀌어도 다시 실행되지 않는다] → README에 `docker compose down -v`로 다시 만드는 법을 적는다.
