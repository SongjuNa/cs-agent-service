"""SLA 목표 설정 (FR-014, 기술 명세서 §5-4)."""

import logging
from dataclasses import dataclass, field

from psycopg import Connection

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class SlaTarget:
    sla_id: str | None = None
    sla_first_response_target_h: int | None = None
    sla_resolution_target_h: int | None = None
    resolution_definition: str | None = None
    settings: dict[str, str] = field(default_factory=dict)   # sla_setting: clock, at_risk_threshold, pause_rule
    flags: list[str] = field(default_factory=list)


def find_sla_target(conn: Connection, category_code: str | None, customer_tier: str | None,
                    priority: str | None) -> SlaTarget:
    if not priority:
        return SlaTarget(flags=["SLA 미정"])
    row = conn.execute(
        """SELECT s.sla_id, s.first_response_hours, s.resolution_hours, c.resolution_definition
             FROM ref.sla_policy s JOIN ref.inquiry_category c ON c.category = s.category
            WHERE s.category = %s AND s.customer_tier = %s AND s.priority = %s""",
        (category_code, customer_tier, priority),
    ).fetchone()
    if row is None:
        log.warning("SLA 정책 없음: %s/%s/%s", category_code, customer_tier, priority)
        return SlaTarget(flags=["SLA 정책 없음 — 데이터 확인"])
    settings = dict(conn.execute("SELECT key, value FROM ref.sla_setting").fetchall())
    return SlaTarget(*row, settings=settings)
