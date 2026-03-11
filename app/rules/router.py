from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.database import get_db
from app.middleware.auth import get_current_user
from app.rules import service as rule_service
from app.rules.schemas import RuleCreate, RuleResponse

router = APIRouter(tags=["rules"], dependencies=[Depends(get_current_user)])


@router.post("/flags/{flag_id}/rules", response_model=RuleResponse, status_code=201)
async def add_rule(
    flag_id: UUID,
    body: RuleCreate,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    changed_by = user.github_login if user else "admin"
    return await rule_service.add_rule(db, flag_id, body, changed_by=changed_by)


@router.delete("/rules/{rule_id}", status_code=204)
async def remove_rule(
    rule_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User | None = Depends(get_current_user),
):
    changed_by = user.github_login if user else "admin"
    await rule_service.remove_rule(db, rule_id, changed_by=changed_by)
