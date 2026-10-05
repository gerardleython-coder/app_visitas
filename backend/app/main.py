import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.presentation.audit import router as audit_router
from app.presentation.administrators import router as administrators_router
from app.presentation.auth import router as auth_router
from app.presentation.brothers import router as brothers_router
from app.presentation.operators import router as operators_router
from app.presentation.ranking import router as ranking_router
from app.presentation.visits import router as visits_router
from app.presentation.territories import router as territories_router
from app.infrastructure.database import DatabaseSettings
from app.infrastructure.email_service import SMTPEmailSender, SMTPSettings
from app.infrastructure.visit_notification_dispatcher import VisitNotificationDispatcher
from app.infrastructure.visit_notification_worker import VisitNotificationWorker


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    stop_event = asyncio.Event()
    dispatcher = VisitNotificationDispatcher(
        database_url=DatabaseSettings().database_url,
        sender=SMTPEmailSender(SMTPSettings()),
    )
    worker = VisitNotificationWorker(dispatcher)
    task = asyncio.create_task(worker.run(stop_event))
    try:
        yield
    finally:
        stop_event.set()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


app = FastAPI(title="App Visitas API", version="0.1.0", lifespan=lifespan)
cors_origins = [
    origin.strip()
    for origin in os.environ.get(
        "CORS_ORIGINS",
        "http://localhost:5000,http://127.0.0.1:5000",
    ).split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)
app.include_router(auth_router, prefix="/api/v1")
app.include_router(administrators_router, prefix="/api/v1")
app.include_router(audit_router, prefix="/api/v1")
app.include_router(brothers_router, prefix="/api/v1")
app.include_router(operators_router, prefix="/api/v1")
app.include_router(territories_router, prefix="/api/v1")
app.include_router(ranking_router, prefix="/api/v1")
app.include_router(visits_router, prefix="/api/v1")


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}