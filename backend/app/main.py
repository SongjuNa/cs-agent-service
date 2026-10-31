import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI

from app.api import assign, assist, autosend, dashboard, calls, cases, chunks, customers, gold_inputs, me, messages, notes, ref_lists, reference, runs, sub_tickets, tickets
from app.api.deps import open_connection
from app.config import get_settings
from app.db.runs import close_stale_runs
from app.db.store import gloss_reminders
from app.llm.client import default_transport
from app.retrieval.fault import warm_cache
from app.scheduler import start_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    """켜질 때 끝나지 않은 실행을 닫고(FR-036 예외 2행), 켜져 있는 동안 5분 주기 점검을 돌린다(§6-4)."""
    try:
        with open_connection() as conn:
            closed = close_stale_runs(conn, datetime.now(timezone.utc))
        if closed:
            logging.getLogger(__name__).warning("끝나지 않은 실행 %d건을 FAILED로 닫음: %s", len(closed), closed)
    except Exception:  # noqa: BLE001 — 닫기 실패로 서버를 멈추지 않는다
        logging.getLogger(__name__).exception("끝나지 않은 실행 닫기 실패")
    try:  # 고장 사전 증상 벡터 캐시를 메모리에 올린다(FR-018, 조장 결정 2026-10-23). 언어 모델은 부르지 않는다
        logging.getLogger(__name__).info("고장 사전 벡터 %d개를 캐시에서 읽음", warm_cache())
    except Exception:  # noqa: BLE001
        logging.getLogger(__name__).exception("고장 사전 벡터 캐시 읽기 실패")
    scheduler = start_scheduler(gloss_reminders(default_transport)) if get_settings().scheduler_enabled else None
    app.state.scheduler = scheduler
    yield
    if scheduler:
        scheduler.shutdown(wait=False)


app = FastAPI(title="CS Agent Service", lifespan=lifespan)
app.include_router(tickets.router)
app.include_router(messages.router)
app.include_router(chunks.router)
app.include_router(sub_tickets.router)
app.include_router(runs.router)
app.include_router(ref_lists.router)
app.include_router(gold_inputs.router)
app.include_router(me.router)
app.include_router(calls.router)
app.include_router(customers.router)
app.include_router(reference.router)
app.include_router(cases.router)
app.include_router(assist.router)
app.include_router(notes.router)
app.include_router(assign.router)
app.include_router(autosend.router)
app.include_router(dashboard.router)
