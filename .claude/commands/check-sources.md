---
name: "Check Sources"
description: "propose 문서의 근거 점검표 만들기 (기계 점검 + 검증 에이전트)"
category: "Workflow"
---

OpenSpec 변경 `$ARGUMENTS`의 propose 문서를 점검해 `openspec/changes/$ARGUMENTS/근거_점검표.md`를 만든다. 문서는 고치지 않는다.

1. 기계 점검을 실행한다: `python scripts/check_sources.py $ARGUMENTS`
   - 없는 FR·AC 번호, 절 번호, ticket_id, 규칙 ID, 표·열 이름과, 근거 꼬리표가 없는 줄이 나온다.
2. 하위 에이전트 `source-checker`를 변경 이름 `$ARGUMENTS`로 부른다. 초안을 쓴 대화의 생각이나 설명은 넘기지 않는다. 변경 이름만 넘긴다.
3. 두 결과를 합쳐 `근거_점검표.md`를 쓴다. 순서는 다음과 같다.
   1. 사람 확인 필요 (기준 문서끼리 또는 문서와 데이터가 다른 곳)
   2. 기계 점검 결과
   3. 검증 에이전트의 의심 목록과 빠진 요구
   4. 집계
4. 점검표를 사람에게 보여 준다. 초안을 고칠지는 사람이 정한다. 고친 뒤에는 이 명령을 다시 실행한다.
