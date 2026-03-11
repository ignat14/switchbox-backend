import logging
import traceback

from fastapi import Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger("switchbox")


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    if isinstance(exc, IntegrityError):
        logger.warning("Integrity error on %s %s: %s", request.method, request.url.path, exc)
        return JSONResponse(
            status_code=409,
            content={"error": "conflict", "message": "Resource already exists or constraint violated"},
        )

    logger.error(
        "Unhandled error on %s %s: %s\n%s",
        request.method,
        request.url.path,
        exc,
        traceback.format_exc(),
    )
    return JSONResponse(
        status_code=500,
        content={"error": "internal_server_error", "message": "Something went wrong"},
    )
