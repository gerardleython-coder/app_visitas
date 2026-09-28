from datetime import datetime
from typing import NoReturn
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.application.audit import ListAudit
from app.domain.audit import AuditEvent
from app.domain.authentication import UserAccount, UserRole
from app.domain.errors import ForbiddenException
from app.presentation.dependencies import get_audit_query, require_roles


class AuditResponse(BaseModel):
    id: UUID
    actor_id: UUID
    resource: str
    resource_id: UUID
    action: str
    church_id: UUID | None
    previous_values: dict[str, object] | None
    new_values: dict[str, object] | None
    reason: str | None
    created_at: datetime


router = APIRouter(tags=["audit"])


def _response(event: AuditEvent) -> AuditResponse:
    return AuditResponse(
        id=event.id,
        actor_id=event.actor_id,
        resource=event.resource,
        resource_id=event.resource_id,
        action=event.action,
        church_id=event.church_id,
        previous_values=event.previous_values,
        new_values=event.new_values,
        reason=event.reason,
        created_at=event.created_at,
    )


def _raise_forbidden(error: ForbiddenException) -> NoReturn:
    raise HTTPException(
        status_code=403,
        detail={"code": "forbidden", "message": "Permisos insuficientes"},
    ) from error


@router.get("/audit", response_model=list[AuditResponse])
async def list_audit(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    actor: UserAccount = Depends(require_roles(UserRole.ADMIN, UserRole.PASTOR)),
    query: ListAudit = Depends(get_audit_query),
) -> list[AuditResponse]:
    try:
        events = await query.execute(actor, offset=offset, limit=limit)
    except ForbiddenException as error:
        _raise_forbidden(error)
    return [_response(event) for event in events]