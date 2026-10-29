# Spec Delta: api-contract

## Purpose

서버 API의 응답 모양을 계약(OpenAPI)에 적고, 화면 타입을 그 계약에서 만든다(기술 명세서 v1.4 §1).

## ADDED Requirements

### Requirement: 응답 모양을 계약에 적는다
서버의 모든 API는 성공 응답(200·201·202)의 모양을 이름 있는 스키마로 `/openapi.json`에 실어야 한다(MUST). 응답 값·상태 코드는 바꾸지 않아야 하며, 스키마에 적지 않은 값도 응답에서 빼지 않아야 한다(MUST)(근거: 기술 명세서 v1.4 §1, §8-1, 구현 선택).

#### Scenario: AC-contract-1 모든 API에 응답 모양
- **GIVEN** 서버 앱을 불러온다
- **WHEN** `/openapi.json`을 읽는다
- **THEN** 모든 경로·메서드의 성공 응답이 `components/schemas`의 이름 있는 스키마를 가리킨다

#### Scenario: AC-contract-3 응답 값 그대로
- **GIVEN** 응답 모델을 붙인 서버
- **WHEN** 기존 인수 시험 전체를 돌린다
- **THEN** 모두 통과한다

### Requirement: 화면 타입은 계약에서 만든다
화면의 응답 타입은 저장소의 계약 사본 `frontend/openapi.json`에서 생성해야 하며(MUST), 계약 사본은 서버가 내는 계약과 같아야 한다(MUST)(근거: 기술 명세서 v1.4 §1, 구현 선택).

#### Scenario: AC-contract-2 계약 사본이 최신
- **GIVEN** 서버 앱과 `frontend/openapi.json`
- **WHEN** 서버 계약을 뽑아 사본과 비교한다
- **THEN** 둘이 같다

#### Scenario: AC-contract-4 화면 빌드
- **GIVEN** `npm run gen:api`로 만든 `frontend/src/api.gen.ts`
- **WHEN** `npm run build`를 돌린다
- **THEN** 타입 오류 없이 빌드된다
