"""SLA·상태 재생 채점 (기술 명세서 v1.4 §10-1 3·4, 명세서 v1.5 AC-026-6, AC-025-5).

채점 코드다. 정답지(gold.ticket_gold)의 정답 열을 읽고 scoring 스키마와 eval 표에만 쓴다(CLAUDE.md 규칙 6 예외).
서비스 DB(svc)에는 아무것도 쓰지 않는다(§10-1 2).

문의 한 건을 정답지의 시각으로 재생한다.
1. INTAKE(접수 시각). 정답 상태가 NEW가 아니면 PIPELINE_DONE(접수 시각).
2. 정보 요청을 보냈으면 INFO_REQUEST_SENT(1차 응답 시각).
   - 정답 final_action = CLOSED_NO_RESPONSE면 1차 응답 + 168시간에 NO_REPLY_168H로 닫는다(D22).
   - 정답 상태가 WAITING_CUSTOMER면 그대로 둔다.
   - 그 밖이면 1차 응답 + customer_wait_hours에 CUSTOMER_REPLY.
3. 이관했으면 ESCALATE. 데이터에 이관 시각이 없어 바로 앞 사건 시각에 넣는다(해결 시계를 멈추지 않으므로 SLA 값에는 영향 없음).
4. 해결 시각이 있으면 FINAL_REPLY_SENT(해결 시각). 정답 상태가 CLOSED면 해결 + 168시간에 닫는다(D20).
5. 1차 응답 시각을 넣고 scoring.inquiry_sla(스냅샷)을 정답과 비교한다.

실행: 저장소 루트에서 python -m jobs.replay_gold  (eval.eval_run·eval_case·eval_summary에 기록하고 csv를 쓴다)
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import psycopg
from psycopg import Connection

from app.config import get_settings
from app.db.assignees import name_of
from app.rules.sla import find_sla_target

SNAPSHOT = datetime(2026, 9, 30, 23, 59, tzinfo=timezone.utc)  # 데이터 README "스냅샷"
NO_REPLY = timedelta(hours=168)
ELAPSED_TOLERANCE = Decimal("0.1")  # §10-2 SLA 경과 오차
ITEMS = ("sla_first_response_target_h", "sla_resolution_target_h", "sla_first_response_status",
         "sla_resolution_status", "sla_elapsed_hours")

GOLD_SQL = """
SELECT ticket_id, received_at_utc::timestamptz, channel, language, customer_id, customer_tier, inquiry_body,
       category_code, priority, status, escalated = 'Y', escalation_reason, info_request_sent = 'Y',
       first_response_at_utc::timestamptz, resolved_at_utc::timestamptz, customer_wait_hours::numeric,
       final_action, sla_first_response_target_h::int, sla_resolution_target_h::int,
       sla_first_response_status, sla_resolution_status, sla_elapsed_hours::numeric, assignee_masked
  FROM gold.ticket_gold ORDER BY ticket_id"""


@dataclass
class Gold:
    ticket_id: str
    received: datetime
    channel: str
    language: str
    customer_id: str
    tier: str
    body: str
    category: str
    priority: str
    status: str
    escalated: bool
    escalation_reason: str | None
    info_sent: bool
    first_response: datetime | None
    resolved: datetime | None
    wait_h: Decimal | None
    final_action: str | None
    fr_target: int | None
    res_target: int | None
    fr_status: str | None
    res_status: str | None
    elapsed: Decimal | None
    assignee: str | None = None  # 담당 상담원 ID → 명단 이름(W6, add-agent-roster)


@dataclass
class Result:
    rows: int = 0
    cases: list[dict] = field(default_factory=list)   # eval_case 모양
    events: int = 0                                     # 만든 상태 이력 줄 수(AC-025-5 참고 지표)

    def summary(self) -> dict[str, dict]:
        out = {}
        for item in ITEMS:
            cs = [c for c in self.cases if c["item"] == item]
            scored = [c for c in cs if c["match_yn"] is not None]
            matched = sum(c["match_yn"] for c in scored)
            out[item] = {"n": len(cs), "excluded_n": len(cs) - len(scored), "matched": matched,
                         "accuracy": Decimal(matched) / len(scored) if scored else None}
        return out


def read_gold(conn: Connection) -> list[Gold]:
    return [Gold(*r) for r in conn.execute(GOLD_SQL).fetchall()]


def exclusions(conn: Connection, gold: list[Gold]) -> dict[str, str]:
    """경과 채점 제외(§10-3). eval.exclusion을 읽고, 아직 적재 전이면 D19 정의대로 데이터에서 뽑는다."""
    rows = conn.execute("""SELECT ticket_id, coalesce(reason, item) FROM eval.exclusion
                            WHERE item IN ('sla_elapsed_hours', 'ALL')""").fetchall()
    if rows:
        return dict(rows)
    out = {}
    for g in gold:
        if g.wait_h is not None and g.wait_h < 0:
            out[g.ticket_id] = "D19 대기 시간 음수"
        elif g.status == "NEW" and g.wait_h:
            out[g.ticket_id] = "D19 NEW인데 대기 시간 있음"
    return out


def events_of(g: Gold) -> list[tuple[str, str, datetime]]:
    """정답지 시각으로 쌓을 상태 이력(위 머리말 1~4). 시연 재생(W6, jobs/replay_demo.py)도 같은 순서를 쓴다."""
    events = [("NEW", "INTAKE", g.received)]
    if g.status != "NEW":
        events.append(("IN_PROGRESS", "PIPELINE_DONE", g.received))
    waiting_end = False
    if g.info_sent and g.first_response is not None:
        events.append(("WAITING_CUSTOMER", "INFO_REQUEST_SENT", g.first_response))
        if g.final_action == "CLOSED_NO_RESPONSE":
            events.append(("CLOSED", "NO_REPLY_168H", g.first_response + NO_REPLY))
            waiting_end = True
        elif g.status == "WAITING_CUSTOMER":
            waiting_end = True
        else:
            events.append(("IN_PROGRESS", "CUSTOMER_REPLY", g.first_response + timedelta(hours=float(g.wait_h or 0))))
    if not waiting_end:
        if g.escalated:
            events.append(("ESCALATED", "ESCALATE", events[-1][2]))
        if g.resolved is not None:
            events.append(("RESOLVED", "FINAL_REPLY_SENT", g.resolved))
            if g.status == "CLOSED":
                events.append(("CLOSED", "NO_REPLY_168H_AFTER_RESOLVED", g.resolved + NO_REPLY))
    return events


def _transition(conn: Connection, sub_id: str, to_status: str, event: str, at: datetime,
                reason: str | None = None, final_action: str | None = None) -> None:
    conn.execute("SELECT scoring.transition(%s, %s, %s, %s, 'SYSTEM', %s, %s)",
                 (sub_id, to_status, event, at, reason, final_action))


def replay_one(conn: Connection, g: Gold) -> int:
    """문의 한 건을 재생하고 만든 이력 줄 수를 돌려준다."""
    sub_id = f"{g.ticket_id}-1"
    target = find_sla_target(conn, g.category, g.tier, g.priority)  # §10-1 3 정답 우선순위로 조회
    conn.execute(
        """INSERT INTO scoring.ticket (ticket_id, received_at_utc, channel, language, customer_id, customer_tier,
               inquiry_body, source, source_ticket_id)
           VALUES (%s, %s, %s, %s, %s, %s, %s, 'REPLAY', %s)""",
        (g.ticket_id, g.received, g.channel, g.language, g.customer_id, g.tier, g.body[:2000], g.ticket_id),
    )
    conn.execute(
        """INSERT INTO scoring.sub_ticket (sub_ticket_id, ticket_id, seq, category_code, priority, sla_id,
               sla_first_response_target_h, sla_resolution_target_h, assignee_masked)
           VALUES (%s, %s, 1, %s, %s, %s, %s, %s, %s)""",
        (sub_id, g.ticket_id, g.category, g.priority, target.sla_id, target.sla_first_response_target_h,
         target.sla_resolution_target_h, name_of(g.assignee)),
    )
    events = events_of(g)
    for to_status, event, at in events:
        _transition(conn, sub_id, to_status, event, at,
                    reason=g.escalation_reason or "이관(재생)" if event == "ESCALATE" else None,
                    final_action="CLOSED_NO_RESPONSE" if event == "NO_REPLY_168H" else None)
    conn.execute("UPDATE scoring.sub_ticket SET first_response_at_utc = %s WHERE sub_ticket_id = %s",
                 (g.first_response, sub_id))
    return len(events)


def _clear_scoring(conn: Connection) -> None:
    """scoring 스키마는 실행마다 비우고 다시 채운다(schema.sql scoring 주석)."""
    for table in ("sla_alert", "priority_adjustment", "ticket_status_history", "inquiry_field", "message_gloss",
                  "agent_step", "agent_run", "ticket_message", "sub_ticket", "ticket"):
        conn.execute(f"DELETE FROM scoring.{table}")


def replay(conn: Connection) -> Result:
    """scoring에 4,000건을 재생하고 정답과 비교한다. 호출하는 쪽의 트랜잭션 안에서 돈다."""
    _clear_scoring(conn)
    gold = read_gold(conn)
    excluded = exclusions(conn, gold)
    result = Result(rows=len(gold))
    for g in gold:
        result.events += replay_one(conn, g)
    sla = {r[0]: r[1:] for r in conn.execute(
        """SELECT sub_ticket_id, fr_target_h, res_target_h, fr_status, res_status, res_elapsed_h
             FROM scoring.inquiry_sla(%s)""", (SNAPSHOT,)).fetchall()}
    for g in gold:
        fr_t, res_t, fr_s, res_s, el = sla[f"{g.ticket_id}-1"]
        actual = {"sla_first_response_target_h": fr_t, "sla_resolution_target_h": res_t,
                  "sla_first_response_status": fr_s, "sla_resolution_status": res_s, "sla_elapsed_hours": el}
        expected = {"sla_first_response_target_h": g.fr_target, "sla_resolution_target_h": g.res_target,
                    "sla_first_response_status": g.fr_status, "sla_resolution_status": g.res_status,
                    "sla_elapsed_hours": g.elapsed}
        for item in ITEMS:
            exp, act = expected[item], actual[item]
            reason = None
            if item == "sla_elapsed_hours":
                reason = excluded.get(g.ticket_id)
                match = None if reason else (exp is not None and act is not None
                                             and abs(Decimal(exp) - Decimal(act)) <= ELAPSED_TOLERANCE)
            else:
                match = exp == act
            result.cases.append({"source_ticket_id": g.ticket_id, "sub_ticket_id": f"{g.ticket_id}-1", "item": item,
                                 "expected_value": None if exp is None else str(exp),
                                 "actual_value": None if act is None else str(act),
                                 "match_yn": match, "excluded_reason": reason})
    return result


def record(conn: Connection, result: Result, out_dir: Path) -> tuple[int, Path]:
    """eval_run·eval_case·eval_summary와 csv로 남긴다(§10-1 4)."""
    with conn.transaction():
        (run_id,) = conn.execute(
            """INSERT INTO eval.eval_run (input_source, ticket_count, note)
               VALUES ('ALL_4000', %s, %s) RETURNING eval_run_id""",
            (result.rows, f"SLA 재생 채점(§10-1 3), 상태 이력 {result.events}줄 생성"),
        ).fetchone()
        with conn.cursor().copy(
            """COPY eval.eval_case (eval_run_id, source_ticket_id, sub_ticket_id, item, expected_value, actual_value,
                   match_yn, excluded_reason) FROM STDIN""") as copy:
            for c in result.cases:
                copy.write_row((run_id, c["source_ticket_id"], c["sub_ticket_id"], c["item"], c["expected_value"],
                                c["actual_value"], c["match_yn"], c["excluded_reason"]))
        for item, s in result.summary().items():
            threshold = Decimal(1)
            conn.execute(
                """INSERT INTO eval.eval_summary (eval_run_id, item, n, excluded_n, matched, accuracy, threshold, passed)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s)""",
                (run_id, item, s["n"], s["excluded_n"], s["matched"], s["accuracy"], threshold,
                 s["accuracy"] is not None and s["accuracy"] >= threshold),
            )
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"scoring_ALL_4000_{date.today():%Y%m%d}.csv"
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(result.cases[0]))
        writer.writeheader()
        writer.writerows(result.cases)
    return run_id, path


def main() -> None:
    settings = get_settings()
    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        with conn.transaction():
            result = replay(conn)
        run_id, path = record(conn, result, Path("scoring"))
    for item, s in result.summary().items():
        print(f"{item}: {s['matched']}/{s['n'] - s['excluded_n']} (제외 {s['excluded_n']})")
    print(f"eval_run {run_id}, {path}")


if __name__ == "__main__":
    main()
