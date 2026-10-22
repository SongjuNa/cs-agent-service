# CLAUDE.md — AI 코딩 도구 작업 규칙

이 저장소는 OpenSpec으로 명세를 먼저 합의하고 코드를 쓰는 방식(SDD)으로 개발한다.

## 무엇을 만들지
- 만들 기능은 `openspec/changes/<변경 이름>/`의 proposal·specs·design·tasks를 따른다. 여기에 없는 기능은 만들지 않는다.
- 현재 범위는 MVP 1순위 18개 기능이다(목록은 `openspec/config.yaml`). 2순위 이후 기능은 만들지 않는다.

## 기준 문서 (`docs/`)
- 기능 요구사항 명세서 v1.5: `docs/requirements/functional-requirements.md`
- 화면 정의서 v2: `docs/technical/screen-specification.md`
- 기술 명세서 v1.4: `docs/technical/technical-specification.md`
- 에이전트 설계서 v1.1: `docs/technical/agent-design.md`
- 테이블 정의서 v1.3: `docs/database/table-specification.md`, DB 생성 스크립트 `docs/database/schema.sql`

문서와 코드, 또는 문서끼리 값·이름이 다르면 임의로 고치지 말고 사람에게 묻는다.

## 지켜야 할 규칙
1. 우선순위·부서·필수정보·SLA 목표를 정하는 규칙 코드는 언어 모델 호출 코드를 import하지 않는다.
2. 언어 모델(Gemini)은 한 곳(언어 모델 호출 계층)에서만 부른다. 모든 입력은 보내기 직전, 실행 로그는 저장 직전 개인정보 가리기를 거친다. 원문은 DB에 그대로 저장한다.
3. 고객에게 가는 메시지는 DRAFT로만 만든다. SENT로 바꾸는 것은 상담원 승인 API뿐이다.
4. 표·열 이름은 테이블 정의서 v1.3 그대로 쓴다. 새 표나 열이 필요하면 만들지 말고 사람에게 묻는다.
5. 고객 본문은 프롬프트 안에서 `<customer_message>` 안에만 넣는다.
6. 정답지(gold 스키마)의 정답 열은 서비스 코드에서 읽지 않는다. 서비스는 `gold.v_inputs`만 읽는다. 정답과 비교하는 시험·채점 코드만 예외다.
7. 명세서 완료 기준(AC) 하나마다 테스트 하나를 만든다.
8. API 키, `.env`, 운영진 원본 데이터 파일은 커밋하지 않는다.

## 작업 방식
- 변경 하나 = 브랜치 하나(`feat/모듈-내용`) = PR 하나. `main` 병합은 팀 승인 후.
- OpenSpec 명령: `/opsx:explore`(생각 정리) → `/opsx:propose <이름>`(문서 초안) → 사람 검토 → `/opsx:apply`(구현) → `/opsx:archive`(완료 기록).
