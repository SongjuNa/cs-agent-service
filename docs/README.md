# 프로젝트 산출물 관리

이 디렉터리는 LS전선 해외 고객 C/S 대응 AI Agent 부트캠프 프로젝트의 **공식 산출물**을 관리합니다. 4인 팀의 유지보수 부담을 줄이기 위해 문서별 **원본 하나(Single Source of Truth)** 를 원칙으로 합니다.

| 폴더 | 목적 | 권장 원본 |
|---|---|---|
| [planning](planning/README.md) | 프로젝트 목적·범위·일정·역할 | Markdown |
| [requirements](requirements/README.md) | 기능·비기능 요구사항과 인수 조건 | Markdown |
| [technical](technical/README.md) | 기술 명세·아키텍처·Agent 설계 | Markdown + Mermaid |
| [database](database/README.md) | ERD·데이터 모델 및 제약조건 | SQL + Markdown |
| [design](design/README.md) | LS전선 CI 참조와 문서 디자인 토큰 | Markdown + CSS |

## 문서 작성·버전 관리 원칙

1. 문서·폴더 이름은 영문 소문자 **kebab-case**, 본문은 한국어를 허용합니다.
2. 현재 유효한 문서는 **고정된 파일명** 하나로 유지합니다. `v1.0/`, `v1.1/` 같은 복제 폴더를 만들지 않습니다.
3. 문서 상단에 `version`, `status`, `updated`, `owner` 등 필요한 메타데이터를 표시합니다. 실제 값은 작성자가 입력합니다.
4. 수정 이력은 Git 커밋과 Pull Request로 추적합니다. 주요 제출 시점은 Git 태그 또는 GitHub Release로 기록합니다. **태그는 문서 하나가 아니라 저장소의 커밋 전체를 가리킵니다.**
5. Markdown을 원본으로 유지하고 **HTML/PDF는 제출용 생성물**로 취급합니다. Markdown과 HTML을 각각 독립 수정하지 않습니다.
6. 데이터베이스는 `database/schema.sql`을 편집 원본으로 사용하고, 표·열 설명은 `database/table-specification.md`에 둡니다. 도식은 필요할 때 SQL에서 생성합니다. 구현이 시작되면 실제 DB와 SQL 사이의 차이를 점검합니다.
7. API 구현이 시작되면 OpenAPI 스키마를 API 계약의 기준으로 활용하고, 다른 문서에 같은 스키마를 중복 복사하지 않습니다.
8. WBS 등 변경 빈도가 높은 일정은 팀이 정한 Notion 원본을 활용할 수 있습니다. Git에는 확정된 내보내기본만 필요할 때 보관합니다.
9. 변경 제안과 구현 단위 명세는 [`../openspec/`](../openspec/README.md)에서 관리합니다. 요구사항 ID(FR/NFR)로 기획·요구사항과 연결합니다.

## 권장 작업 흐름

요구사항 확정 → 영향 받는 명세 수정 및 리뷰 → 기능별 OpenSpec 작업 → 구현/테스트 → PR 검토 → 필요한 제출용 HTML/PDF 생성.

**현재 디렉터리의 README는 관리 안내서이며, 기획서·명세서의 실제 내용이 작성되었다는 의미가 아닙니다.**
