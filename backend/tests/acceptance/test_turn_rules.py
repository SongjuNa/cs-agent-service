"""접수함 내 차례·검토 모드 규칙 (변경 add-inbox-turn-depth 결정 2·4). DB 없이 표 그대로 시험한다."""

import pytest

from app.rules.turn import depth_of, turn_of


@pytest.mark.parametrize("status,needs,draft,replied,want", [
    ("RESOLVED", False, False, False, ("DONE", "DONE")),
    ("CLOSED", True, True, True, ("DONE", "DONE")),
    ("ESCALATED", False, False, False, ("DEPT", "WAIT_DEPT")),
    ("ESCALATED", True, True, True, ("DEPT", "WAIT_DEPT")),  # 이관 중이면 다른 조건보다 우선
    ("WAITING_CUSTOMER", True, False, False, ("CUSTOMER", "WAIT_CUSTOMER")),
    ("NEW", True, True, False, ("ME", "SEND_INFO_REQUEST")),
    ("IN_PROGRESS", False, True, True, ("ME", "CHECK_DEPT_REPLY")),  # 부서 회신이 초안보다 먼저
    ("IN_PROGRESS", False, True, False, ("ME", "APPROVE_DRAFT")),
    ("IN_PROGRESS", False, False, False, ("ME", "WRITE_ANSWER")),
])
def test_turn_of(status, needs, draft, replied, want):
    assert turn_of(status, needs, draft, replied) == want


@pytest.mark.parametrize("priority,urgency,needs,want", [
    ("P1", "NONE", False, "DEEP"),
    ("P3", "SAFETY", False, "DEEP"),
    ("P4", "SITE_DOWN", True, "DEEP"),
    ("P3", "NONE", False, "QUICK"),
    ("P4", "DEADLINE", False, "QUICK"),  # 납기 긴급은 설비 정지가 아니다
    ("P3", "NONE", True, "NORMAL"),  # 막는 누락이 있으면 빠른 확인이 될 수 없다
    ("P2", "NONE", False, "NORMAL"),
    (None, "NONE", False, "NORMAL"),
])
def test_depth_of(priority, urgency, needs, want):
    assert depth_of(priority, urgency, needs) == want
