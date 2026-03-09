from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from app.database import async_session, engine
from app.routers import admin, flags, projects, rules


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(title="Switchbox Backend", lifespan=lifespan)

app.include_router(projects.router)
app.include_router(flags.router)
app.include_router(rules.router)
app.include_router(admin.router)


@app.get("/health")
async def health():
    try:
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        db_status = "unreachable"

    return {
        "status": "ok" if db_status == "connected" else "degraded",
        "version": "0.1.0",
        "database": db_status,
    }
