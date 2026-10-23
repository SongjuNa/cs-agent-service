from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import chunks, messages, tickets
from app.config import get_settings
from app.scheduler import start_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    """서버가 켜져 있는 동안 5분 주기 점검을 돌린다(기술 명세서 §6-4)."""
    scheduler = start_scheduler() if get_settings().scheduler_enabled else None
    app.state.scheduler = scheduler
    yield
    if scheduler:
        scheduler.shutdown(wait=False)


app = FastAPI(title="CS Agent Service", lifespan=lifespan)
app.include_router(tickets.router)
app.include_router(messages.router)
app.include_router(chunks.router)
