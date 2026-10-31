"""접수함 줄의 "누구 차례인가"와 "검토 모드" (변경 add-inbox-turn-depth, 최신 목업 lib/progress.ts·lib/depth.ts).

순수 함수다. 언어 모델 호출 계층을 import하지 않는다(CLAUDE.md 규칙 1). 입력은 접수함 줄에서 이미 읽은 값뿐이다.
검토 모드의 조건은 팀 제안안이라 확정되면 이 파일만 고친다.
"""

from __future__ import annotations

CLOSED = ("RESOLVED", "CLOSED")
URGENT = ("SAFETY", "SITE_DOWN")  # 목업 isUrgent: 안전·설비 정지


def turn_of(status: str, needs_info: bool, has_unsent_draft: bool, dept_replied: bool,
            auto_state: str = "NONE") -> tuple[str, str]:
    """(turn, next_action). turn: ME·DEPT·CUSTOMER·DONE.

    자동 발송했는데 사후 검수가 아직이면(auto_state=PENDING) 문의가 끝났어도 내 차례다(변경 add-auto-send-views).

    이관 회신이 오면 서버는 ESCALATED → IN_PROGRESS로 바꾸므로, 목업의 "부서 회신 도착"은
    "ESCALATED가 아니고 이관 회신 메시지가 있음"(dept_replied)이다.
    """
    if auto_state == "PENDING":
        return "ME", "REVIEW_AUTO"
    if status in CLOSED:
        return "DONE", "DONE"
    if status == "ESCALATED":
        return "DEPT", "WAIT_DEPT"
    if status == "WAITING_CUSTOMER":
        return "CUSTOMER", "WAIT_CUSTOMER"
    if needs_info:
        return "ME", "SEND_INFO_REQUEST"
    if dept_replied:
        return "ME", "CHECK_DEPT_REPLY"
    if has_unsent_draft:
        return "ME", "APPROVE_DRAFT"
    return "ME", "WRITE_ANSWER"


def depth_of(priority: str | None, urgency_flag: str, needs_info: bool) -> str:
    """DEEP·NORMAL·QUICK. 긴급(안전·설비 정지)이나 P1이면 상세, 막는 누락이 없는 P3·P4면 빠른, 그 밖은 일반.

    1차 규칙이다. 목업의 "검토 표시 걸림", "AI 분류 신뢰도 낮음", "이관 후보"는 저장 위치를 확인한 뒤 더한다.
    """
    if urgency_flag in URGENT or priority == "P1":
        return "DEEP"
    if not needs_info and priority in ("P3", "P4"):
        return "QUICK"
    return "NORMAL"


TURN_RANK = {"ME": 0, "DEPT": 1, "CUSTOMER": 1, "DONE": 2}
