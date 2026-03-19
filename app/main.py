import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.admin import router as admin_router
from app.auth import router as auth_router
from app.config import settings
from app.database import async_session, engine
from app.environments import router as environments_router
from app.flags import router as flags_router
from app.logging_config import setup_logging
from app.middleware.error_handler import global_exception_handler
from app.middleware.logging_middleware import RequestLoggingMiddleware
from app.projects import router as projects_router
from app.rules import router as rules_router

setup_logging()

logger = logging.getLogger("switchbox")


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

app.include_router(auth_router.router)
app.include_router(projects_router.router)
app.include_router(environments_router.router)
app.include_router(flags_router.router)
app.include_router(rules_router.router)
app.include_router(admin_router.router)


# --- Health check ---

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
