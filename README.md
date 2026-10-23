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

`.env`의 비밀번호를 바꾸면 `DATABASE_URL`의 비밀번호도 같이 바꾼다. `GEMINI_API_KEY=` 뒤에 Gemini 키를 넣는다(없으면 문의 처리와 실제 Gemini 시험이 돌지 않는다). `.env`는 커밋하지 않는다.

### 2. DB와 서버 띄우기

```bash
docker compose up -d --build
```

- db: PostgreSQL 16 + pgvector. 처음 뜰 때 `docs/database/schema.sql`을 실행해 표를 만든다.
- api: http://localhost:8000/docs 에서 API 설명서를 볼 수 있다.

### 3. 기준정보·정답지 넣기

운영진 데이터 폴더 `CS_AI_Agent_Training_Data_v1/`을 저장소 안 `data/` 아래에 둔다(`data/CS_AI_Agent_Training_Data_v1/ref/…`). `data/`는 커밋되지 않는다. 다른 곳에 두었으면 `.env`의 `DATA_DIR`를 그 경로로 바꾼다.

5번의 가상환경을 만들어 켠 상태에서, 저장소 루트에서 실행한다.

```bash
python -m jobs.load_reference
python -m jobs.load_gold
```

- load_reference: ref 표 24개에 기준정보를 넣는다(테이블 정의서 §2).
- load_gold: gold 표에 tickets.csv 4,000건, resolution_cases.csv 800건을 넣는다(테이블 정의서 §3).
- 다시 실행하면 비우고 다시 넣는다. 다른 표(svc 등)가 기준정보를 가리키고 있으면 아무것도 바꾸지 않고 멈춘다.

이어서 문서 색인을 만든다. 문서 107개를 절 895개로 나누고 Gemini 임베딩으로 바꿔 넣는다(키 필요, 20초쯤).

```bash
python -m jobs.build_doc_index
```

기준정보를 다시 넣거나 시험(5번)을 돌린 뒤에는 색인이 비거나 시험용 가짜 색인으로 바뀌므로 이 명령을 다시 실행한다.

### 4. DB를 처음부터 다시 만들기

schema.sql은 DB가 비어 있을 때 한 번만 실행된다. schema.sql이 바뀌었으면 데이터를 지우고 다시 띄운다.

```bash
docker compose down -v
docker compose up -d --build
```

### 5. 시험 실행

DB를 띄우고 3번 데이터 폴더를 둔 상태에서 실행한다. 시험이 적재 작업을 직접 실행한다.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e "backend[test]"
cd backend
pytest
```

### 6. 화면 띄우기

2번(DB·API 서버)과 3번(기준정보·정답지·색인)을 마친 상태에서, 준비물로 Node.js 18 이상이 더 필요하다.

```bash
cd frontend
npm install
npm run dev
```

다른 창에서 저장소 루트로 돌아와 정답지 문의를 접수 API로 넣는다. 출력되는 화면 주소(http://localhost:5173/tickets/…)를 열면 티켓 상세 화면이 보인다. 처리(Gemini 호출)가 끝날 때까지 1분쯤 "처리 중"으로 보인다.

```bash
python -m jobs.run_tickets CSV1-000017 CSV1-000004
```
