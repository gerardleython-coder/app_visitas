from fastapi import FastAPI

from app.presentation.auth import router as auth_router

app = FastAPI(title="App Visitas API", version="0.1.0")
app.include_router(auth_router, prefix="/api/v1")


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok"}