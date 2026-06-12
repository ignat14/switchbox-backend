"""SDK connection liveness, read back from Cloudflare KV.

The CDN Worker (switchbox-worker-cdn) upserts `conn:{sdk_key}` with an ISO
timestamp on each flags.json fetch, throttled to one write per 5 minutes per
key. This module reads those keys via the Cloudflare KV REST API so the
dashboard can show a "Connected" badge. Admin-side read only — the API stays
out of the SDK read path.
"""

import logging
import time
from datetime import datetime, timedelta, timezone

import httpx

from app.config import settings
from app.environments.models import Environment
from app.environments.schemas import EnvironmentConnectionResponse

logger = logging.getLogger(__name__)

# Worker KV write throttle (5 min) + SDK poll interval (30s) + slack.
CONNECTED_WINDOW = timedelta(minutes=7)

# Server-side cache so a dashboard polling many environments every ~10s
# doesn't turn into one Cloudflare API call per environment per poll.
CACHE_TTL_SECONDS = 10.0

KV_REQUEST_TIMEOUT = 5.0

_cache: dict[str, tuple[float, EnvironmentConnectionResponse]] = {}


def _is_configured() -> bool:
    return bool(
        settings.CF_KV_API_TOKEN
        and settings.CF_KV_NAMESPACE_ID
        and settings.R2_ACCOUNT_ID
    )


async def _read_last_seen(client: httpx.AsyncClient, sdk_key: str) -> datetime | None:
    """Read conn:{sdk_key} from KV. None if the key has never been written."""
    url = (
        f"https://api.cloudflare.com/client/v4/accounts/{settings.R2_ACCOUNT_ID}"
        f"/storage/kv/namespaces/{settings.CF_KV_NAMESPACE_ID}/values/conn:{sdk_key}"
    )
    response = await client.get(
        url, headers={"Authorization": f"Bearer {settings.CF_KV_API_TOKEN}"}
    )
    if response.status_code == 404:
        return None
    response.raise_for_status()
    # The Worker writes Date.toISOString() — e.g. "2026-06-12T10:00:00.000Z".
    return datetime.fromisoformat(response.text.strip())


def _as_utc(value: datetime) -> datetime:
    # SQLite (tests) returns naive datetimes even for timezone-aware columns.
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


async def get_connection(env: Environment) -> EnvironmentConnectionResponse:
    """Resolve the connection status for an environment.

    Statuses: `never` (no fetch ever), `connected` (seen within the window),
    `stale` (seen, but quiet), `unknown` (KV unconfigured or unreachable —
    fail soft rather than showing a misleading "never").
    """
    if not _is_configured():
        return EnvironmentConnectionResponse(status="unknown", last_seen_at=None)

    cache_key = str(env.id)
    cached = _cache.get(cache_key)
    if cached and time.monotonic() - cached[0] < CACHE_TTL_SECONDS:
        return cached[1]

    now = datetime.now(timezone.utc)

    # During a key-rotation grace period clients may still poll the old key —
    # without this the badge would show "never" for 24h after a rotation.
    sdk_keys = [env.sdk_key]
    if (
        env.previous_sdk_key
        and env.previous_sdk_key_expires_at
        and _as_utc(env.previous_sdk_key_expires_at) > now
    ):
        sdk_keys.append(env.previous_sdk_key)

    try:
        async with httpx.AsyncClient(timeout=KV_REQUEST_TIMEOUT) as client:
            timestamps = [await _read_last_seen(client, key) for key in sdk_keys]
    except Exception:
        logger.warning("KV connection lookup failed", exc_info=True)
        return EnvironmentConnectionResponse(status="unknown", last_seen_at=None)

    seen = [_as_utc(ts) for ts in timestamps if ts is not None]
    last_seen_at = max(seen) if seen else None

    if last_seen_at is None:
        result = EnvironmentConnectionResponse(status="never", last_seen_at=None)
    elif now - last_seen_at <= CONNECTED_WINDOW:
        result = EnvironmentConnectionResponse(
            status="connected", last_seen_at=last_seen_at
        )
    else:
        result = EnvironmentConnectionResponse(
            status="stale", last_seen_at=last_seen_at
        )

    _cache[cache_key] = (time.monotonic(), result)
    return result
