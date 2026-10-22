"""필수정보 확인 (FR-013, 기술 명세서 §5-4)."""

from dataclasses import dataclass, field

from psycopg import Connection


@dataclass(frozen=True)
class RequiredInfoResult:
    required_info: list[str] = field(default_factory=list)          # field_order 순
    missing_info: list[str] = field(default_factory=list)
    missing_blocking_info: list[str] = field(default_factory=list)
    labels: dict[str, str] = field(default_factory=dict)            # info_field.label
    info_request_needed: bool = False                                # FR-013 출력 "정보 요청 필요 여부"
    flags: list[str] = field(default_factory=list)


def check_required_info(conn: Connection, product_family: str | None, category_code: str | None,
                        provided_info: list[str] | set[str]) -> RequiredInfoResult:
    if not product_family or not category_code:
        return RequiredInfoResult(flags=["제품·유형 확인 뒤 계산됨"])
    rows = conn.execute(
        """SELECT r.field, r.is_blocking, i.label
             FROM ref.required_info_field r JOIN ref.info_field i USING (field)
            WHERE r.family = %s AND r.category = %s
            ORDER BY r.field_order""",
        (product_family, category_code),
    ).fetchall()
    provided = set(provided_info)
    missing = [f for f, _, _ in rows if f not in provided]
    blocking = [f for f, is_blocking, _ in rows if is_blocking and f not in provided]
    return RequiredInfoResult(
        required_info=[f for f, _, _ in rows],
        missing_info=missing,
        missing_blocking_info=blocking,
        labels={f: label for f, _, label in rows},
        info_request_needed=bool(blocking),
    )
