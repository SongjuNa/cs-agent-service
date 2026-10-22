# Proposal: 프로젝트 뼈대 (setup-project-structure)

## Why

저장소에는 기준 문서(docs/)와 OpenSpec 설정만 있고 실행할 수 있는 코드가 없다. 1순위 기능 18개를 OpenSpec 변경으로 하나씩 만들려면, 그 변경들이 코드를 넣을 폴더와 DB·서버를 띄우는 방법이 먼저 있어야 한다.

이 변경은 기능(FR)이 아니라 기술 명세서 v1.4 §9의 **W7 배포 구성 중 1순위에 필요한 부분**이다. 그래서 요구사항 제목에는 FR 번호 대신 (W7)을, 시나리오 제목에는 AC 번호 대신 W7-n을 붙인다.

## What Changes

- **DB 컨테이너**: PostgreSQL 16 + pgvector. 처음 시작할 때 `docs/database/schema.sql`(테이블 정의서 v1.3)을 실행해 표를 만든다(기술 명세서 §1-5).
  - 컨테이너 = 프로그램과 실행에 필요한 것을 한 상자에 담아, 누구 컴퓨터에서나 같은 명령으로 띄우는 실행 단위.
- **api 컨테이너**: FastAPI 서버. 포트 8000, `/docs`에서 API 설명서(OpenAPI)가 보인다(§1-5). 이번에는 API 기능이 하나도 없다.
- **docker-compose.yml**: 위 두 컨테이너를 명령 하나로 띄운다. 화면(web) 컨테이너는 넣지 않는다(프로젝트 구조 1순위 판: 화면은 개발 서버로 띄움).
- **.env.example**: 필요한 환경 변수 이름만 적은 견본. 실제 값이 든 `.env`는 커밋하지 않는다(CLAUDE.md 규칙 8).
- **backend 폴더 구조**: `app/` 아래 api, pipeline, llm, rules, retrieval, checks, masking, db 8개 폴더와 `tests/`(프로젝트 구조 1순위 판 2장).
- **시험 설정**: pytest로 "DB 표 수가 정의서와 같다", "서버가 뜨고 /docs가 열린다" 두 가지를 확인한다.
- **README.md**: 실행 방법을 추가한다(확인한 명령만 적는다, docs/database/README.md 규칙 5).

## Capabilities

### New Capabilities
- `service-runtime`: 서비스를 실행하는 환경. DB를 정의서대로 만들고 서버를 띄우는 동작.

### Modified Capabilities
- 없음.

## 범위 밖

- 화면(frontend/), web 컨테이너: 9번 변경 `add-ticket-detail-minimal`에서 만든다.
- 기준정보·정답지 적재(W1, W3)와 `jobs/` 폴더: 2번 변경 `load-reference-and-gold`.
- 언어 모델 관련 환경 변수(모델 이름 등)와 라이브러리(LangGraph, Gemini): 그것을 처음 쓰는 변경에서 추가한다.
- 스케줄러(§1-5의 api에 포함): 2순위.
- 기술 명세서 §1-5의 초기화 순서 중 W1~W3, W9, W10 실행: 각 변경에서 붙인다.
- 각 폴더 안의 기능 코드: 폴더만 만들고 빈 파일을 미리 만들지 않는다.

## Impact

- 새 파일: `docker-compose.yml`, `.env.example`, `.gitignore`, `backend/`(Dockerfile, pyproject.toml, app/, tests/).
- 고치는 파일: `README.md`(실행 방법 추가).
- `docs/`와 `docs/database/schema.sql`은 고치지 않는다.
- 근거: 기술 명세서 v1.4 §1-1, §1-2, §1-5, §9(W7); 테이블 정의서 v1.3 §1; 프로젝트 구조 1순위 판 2장·6장.
