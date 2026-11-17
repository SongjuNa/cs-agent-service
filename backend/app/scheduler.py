"""주기 점검 (기술 명세서 v1.4 §6-4 "주기 점검(스케줄러, 5분, T30)", 명세서 v1.5 FR-027 처리 1·4).

한 주기에 차례로: 1 SLA 경고(FR-027)와 해제, 2 회신 리마인드(FR-023)와 대역(L7), 3 무응답 종료(D22),
4 해결 뒤 종료(D20). 단계마다 따로 돌리고, 오류는 서버 로그에 남겨 다음 주기에 다시 한다.
따로 하루 한 번 보존 기간(90일)이 지난 실행 기록을 지운다(FR-036 예외 3행, §6-5).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import psycopg
from apscheduler.schedulers.background import BackgroundScheduler
from psycopg import Connection

from app.config import get_settings
from collections.abc import Callable
from app.db.runs import purge_runs
from app.sla.alerts import clear_alerts, raise_alerts
from app.status.closing import close_due
from app.status.reminder import send_reminders

log = logging.getLogger(__name__)

INTERVAL_MINUTES = 5  # §6-4, FR-027 처리 1 "제안 5분"
JOB_ID = "periodic_check"
PURGE_JOB_ID = "purge_runs"
MAIL_JOB_ID = "mail_poll"


Gloss = Callable[[Connection, list[dict]], list[int]]  # 리마인드 대역(L7). 이 모듈은 언어 모델 계층을 import하지 않는다


def periodic_check(conn: Connection, as_of: datetime, gloss: Gloss | None = None) -> dict[str, int | str]:
    """한 주기. 단계별 처리 건수(실패한 단계는 "오류")를 돌려준다. gloss가 있으면 새 리마인드에 대역을 붙인다."""
    sent: list[dict] = []

    def reminders() -> list[dict]:
        sent.extend(send_reminders(conn, as_of))
        return sent

    steps = [
        ("alerts", lambda: raise_alerts(conn, as_of)),
        ("cleared", lambda: clear_alerts(conn, as_of)),
        ("reminders", reminders),
        ("glossed", lambda: gloss(conn, sent) if gloss else []),
        ("closed", lambda: close_due(conn, as_of)),
    ]
    result: dict[str, int | str] = {}
    for name, run in steps:
        try:
            with conn.transaction():
                result[name] = len(run())
        except Exception:  # FR-027 예외 3행: 기록하고 다음 주기에 다시
            log.exception("주기 점검 %s 실패 (as_of %s)", name, as_of)
            result[name] = "오류"
    return result


def _tick(gloss: Gloss | None) -> None:
    with psycopg.connect(get_settings().database_url, autocommit=True) as conn:
        result = periodic_check(conn, datetime.now(timezone.utc), gloss)
    log.info("주기 점검 %s", result)


def _purge() -> None:
    try:
        with psycopg.connect(get_settings().database_url, autocommit=True) as conn:
            removed = purge_runs(conn, datetime.now(timezone.utc))
        log.info("실행 기록 보존: %d건 지움", len(removed))
    except Exception:  # 다음 날 다시 한다
        log.exception("실행 기록 보존 작업 실패")


def _mail(poll: Callable[[], dict]) -> None:
    try:
        result = poll()
        if result["accepted"]:
            log.info("부서 회신 메일 %d건 연결", len(result["accepted"]))
    except Exception:  # 메일 서버가 잠깐 꺼져 있어도 다음 주기에 다시
        log.exception("받은 메일함 확인 실패")


def start_scheduler(gloss: Gloss | None = None, mail_poll: Callable[[], dict] | None = None,
                    mail_seconds: int = 30) -> BackgroundScheduler:
    """mail_poll이 있으면 받은 메일함 확인을 mail_seconds마다 따로 돌린다(변경 add-escalation-mail-live)."""
    scheduler = BackgroundScheduler(timezone="UTC")
    if mail_poll:
        scheduler.add_job(_mail, "interval", args=[mail_poll], seconds=mail_seconds, id=MAIL_JOB_ID, max_instances=1,
                          coalesce=True)
    scheduler.add_job(_tick, "interval", args=[gloss], minutes=INTERVAL_MINUTES, id=JOB_ID, max_instances=1, coalesce=True)
    # 켜자마자 한 번, 그 뒤 하루마다(하루 안에 다시 켜도 빠지지 않게)
    scheduler.add_job(_purge, "interval", days=1, id=PURGE_JOB_ID, max_instances=1, coalesce=True,
                      next_run_time=datetime.now(timezone.utc))
    scheduler.start()
    return scheduler
