"""W3 정답지 적재: tickets.csv → gold.ticket_gold, resolution_cases.csv → gold.resolution_case_gold.

원본 열 이름 그대로, 모든 값을 문자열로 넣는다(테이블 정의서 v1.3 §3). 빈 칸은 NULL.
표를 비우고 다시 넣으며, 전체가 트랜잭션 하나다.

실행: 저장소 루트에서 python -m jobs.load_gold
"""

import csv
from pathlib import Path

import psycopg

from app.config import get_settings

FILES = {
    "ticket_gold": "tickets.csv",
    "resolution_case_gold": "resolution_cases.csv",
}


def read_csv(path: Path) -> tuple[list[str], list[list[str | None]]]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
        return header, [[v if v != "" else None for v in row] for row in reader]


def table_columns(conn: psycopg.Connection, table: str) -> list[str]:
    return [
        r[0]
        for r in conn.execute(
            "SELECT column_name FROM information_schema.columns"
            " WHERE table_schema = 'gold' AND table_name = %s ORDER BY ordinal_position",
            (table,),
        )
    ]


def load(database_url: str, data_dir: Path) -> dict[str, int]:
    counts = {}
    with psycopg.connect(database_url) as conn:
        try:
            # TRUNCATE는 eval.gold_set이 가리키기만 해도 거부되므로 DELETE로 비운다(load_reference와 같은 이유)
            for table in FILES:
                conn.execute(f"DELETE FROM gold.{table}")
        except psycopg.errors.ForeignKeyViolation as e:
            raise SystemExit(
                "정답지를 다른 표(eval.gold_set 등)가 가리키고 있어 비울 수 없습니다. 아무것도 바꾸지 않았습니다.\n"
                f"{e}"
            ) from e
        for table, filename in FILES.items():
            header, rows = read_csv(data_dir / filename)
            if set(header) != set(table_columns(conn, table)):
                raise SystemExit(f"{filename}의 머리글이 gold.{table}의 열과 다릅니다. 아무것도 바꾸지 않았습니다.")
            columns = ", ".join(header)
            with conn.cursor().copy(f"COPY gold.{table} ({columns}) FROM STDIN") as copy:
                for row in rows:
                    copy.write_row(row)
            counts[table] = len(rows)
    return counts


def main() -> None:
    settings = get_settings()
    for table, n in load(settings.database_url, settings.data_path).items():
        print(f"gold.{table}: {n}")


if __name__ == "__main__":
    main()
