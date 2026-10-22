"""정답지 문의를 접수 API로 넣는다 (프로젝트 구조 1순위 판 2장 jobs/run_tickets.py, 화면 정의서 v2 0-2절).

gold.v_inputs의 입력 열만 읽는다(CLAUDE.md 규칙 6). 출처는 LOAD, 원본 번호는 source_ticket_id에 남긴다.
새 번호와 화면 주소를 출력한다.

실행: 저장소 루트에서 python -m jobs.run_tickets CSV1-000017 CSV1-000004
      (API 주소 기본값 http://localhost:8000, 화면 주소 기본값 http://localhost:5173)
"""

import argparse
import sys
from typing import Any

import httpx
import psycopg

from app.config import get_settings


def read_inputs(conn: psycopg.Connection, ticket_ids: list[str]) -> list[dict[str, Any]]:
    cur = conn.execute("SELECT * FROM gold.v_inputs WHERE ticket_id = ANY(%s) ORDER BY ticket_id", (ticket_ids,))
    names = [d.name for d in cur.description]
    return [dict(zip(names, row)) for row in cur.fetchall()]


def payload(row: dict[str, Any]) -> dict[str, Any]:
    """v_inputs 한 행 → POST /tickets 입력."""
    received = row["received_at_utc"]
    return {
        "channel": row["channel"],
        "customer_id": row["customer_id"],
        "product_code": row["product_code"],
        "language": row["language"],
        "inquiry_body": row["inquiry_body"],
        "received_at_utc": received.isoformat() if received else None,
        "source": "LOAD",
        "source_ticket_id": row["ticket_id"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="정답지 문의를 POST /tickets로 넣는다")
    parser.add_argument("ticket_ids", nargs="+", help="정답지 ticket_id (예: CSV1-000017)")
    parser.add_argument("--api", default="http://localhost:8000")
    parser.add_argument("--web", default="http://localhost:5173")
    args = parser.parse_args(argv)

    with psycopg.connect(get_settings().database_url) as conn:
        rows = read_inputs(conn, args.ticket_ids)
    missing = sorted(set(args.ticket_ids) - {r["ticket_id"] for r in rows})
    for ticket_id in missing:
        print(f"{ticket_id}: 정답지에 없음", file=sys.stderr)
    failed = bool(missing)
    with httpx.Client(base_url=args.api, timeout=30) as client:
        for row in rows:
            res = client.post("/tickets", json=payload(row))
            if res.status_code != 201:
                print(f"{row['ticket_id']}: 접수 실패 {res.status_code} {res.text}", file=sys.stderr)
                failed = True
                continue
            new_id = res.json()["ticket_id"]
            print(f"{row['ticket_id']} → {new_id}  {args.web}/tickets/{new_id}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
