import logging
import uuid
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.schemas import AuthResponse, GitHubCallbackRequest, UserResponse
from app.auth.service import (
    create_access_token,
    exchange_github_code,
    fetch_github_user,
    upsert_user,
    verify_token,
)
from app.config import settings
from app.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


async def _require_jwt(
    authorization: str = Header(), db: AsyncSession = Depends(get_db)
) -> User:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    token = authorization.removeprefix("Bearer ")
    try:
        payload = verify_token(token)
        user_id = uuid.UUID(payload["sub"])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid token")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    return user


@router.get("/github/login")
async def github_login():
    params = urlencode(
        {
            "client_id": settings.GITHUB_CLIENT_ID,
            "redirect_uri": f"{settings.FRONTEND_URL}/auth/callback",
            "scope": "read:user user:email",
        }
    )
    return {"url": f"https://github.com/login/oauth/authorize?{params}"}


@router.post("/github/callback", response_model=AuthResponse)
async def github_callback(
    body: GitHubCallbackRequest, db: AsyncSession = Depends(get_db)
):
    try:
        github_token = await exchange_github_code(body.code)
        github_user = await fetch_github_user(github_token)
    except Exception:
        logger.exception("GitHub OAuth exchange failed")
        raise HTTPException(status_code=400, detail="GitHub authentication failed")

    user = await upsert_user(db, github_user)
    access_token = create_access_token(user)

    return AuthResponse(
        access_token=access_token,
        user=UserResponse.model_validate(user),
    )


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(_require_jwt)):
    return UserResponse.model_validate(user)
