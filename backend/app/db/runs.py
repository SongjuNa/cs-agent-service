"""실행 기록 열기·닫기·지우기·조회 (명세서 v1.5 FR-036 처리 1·5·7, 예외 2·3행, 기술 명세서 v1.4 §6-5, §8-1).

이 모듈은 언어 모델 호출 계층을 import하지 않는다(주기 점검이 부른다).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from psycopg import Connection

RETENTION_DAYS = 90  # §6-5 "agent_run·agent_step 90일(제안)", 에이전트 설계서 7-2
MSG_INTERRUPTED = "UNKNOWN: 처리 중단(서버 재시작)"  # FR-036 예외 2행, C-82


def pipeline_run(alias: str = "r") -> str:
    """처리 흐름 전체를 도는 실행인지 가리는 SQL 조건(접수·고객 회신·다시 처리).

    RETRY는 대역 다시 만들기·[다시 검증]에도 쓰이므로(§6-5) 처리 흐름 단계(T2·Q1·Q2)를 남긴 RETRY만 넣는다(C-87).
    """
    return (f"({alias}.trigger IN ('INTAKE','CUSTOMER_REPLY') OR ({alias}.trigger = 'RETRY' AND EXISTS "
            f"(SELECT 1 FROM svc.agent_step ps WHERE ps.run_id = {alias}.run_id AND ps.step_name IN ('T2','Q1','Q2'))))")


def _rows(conn: Connection, sql: str, params: tuple) -> list[dict[str, Any]]:
    cur = conn.execute(sql, params)
    names = [d.name for d in cur.description]
    return [dict(zip(names, r)) for r in cur.fetchall()]


def close_stale_runs(conn: Connection, now: datetime) -> list[int]:
    """끝나지 않은 실행(status 비어 있음)을 FAILED로 닫는다. 서버가 켜질 때 한 번(§6-5).

    단계 행은 실행 끝에 한 번에 쓰므로 반쯤 쓴 단계는 없다. 오류 종류는 그 문의의 pipeline_error에 남긴다(C-82).
    """
    with conn.transaction():
        closed = conn.execute(
            """UPDATE svc.agent_run SET status = 'FAILED', finished_at_utc = %s
                WHERE status IS NULL RETURNING run_id, ticket_id, sub_ticket_id""", (now,)).fetchall()
        for run_id, ticket_id, sub_ticket_id in closed:
            (latest,) = conn.execute(
                f"SELECT max(r.run_id) FROM svc.agent_run r WHERE r.ticket_id = %s AND (r.run_id = %s OR {pipeline_run()})",
                (ticket_id, run_id)).fetchone()
            if latest == run_id:  # 그 뒤에 끝난 처리가 있으면 그 결과를 그대로 둔다
                conn.execute(
                    """UPDATE svc.sub_ticket SET pipeline_error = %s
                        WHERE ticket_id = %s AND (%s::text IS NULL OR sub_ticket_id = %s)""",
                    (MSG_INTERRUPTED, ticket_id, sub_ticket_id, sub_ticket_id))
    return [r[0] for r in closed]


def purge_runs(conn: Connection, as_of: datetime, days: int = RETENTION_DAYS) -> list[int]:
    """보존 기간이 지난 실행을 지운다(단계는 함께 지워진다). 메시지 이력은 지우지 않는다(FR-036 예외 3행).

    eval.self_check·eval.agent_feedback이 가리키는 실행은 외래 키에 삭제 연쇄가 없어 남긴다(C-83).
    """
    with conn.transaction():
        rows = conn.execute(
            """DELETE FROM svc.agent_run r
                WHERE r.finished_at_utc < %s
                  AND NOT EXISTS (SELECT 1 FROM eval.self_check c WHERE c.run_id = r.run_id)
                  AND NOT EXISTS (SELECT 1 FROM eval.agent_feedback f WHERE f.run_id = r.run_id)
                RETURNING r.run_id""", (as_of - timedelta(days=days),)).fetchall()
    return [r[0] for r in rows]


_RUN_COLS = """r.run_id, r.ticket_id, r.sub_ticket_id, r.trigger, r.started_at_utc, r.finished_at_utc,
               (extract(epoch FROM r.finished_at_utc - r.started_at_utc) * 1000)::bigint AS duration_ms,
               r.status, r.last_step, r.llm_model"""


def ticket_runs(conn: Connection, ticket_id: str) -> list[dict[str, Any]] | None:
    """티켓의 실행 목록(오래된 것부터). 티켓이 없으면 None. current = 같은 하위 문의의 마지막 처리 흐름 실행(처리 5)."""
    if conn.execute("SELECT 1 FROM svc.ticket WHERE ticket_id = %s", (ticket_id,)).fetchone() is None:
        return None
    runs = _rows(conn, f"""
        SELECT {_RUN_COLS},
               {pipeline_run()} AS pipeline, count(s.step_id) AS step_count,
               count(s.step_id) FILTER (WHERE s.result = 'FAILED') AS failed_steps, sum(s.llm_calls) AS llm_calls,
               sum(s.input_tokens) AS input_tokens, sum(s.output_tokens) AS output_tokens
          FROM svc.agent_run r LEFT JOIN svc.agent_step s ON s.run_id = r.run_id
         WHERE r.ticket_id = %s
         GROUP BY r.run_id ORDER BY r.run_id""", (ticket_id,))
    latest: dict[str | None, int] = {}
    for r in runs:
        if r["pipeline"]:
            latest[r["sub_ticket_id"]] = r["run_id"]
    for r in runs:
        r["current"] = latest.get(r["sub_ticket_id"]) == r["run_id"]
    return runs


def run_steps(conn: Connection, run_id: int) -> dict[str, Any] | None:
    """실행 한 줄과 단계 목록(step_order 순). 실행이 없으면 None."""
    run = _rows(conn, f"SELECT {_RUN_COLS} FROM svc.agent_run r WHERE r.run_id = %s", (run_id,))
    if not run:
        return None
    steps = _rows(conn, """
        SELECT step_id, step_name, step_order, started_at_utc, finished_at_utc, latency_ms, result, error_kind, error,
               prompt_version, input_tokens, output_tokens, llm_calls, input_json, output_json
          FROM svc.agent_step WHERE run_id = %s ORDER BY step_order""", (run_id,))
    return {"run": run[0], "steps": steps}
