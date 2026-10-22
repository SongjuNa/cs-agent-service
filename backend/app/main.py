from fastapi import FastAPI

from app.api import chunks, messages, tickets

app = FastAPI(title="CS Agent Service")
app.include_router(tickets.router)
app.include_router(messages.router)
app.include_router(chunks.router)
