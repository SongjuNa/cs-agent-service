"""상담원의 분류 직접 수정 (명세서 v1.5 FR-030 처리 6, AC-030-5, AC-010-3, AC-013-3, 기술 명세서 v1.4 §2-4·§8-1 PATCH).

고친 값은 sub_ticket 열과 inquiry_field(source AGENT)에 두고, 무엇을 고쳤는지는 AGENT_EDIT 실행의 Q2 단계
input_json에 남긴다(새 열 없음, C-110). 다시 돌기는 pipeline/reprocess.reuse가 한다. 고친 기록 읽기는 db/runs.agent_edits.
규칙 판정은 하지 않는다(규칙은 다시 돌기의 Q2~Q6이 한다).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from psycopg import Connection

from app.db.runs import latest_pipeline_run, ticket_of
from app.db.store import start_run

EDITABLE = ("category_code", "urgency_flag", "product_code", "return_kind")
RETURN_KINDS = ("DEFECT", "NON_DEFECT")  # SCR-03 C-05 "불량/비불량 선택"
MSG_NOTHING = "고칠 값이 없음"
MSG_BAD = "{} 값이 올바르지 않음"
MSG_BUSY = "처리 중"
MSG_CLOSED = "종료된 문의는 바꿀 수 없음"  # 화면 정의서 v1 SCR-03-P3 오류 문구
MSG_CONFLICT = "다른 사용자가 변경함. 새로고침"  # FR-030 예외 4행, SCR-03-P8


class EditError(ValueError):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


@dataclass
class Edit:
    category_code: str | None = None
    urgency_flag: str | None = None
    product_code: str | None = None
    return_kind: str | None = None
    received_fields: list[dict[str, Any]] = field(default_factory=list)  # [{field, value}]
    expected_version: int | None = None


def _exists(conn: Connection, sql: str, value: str) -> bool:
    return conn.execute(sql, (value,)).fetchone() is not None


def _check(conn: Connection, sub: dict[str, Any], edit: Edit) -> dict[str, dict[str, Any]]:
    """바뀌는 항목 {이름: {from, to}}. 값이 틀리면 EditError(400)."""
    checks = {
        "category_code": "SELECT 1 FROM ref.inquiry_category WHERE category = %s",
        "urgency_flag": "SELECT 1 FROM ref.urgency WHERE urgency = %s",
        "product_code": "SELECT 1 FROM ref.product WHERE product_code = %s",
    }
    changes: dict[str, dict[str, Any]] = {}
    for name in EDITABLE:
        value = getattr(edit, name)
        if value is None or value == sub[name]:
            continue
        if name == "return_kind":
            category = edit.category_code or sub["category_code"]
            if value not in RETURN_KINDS or category != "RETURN":
                raise EditError(MSG_BAD.format(name))
        elif not _exists(conn, checks[name], value):
            raise EditError(MSG_BAD.format(name))
        changes[name] = {"from": sub[name], "to": value}
    known = {r[0] for r in conn.execute("SELECT field FROM svc.inquiry_field WHERE sub_ticket_id = %s",
                                        (sub["sub_ticket_id"],)).fetchall()}
    received = []
    for item in edit.received_fields:
        name = item.get("field")
        if name not in sub["required_info"]:
            raise EditError(MSG_BAD.format(name or "field"))
        if name not in known:
            received.append(name)
    if received:
        changes["received_fields"] = {"from": None, "to": received}
    if not changes:
        raise EditError(MSG_NOTHING)
    return changes


def apply_edit(conn: Connection, sub_ticket_id: str, edit: Edit, agent_id: str, at: datetime) -> dict[str, Any]:
    """고친 값을 저장하고 AGENT_EDIT 실행을 연다. 돌려주는 값: {run_id, changes, version}.

    실행은 응답 전에 연다(화면이 바로 "처리 중"을 본다, 17번 다시 시도와 같다).
    """
    ticket_id = ticket_of(sub_ticket_id)
    with conn.transaction():
        if conn.execute("SELECT 1 FROM svc.ticket WHERE ticket_id = %s FOR UPDATE", (ticket_id,)).fetchone() is None:
            raise LookupError(sub_ticket_id)
        cur = conn.execute("SELECT * FROM svc.sub_ticket WHERE sub_ticket_id = %s FOR UPDATE", (sub_ticket_id,))
        row = cur.fetchone()
        if row is None:
            raise LookupError(sub_ticket_id)
        sub = dict(zip([d.name for d in cur.description], row))
        run = latest_pipeline_run(conn, ticket_id)
        if run is None or run["busy"]:
            raise EditError(MSG_BUSY, 409)
        if sub["status"] == "CLOSED":
            raise EditError(MSG_CLOSED, 409)
        if edit.expected_version is not None and edit.expected_version != sub["version"]:
            raise EditError(MSG_CONFLICT, 409)
        changes = _check(conn, sub, edit)
        values = {k: v["to"] for k, v in changes.items() if k in EDITABLE}
        if "category_code" in values and values["category_code"] != "RETURN":
            values["return_kind"] = None  # schema.sql CHECK(return_kind는 RETURN만)
        sets = ", ".join(f"{k} = %({k})s" for k in values)
        (version,) = conn.execute(
            f"UPDATE svc.sub_ticket SET {sets + ', ' if sets else ''}version = version + 1 "
            "WHERE sub_ticket_id = %(id)s RETURNING version", {**values, "id": sub_ticket_id}).fetchone()
        given = {i["field"]: i.get("value") for i in edit.received_fields}
        for name in changes.get("received_fields", {}).get("to", []):
            conn.execute("""INSERT INTO svc.inquiry_field (sub_ticket_id, field, value_raw, source)
                            VALUES (%s, %s, %s, 'AGENT')""", (sub_ticket_id, name, given.get(name)))
        run_id = start_run(conn, ticket_id, sub_ticket_id, "AGENT_EDIT")
    return {"run_id": run_id, "changes": changes, "version": version,
            "record": {"agent_edit": changes, "by": agent_id, "at": at.isoformat()}}
