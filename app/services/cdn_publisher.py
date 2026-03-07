import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

import boto3
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.flag import Flag

logger = logging.getLogger(__name__)

LOCAL_OUTPUT_DIR = Path("cdn_output")


def _get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        region_name="auto",
    )


def _upload_json(key: str, body: str) -> None:
    client = _get_s3_client()
    client.put_object(
        Bucket=settings.R2_BUCKET_NAME,
        Key=key,
        Body=body.encode(),
        ContentType="application/json",
        CacheControl="public, max-age=30",
    )


async def publish_flags(db: AsyncSession, project_id: UUID, environment: str) -> None:
    try:
        result = await db.execute(
            select(Flag)
            .where(Flag.project_id == project_id, Flag.environment == environment)
        )
        flags = result.scalars().all()

        config = {
            "version": datetime.now(timezone.utc).isoformat(),
            "flags": {},
        }
        for flag in flags:
            config["flags"][flag.key] = {
                "enabled": flag.enabled,
                "rollout_pct": flag.rollout_pct,
                "flag_type": flag.flag_type,
                "default_value": flag.default_value,
                "rules": [
                    {
                        "attribute": rule.attribute,
                        "operator": rule.operator,
                        "value": rule.value,
                    }
                    for rule in flag.rules
                ],
            }

        payload = json.dumps(config, indent=2)
        object_key = f"{project_id}/{environment}/flags.json"

        if settings.R2_ACCOUNT_ID:
            await asyncio.to_thread(_upload_json, object_key, payload)
            logger.info("Published to R2: %s", object_key)
        else:
            out = LOCAL_OUTPUT_DIR / object_key
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(payload)
            logger.info("Published locally: %s", out)
    except Exception:
        logger.exception("CDN publish failed for %s/%s", project_id, environment)
