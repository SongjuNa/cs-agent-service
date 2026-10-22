# CS Agent Service

LS전선 해외 고객 C/S 대응 AI Agent 프로젝트

## 프로젝트 개요

- 프로젝트 유형: AI Agent 부트캠프
- 개발 인원: 4명
- 문서 관리: GitHub
- 개발 방식: SDD (OpenSpec)

## 실행 방법

준비물: Docker(Docker Compose 포함), Python 3.11

### 1. 설정 파일 만들기

```bash
cp .env.example .env
```

`.env`의 비밀번호를 바꾸면 `DATABASE_URL`의 비밀번호도 같이 바꾼다. `.env`는 커밋하지 않는다.

### 2. DB와 서버 띄우기

```bash
docker compose up -d --build
```

- db: PostgreSQL 16 + pgvector. 처음 뜰 때 `docs/database/schema.sql`을 실행해 표를 만든다.
- api: http://localhost:8000/docs 에서 API 설명서를 볼 수 있다.

### 3. DB를 처음부터 다시 만들기

schema.sql은 DB가 비어 있을 때 한 번만 실행된다. schema.sql이 바뀌었으면 데이터를 지우고 다시 띄운다.

```bash
docker compose down -v
docker compose up -d --build
```

### 4. 시험 실행

DB를 띄운 상태에서 실행한다.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e "backend[test]"
cd backend
pytest
```
