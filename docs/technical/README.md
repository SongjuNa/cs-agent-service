# technical — 기술·시스템 설계

## 목적
시스템의 기술 선택, 구성요소, 책임, 연결 관계와 **AI Agent 실행 설계**를 설명합니다.

## 관리 대상
- `technical-specification.md` — 기술 스택과 주요 설계 결정(확정 후 추가)
- 필요 시 `architecture.md`, `agent-workflow.md` — 큰 다이어그램을 분리해야 할 때만 추가

## 주요 내용
- Frontend·Backend·LLM·RAG·Tool·DB의 경계와 책임
- Agent 역할, State, 분기·종료·실패 및 Human-in-the-Loop 경로
- 외부 시스템 의존성, 재시도·타임아웃, 개인정보·로깅 등 주요 비기능 설계
- 주요 기술 선택과 트레이드오프

## 형식 및 규칙
- Markdown 본문에 Mermaid 다이어그램을 우선 사용하고, SVG가 필요한 경우 승인된 이미지 자산으로 관리합니다.
- OpenAPI 계약은 구현 시 자동 생성/별도 YAML로 관리하되 이 폴더에 동일 내용을 중복 작성하지 않습니다.
- 이 폴더는 **프로젝트 차원의 설계**를 설명합니다. 작업별 구현 계획과 변경 명세는 [OpenSpec](../../openspec/README.md)을 활용합니다.
- 실제로 확정하지 않은 모델·기술 선택은 `결정 필요`로 표시합니다.
