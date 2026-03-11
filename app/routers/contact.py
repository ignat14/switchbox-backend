import logging
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr

from app.config import settings

logger = logging.getLogger("switchbox")

router = APIRouter(tags=["contact"])


class ContactRequest(BaseModel):
    email: EmailStr
    message: str = ""


@router.post("/contact", status_code=204)
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
