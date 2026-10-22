# Spec Delta: service-runtime

## Purpose

서비스를 실행하는 환경을 정한다. 팀원 누구나 같은 명령으로 테이블 정의서대로 만든 DB와 API 서버를 띄울 수 있게 한다(기술 명세서 v1.4 §1-5, W7).

## ADDED Requirements

### Requirement: DB는 테이블 정의서대로 만들어진다 (W7)
DB 컨테이너는 PostgreSQL 16 + pgvector여야 하며(MUST), 빈 상태로 처음 시작할 때 `docs/database/schema.sql`을 실행해야 한다(MUST). 실행이 끝난 DB의 스키마별 표 수는 테이블 정의서 v1.3 §1과 같아야 한다(SHALL). 표 수는 뷰를 뺀 표만 센다.

#### Scenario: W7-1 처음 띄운 DB의 표 수가 정의서와 같다
- **GIVEN** DB 데이터가 없는 상태
- **WHEN** 실행 명령으로 DB 컨테이너를 처음 띄운다
- **THEN** 표 수가 ref 25, gold 2, svc 11, scoring 11, eval 8이다
- **AND** `gold.v_inputs` 뷰가 있다

### Requirement: API 서버가 뜨고 설명서를 보여 준다 (W7)
API 서버는 포트 8000에서 떠야 하며(MUST), `/docs` 주소에서 OpenAPI 설명서를 보여 줘야 한다(SHALL). 서버는 환경 변수 `DATABASE_URL`로 DB에 접속해야 한다(MUST).

#### Scenario: W7-2 /docs가 열린다
- **WHEN** 실행 명령으로 db와 api를 띄운 뒤 `http://localhost:8000/docs`를 연다
- **THEN** 응답 코드가 200이다
