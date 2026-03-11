from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.database import async_session, engine
from app.logging_config import setup_logging
from app.middleware.error_handler import global_exception_handler
from app.middleware.logging_middleware import RequestLoggingMiddleware
from app.config import settings
from app.routers import admin, auth, contact, flags, projects, rules

setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(
    title="Switchbox Backend",
    lifespan=lifespan,
    openapi_url=None if settings.ENVIRONMENT == "production" else "/openapi.json",
    docs_url=None if settings.ENVIRONMENT == "production" else "/docs",
    redoc_url=None if settings.ENVIRONMENT == "production" else "/redoc",
)

app.add_exception_handler(Exception, global_exception_handler)

app.add_middleware(RequestLoggingMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://switchbox-ui.pages.dev",
        "http://localhost:5173",
        "https://switchbox.dev",
        "https://www.switchbox.dev",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(flags.router)
app.include_router(rules.router)
app.include_router(admin.router)
app.include_router(contact.router)


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
