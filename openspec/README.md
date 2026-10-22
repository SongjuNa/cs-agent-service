# OpenSpec — SDD 명세 관리 준비

이 폴더는 **Specification-Driven Development(SDD)** 를 위한 OpenSpec의 작업 영역으로 사용할 예정입니다. SDD 자체가 이 폴더를 요구하는 것은 아닙니다.

## 역할
- `specs/`: 현재 합의된 기능의 명세
- `changes/`: 기능 추가·변경 제안 및 작업 단위 구현·검증 계획

## docs와의 구분
- [`docs/`](../docs/README.md): 기획·요구사항·아키텍처 등 프로젝트 공식 기준
- `openspec/`: 구체적 기능 변경 단위의 명세·작업·검증 과정
- 각 변경에는 해당 `FR-...`/`NFR-...` ID를 표시하여 추적합니다. 같은 내용을 불필요하게 복제하지 않습니다.

## 적용 순서
1. 팀에서 기능 요구사항과 인수 기준을 합의합니다.
2. OpenSpec 공식 도구를 실제로 도입할 때 해당 버전의 `openspec init`을 실행합니다.
3. 기능 변경을 제안하고 명세 및 작업 계획을 검토한 후 구현합니다.
4. 테스트·리뷰 이후 완료된 변경을 확정 명세에 반영합니다.

2026-10-22 OpenSpec 1.14.3으로 초기화했습니다(`openspec init --tools claude`). 팀 공통 규칙은 `config.yaml`, Claude Code 명령은 `.claude/`에 있습니다. `specs/`는 비어 있으며, 기능을 만들 때마다 변경(change)의 명세가 archive 단계에서 쌓입니다(조장 결정: 기준 문서는 `docs/`). 사전 합의 없이 예시 기능 명세를 생성하지 않습니다.
