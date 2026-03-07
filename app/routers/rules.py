from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import require_admin
from app.schemas.rule import RuleCreate, RuleResponse
from app.services import rule_service

router = APIRouter(tags=["rules"], dependencies=[Depends(require_admin)])


@router.post("/flags/{flag_id}/rules", response_model=RuleResponse, status_code=201)
async def add_rule(
    flag_id: UUID, body: RuleCreate, db: AsyncSession = Depends(get_db)
):
    return await rule_service.add_rule(db, flag_id, body)


@router.delete("/rules/{rule_id}", status_code=204)
async def remove_rule(rule_id: UUID, db: AsyncSession = Depends(get_db)):
    await rule_service.remove_rule(db, rule_id)
