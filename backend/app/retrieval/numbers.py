"""숫자 표 조회 (FR-017, 기술 명세서 v1.4 §5-5). 처리 흐름의 Q9. 언어 모델을 쓰지 않는다.

가격·납기·MOQ·합계, 사양값, 접수 시점 최신 펌웨어, 보증 기간을 표에서 읽고 출처를 붙인다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

from psycopg import Connection

from app.pipeline.state import DocCandidate, LookupValue

PRODUCT_SOURCE = "product_master.csv"
SPEC_SOURCE = "product_spec_facts.csv"
FW_SOURCE = "firmware_history.csv"

VERDICT_UPDATE = "업데이트 안내"
VERDICT_LATEST = "이미 최신"

FLAG_NO_PRODUCT = "제품 확인 필요"
FLAG_NO_FIRMWARE = "펌웨어 없는 제품 — 분류 재검토"
FLAG_NO_RELEASE = "접수 시점 최신 없음"
FLAG_PICK_SPEC = "사양 항목 선택 필요"
FLAG_EARLY_DATE = "요청 납기 < 표준 납기"
FLAG_NOT_IN_TABLE = "표에 없음"  # 기술 명세서 §2-2 Q9 실패


@dataclass
class FirmwareCheck:
    fw_latest_at_intake: str | None
    release_date: date | None
    customer_fw: str | None
    verdict: str | None  # 업데이트 안내 / 이미 최신 / None(고객 버전 없음)


@dataclass
class NumbersResult:
    lookups: list[LookupValue] = field(default_factory=list)
    firmware: FirmwareCheck | None = None
    flags: list[str] = field(default_factory=list)


def version_key(version: str) -> tuple[int, ...]:
    """점으로 나눈 숫자 묶음으로 비교한다("3.10" > "3.9", §5-5)."""
    return tuple(int(part) for part in version.split("."))


def _as_date(value: date | datetime | str | None) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()


def firmware_at_intake(conn: Connection, product_code: str, received_at) -> tuple[str, date] | None:
    """접수 시점 최신 펌웨어 (§5-5 SQL, 팀 정리 §3 원칙 4)."""
    rows = conn.execute(
        "SELECT fw_version, release_date FROM ref.firmware_release WHERE product_code = %s AND release_date <= %s",
        (product_code, _as_date(received_at)),
    ).fetchall()
    if not rows:
        return None
    return max(rows, key=lambda r: (r[1], version_key(r[0])))


def lookup_numbers(
    conn: Connection,
    category_code: str | None,
    product_code: str | None,
    received_at=None,
    quantity: str | None = None,
    current_fw: str | None = None,
    doc_candidates: list[DocCandidate] | None = None,
    required_date: str | None = None,
) -> NumbersResult:
    result = NumbersResult()
    if not product_code:
        result.flags.append(FLAG_NO_PRODUCT)
        return result
    row = conn.execute(
        "SELECT list_price_usd, std_lead_time_weeks, moq, warranty_months, has_firmware FROM ref.product WHERE product_code = %s",
        (product_code,),
    ).fetchone()
    if row is None:
        result.flags.append(FLAG_NO_PRODUCT)
        return result
    price, lead_weeks, moq, warranty, has_firmware = row
    candidates = doc_candidates or []

    def add(item, value, unit, table, key):
        result.lookups.append(LookupValue(item=item, value=value, unit=unit, source_table=table, source_key=key))

    if category_code in ("QUOTE", "ORDER_LEAD"):
        add("list_price_usd", price, "USD", PRODUCT_SOURCE, product_code)
        add("std_lead_time_weeks", lead_weeks, "weeks", PRODUCT_SOURCE, product_code)
        add("moq", moq, "units", PRODUCT_SOURCE, product_code)
        if quantity and str(quantity).isdigit():
            add("line_total_usd", price * int(quantity), "USD", PRODUCT_SOURCE, product_code)
        need_by, received = _as_date(required_date), _as_date(received_at)
        if need_by and received and need_by < received + timedelta(weeks=lead_weeks):
            result.flags.append(FLAG_EARLY_DATE)

    elif category_code in ("TECH_SPEC", "COMPLIANCE"):
        specs = conn.execute(
            "SELECT attribute, value, doc_id, section FROM ref.product_spec WHERE product_code = %s ORDER BY attribute",
            (product_code,),
        ).fetchall()
        sections = {(c.doc_id, c.section_no) for c in candidates}
        picked = [s for s in specs if (s[2], s[3]) in sections]
        if not specs:
            result.flags.append(FLAG_NOT_IN_TABLE)
        elif not picked:
            picked = specs
            result.flags.append(FLAG_PICK_SPEC)
        for attribute, value, _, _ in picked:
            add(attribute, value, None, SPEC_SOURCE, f"{product_code}/{attribute}")

    elif category_code == "FW_UPDATE" or (
        category_code == "MANUAL" and any(c.doc_id.startswith("RN-") for c in candidates)
    ):
        if not has_firmware:
            if category_code == "FW_UPDATE":
                result.flags.append(FLAG_NO_FIRMWARE)
            return result
        latest = firmware_at_intake(conn, product_code, received_at)
        if latest is None:
            result.flags.append(FLAG_NO_RELEASE)
            result.firmware = FirmwareCheck(None, None, current_fw, None)
            return result
        version, released = latest
        verdict = None
        if current_fw:
            try:
                verdict = VERDICT_LATEST if version_key(current_fw) >= version_key(version) else VERDICT_UPDATE
            except ValueError:
                verdict = None
        result.firmware = FirmwareCheck(version, released, current_fw, verdict)
        add("fw_latest_at_intake", version, None, FW_SOURCE, f"{product_code}/{version}")
        if verdict:
            add("fw_verdict", verdict, None, FW_SOURCE, f"{product_code}/{version}")

    elif category_code == "WARRANTY":
        add("warranty_months", warranty, "months", PRODUCT_SOURCE, product_code)

    return result
