from fastapi import FastAPI

from app.presentation.auth import router as auth_router
from app.presentation.brothers import router as brothers_router
from app.presentation.operators import router as operators_router
from app.presentation.visits import router as visits_router

app = FastAPI(title="App Visitas API", version="0.1.0")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(brothers_router, prefix="/api/v1")
app.include_router(operators_router, prefix="/api/v1")
app.include_router(visits_router, prefix="/api/v1")


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}