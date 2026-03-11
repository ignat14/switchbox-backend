import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
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


# --- Contact (inline, small endpoint) ---

class ContactRequest(BaseModel):
    email: EmailStr
    message: str = ""


contact_router = APIRouter(tags=["contact"])


@contact_router.post("/contact", status_code=204)
async def submit_contact(body: ContactRequest):
    if not settings.DISCORD_WEBHOOK_URL:
        logger.error("DISCORD_WEBHOOK_URL is not configured")
        raise HTTPException(status_code=503, detail="Contact form is not available right now.")

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    embed = {
        "title": "New early access request",
        "color": 0x8B5CF6,  # violet-500
        "fields": [
            {"name": "Email", "value": body.email, "inline": True},
            {"name": "Date", "value": timestamp, "inline": True},
        ],
    }

    if body.message.strip():
        embed["fields"].append({"name": "Message", "value": body.message})

    payload = {"embeds": [embed]}

    async with httpx.AsyncClient() as client:
        resp = await client.post(settings.DISCORD_WEBHOOK_URL, json=payload, timeout=10)

    if resp.status_code not in (200, 204):
        logger.error("Discord webhook failed: %s %s", resp.status_code, resp.text)
        raise HTTPException(status_code=502, detail="Failed to send message.")


app.include_router(contact_router)


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
