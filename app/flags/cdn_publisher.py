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
from app.flags.models import Flag, FlagEnvironment

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


def _write_to_path(object_key: str, payload: str) -> None:
    """Write payload to a single CDN path (R2 or local)."""
    if settings.R2_ACCOUNT_ID:
        _upload_json(object_key, payload)
        logger.info("Published to R2: %s", object_key)
    else:
        out = LOCAL_OUTPUT_DIR / object_key
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(payload)
        logger.info("Published locally: %s", out)


async def publish_flags(
    db: AsyncSession, project_id: UUID, environment_id: UUID, sdk_key: str
) -> None:
    """Build flag config JSON and publish to CDN.

    Publishes to {sdk_key}/flags.json. If the environment has a previous_sdk_key
    with an active grace period, also publishes to {previous_sdk_key}/flags.json
    so SDKs using the old key continue to receive updates.
    """
    try:
        # Get all flags for this project, then filter their flag_environments
        result = await db.execute(
            select(Flag).where(Flag.project_id == project_id)
        )
        flags = result.scalars().all()

        config = {
            "version": datetime.now(timezone.utc).isoformat(),
            "flags": {},
        }
        for flag in flags:
            # Find the FlagEnvironment for this specific environment
            fe = next(
                (fe for fe in flag.flag_environments if fe.environment_id == environment_id),
                None,
            )
            if fe is None:
                continue
            config["flags"][flag.key] = {
                "enabled": fe.enabled,
                "rollout_pct": fe.rollout_pct,
                "flag_type": flag.flag_type,
                "default_value": fe.default_value,
                "rules": [
                    {
                        "attribute": rule.attribute,
                        "operator": rule.operator,
                        "value": rule.value,
                    }
                    for rule in fe.rules
                ],
            }

        payload = json.dumps(config, indent=2)

        # Collect all CDN paths to publish to
        paths = [f"{sdk_key}/flags.json"]

        # Check for active grace period on previous key
        from app.environments.models import Environment
        env_result = await db.execute(
            select(Environment).where(Environment.id == environment_id)
        )
        env = env_result.scalar_one_or_none()
        if (
            env
            and env.previous_sdk_key
            and env.previous_sdk_key_expires_at
            and env.previous_sdk_key_expires_at > datetime.now(timezone.utc)
        ):
            paths.append(f"{env.previous_sdk_key}/flags.json")

        for object_key in paths:
            await asyncio.to_thread(_write_to_path, object_key, payload)
    except Exception:
        logger.exception("CDN publish failed for sdk_key %s", sdk_key)
