# Tasks: 프로젝트 뼈대

## 1. 저장소 기본 파일

- [x] 1.1 `.gitignore`(.env, 파이썬 캐시·가상환경, 원본 데이터 폴더)와 `.env.example`(design 결정 4의 이름, 값은 견본만)을 만든다. 확인: `.env.example`에 실제 키 값이 없다
- [x] 1.2 `backend/pyproject.toml`(Python 3.11, design 결정 5의 라이브러리)을 만든다. 확인: 새 가상환경에서 `pip install -e "backend[test]"`가 성공한다

## 2. 서버와 폴더

- [x] 2.1 `backend/app/` 아래 8개 폴더와 빈 `__init__.py`, `config.py`, `main.py`(기능 API 없음)를 만든다. 확인: `uvicorn app.main:app` 실행 뒤 `/docs`가 200
- [x] 2.2 `backend/Dockerfile`을 만든다. 확인: `docker compose build api`가 성공한다

## 3. DB와 compose

- [x] 3.1 `docker-compose.yml`(db, api, schema.sql 연결)을 만든다. 확인: `docker compose up -d` 뒤 db 로그에 오류가 없고 `curl localhost:8000/docs`가 200
- [x] 3.2 README.md에 실행 방법(복사, 띄우기, 다시 만들기, 시험)을 추가한다. 확인: 3.1에서 실제로 실행한 명령만 적혀 있다

## 4. 시험

- [x] 4.1 `backend/tests/test_service_runtime.py`에 W7-1, W7-2 시험을 하나씩 만든다
- [x] 4.2 `pytest backend/tests`를 실행해 W7-1, W7-2가 모두 통과하는지 확인한다

## Workflow follow-up

- 조장 확인 뒤 브랜치 `feat/setup-project-structure`를 올리고 PR을 만든다.
- PR 병합 뒤 `/opsx:archive`로 `openspec/specs/service-runtime/`에 반영한다.
