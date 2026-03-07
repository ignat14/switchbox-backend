from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from app.database import async_session, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    yield
    await engine.dispose()


app = FastAPI(title="TinyFlags Backend", lifespan=lifespan)


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
