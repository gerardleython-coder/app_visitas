import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.presentation.audit import router as audit_router
from app.presentation.auth import router as auth_router
from app.presentation.brothers import router as brothers_router
from app.presentation.operators import router as operators_router
from app.presentation.visits import router as visits_router
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
app.include_router(auth_router, prefix="/api/v1")
app.include_router(audit_router, prefix="/api/v1")
app.include_router(brothers_router, prefix="/api/v1")
app.include_router(operators_router, prefix="/api/v1")
app.include_router(visits_router, prefix="/api/v1")


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}