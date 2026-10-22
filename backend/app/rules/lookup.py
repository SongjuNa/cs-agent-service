"""고객·제품 조회 (FR-010, 기술 명세서 §2-2 Q2)."""

import logging
from dataclasses import dataclass, field

from psycopg import Connection

log = logging.getLogger(__name__)


class CustomerNotFound(Exception):
    """고객 기준정보가 없다. 흐름을 멈춘다(FR-010 예외)."""


@dataclass(frozen=True)
class CustomerInfo:
    customer_id: str
    customer_tier: str
    customer_segment: str
    country: str
    primary_contact_name: str | None
    primary_contact_email: str | None
    primary_contact_phone: str | None


@dataclass(frozen=True)
class ProductInfo:
    """제품 값 묶음. 티켓에 저장하지 않고 돌려주기만 한다(FR-010 처리 2)."""

    product_code: str | None = None
    product_name: str | None = None
    product_family: str | None = None
    family_name: str | None = None
    tech_support_dept: str | None = None
    has_firmware: bool | None = None
    fw_latest: str | None = None
    std_lead_time_weeks: int | None = None
    list_price_usd: int | None = None
    moq: int | None = None
    warranty_months: int | None = None
    doc_ids: list[str] = field(default_factory=list)
    lifecycle_status: str | None = None
    flags: list[str] = field(default_factory=list)


def lookup_customer(conn: Connection, customer_id: str) -> CustomerInfo:
    row = conn.execute(
        """SELECT tier, segment, country, primary_contact_name, primary_contact_email, primary_contact_phone
             FROM ref.customer WHERE customer_id = %s""",
        (customer_id,),
    ).fetchone()
    if row is None:
        log.warning("고객 기준정보 없음: customer_id=%s", customer_id)
        raise CustomerNotFound(f"고객 기준정보를 읽을 수 없음. 데이터 적재 확인 ({customer_id})")
    return CustomerInfo(customer_id, *row)


def lookup_product(conn: Connection, product_code: str | None) -> ProductInfo:
    if not product_code:
        return ProductInfo(flags=["제품 미확정"])
    row = conn.execute(
        """SELECT p.product_name, p.family, f.family_name, f.tech_support_dept, p.has_firmware,
                  p.std_lead_time_weeks, p.list_price_usd, p.moq, p.warranty_months, p.lifecycle_status
             FROM ref.product p JOIN ref.product_family f USING (family)
            WHERE p.product_code = %s""",
        (product_code,),
    ).fetchone()
    if row is None:
        return ProductInfo(flags=["제품 미확정"])
    (name, family, family_name, dept, has_fw, lead, price, moq, warranty, lifecycle) = row
    fw_latest = conn.execute(
        "SELECT fw_version FROM ref.firmware_release WHERE product_code = %s AND is_latest",
        (product_code,),
    ).fetchone()
    doc_ids = [r[0] for r in conn.execute(
        "SELECT doc_id FROM ref.document WHERE product_code = %s ORDER BY doc_id", (product_code,)
    )]
    return ProductInfo(
        product_code=product_code, product_name=name, product_family=family, family_name=family_name,
        tech_support_dept=dept, has_firmware=has_fw, fw_latest=fw_latest[0] if fw_latest else None,
        std_lead_time_weeks=lead, list_price_usd=price, moq=moq, warranty_months=warranty,
        doc_ids=doc_ids, lifecycle_status=lifecycle,
    )
