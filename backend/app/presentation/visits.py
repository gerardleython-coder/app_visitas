from __future__ import annotations

from datetime import datetime
from typing import NoReturn
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.exc import IntegrityError

from app.application.manage_visits import ManageVisits
from app.application.visit_commands import CancelVisitCommand, CreateVisitCommand, UpdateVisitCommand
from app.domain.authentication import UserAccount, UserRole
from app.domain.errors import (
    ConflictException,
    DomainException,
    ForbiddenException,
    NotFoundException,
)
from app.domain.visit import Visit, VisitHistoryEntry, VisitStatus, VisitType
from app.presentation.dependencies import get_visit_management, require_roles


class VisitCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    brother_id: UUID
    visit_type: VisitType
    scheduled_at: datetime
    duration_minutes: int = Field(gt=0)
    location: str = Field(min_length=1, max_length=500)
    observations: str = Field(min_length=1, max_length=4000)


class VisitUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    visit_type: VisitType | None = None
    scheduled_at: datetime | None = None
    duration_minutes: int | None = Field(default=None, gt=0)
    location: str | None = Field(default=None, min_length=1, max_length=500)
    observations: str | None = Field(default=None, min_length=1, max_length=4000)
    status: VisitStatus | None = None

    @model_validator(mode="after")
    def validate_changes(self) -> VisitUpdateRequest:
        if not self.model_fields_set:
            raise ValueError("Debe indicar al menos un cambio")
        for field in self.model_fields_set:
            if getattr(self, field) is None:
                raise ValueError(f"{field} no puede ser nulo")
        return self


class VisitCancelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    reason: str = Field(min_length=1, max_length=2000)


class VisitResponse(BaseModel):
    id: UUID
    brother_id: UUID
    leader_id: UUID
    created_by: UUID
    visit_type: VisitType
    scheduled_at: datetime
    completed_at: datetime | None
    duration_minutes: int
    location: str
    observations: str
    status: VisitStatus
    cancellation_reason: str | None
    created_at: datetime
    updated_at: datetime


class VisitHistoryResponse(BaseModel):
    id: UUID
    visit_id: UUID
    actor_id: UUID
    action: str
    previous_status: VisitStatus | None
    new_status: VisitStatus | None
    previous_scheduled_at: datetime | None
    new_scheduled_at: datetime | None
    previous_values: dict[str, object] | None
    new_values: dict[str, object] | None
    reason: str | None
    created_at: datetime


router = APIRouter(tags=["visits"])


def _raise_domain_http_error(error: DomainException) -> NoReturn:
    if isinstance(error, ForbiddenException):
        raise HTTPException(
            status_code=403,
            detail={"code": "forbidden", "message": "Permisos insuficientes"},
        ) from error
    if isinstance(error, NotFoundException):
        raise HTTPException(
            status_code=404,
            detail={"code": "not_found", "message": str(error)},
        ) from error
    if isinstance(error, ConflictException):
        raise HTTPException(
            status_code=409,
            detail={"code": "conflict", "message": str(error)},
        ) from error
    raise HTTPException(
        status_code=422,
        detail={"code": "invalid_operation", "message": str(error)},
    ) from error


def _raise_integrity_conflict(error: IntegrityError) -> NoReturn:
    raise HTTPException(
        status_code=409,
        detail={"code": "conflict", "message": "Conflicto con el estado o asignación de la visita"},
    ) from error


def _response(visit: Visit) -> VisitResponse:
    return VisitResponse(
        id=visit.id,
        brother_id=visit.brother_id,
        leader_id=visit.leader_id,
        created_by=visit.created_by_id,
        visit_type=visit.visit_type,
        scheduled_at=visit.scheduled_at,
        completed_at=visit.completed_at,
        duration_minutes=visit.duration_minutes,
        location=visit.location,
        observations=visit.observations,
        status=visit.status,
        cancellation_reason=visit.cancellation_reason,
        created_at=visit.created_at,
        updated_at=visit.updated_at,
    )


def _history_response(entry: VisitHistoryEntry) -> VisitHistoryResponse:
    return VisitHistoryResponse(
        id=entry.id,
        visit_id=entry.visit_id,
        actor_id=entry.actor_id,
        action=entry.action,
        previous_status=entry.previous_status,
        new_status=entry.new_status,
        previous_scheduled_at=entry.previous_scheduled_at,
        new_scheduled_at=entry.new_scheduled_at,
        previous_values=entry.previous_values,
        new_values=entry.new_values,
        reason=entry.reason,
        created_at=entry.created_at,
    )


@router.post("/visitas", response_model=VisitResponse, status_code=201)
async def create_visit(
    request: VisitCreateRequest,
    actor: UserAccount = Depends(
        require_roles(UserRole.ADMIN, UserRole.PASTOR, UserRole.LIDER)
    ),
    management: ManageVisits = Depends(get_visit_management),
) -> VisitResponse:
    try:
        visit = await management.create(
            CreateVisitCommand(
                actor=actor,
                brother_id=request.brother_id,
                visit_type=request.visit_type,
                scheduled_at=request.scheduled_at,
                duration_minutes=request.duration_minutes,
                location=request.location,
                observations=request.observations,
            )
        )
    except DomainException as error:
        _raise_domain_http_error(error)
    except IntegrityError as error:
        _raise_integrity_conflict(error)
    return _response(visit)


@router.get("/visitas", response_model=list[VisitResponse])
async def list_visits(
    actor: UserAccount = Depends(
        require_roles(UserRole.ADMIN, UserRole.PASTOR, UserRole.LIDER)
    ),
    management: ManageVisits = Depends(get_visit_management),
) -> list[VisitResponse]:
    try:
        visits = await management.list_visits(actor)
    except DomainException as error:
        _raise_domain_http_error(error)
    return [_response(visit) for visit in visits]


@router.get("/visitas/{visit_id}", response_model=VisitResponse)
async def get_visit(
    visit_id: UUID,
    actor: UserAccount = Depends(
        require_roles(UserRole.ADMIN, UserRole.PASTOR, UserRole.LIDER)
    ),
    management: ManageVisits = Depends(get_visit_management),
) -> VisitResponse:
    try:
        visit = await management.get(actor, visit_id)
    except DomainException as error:
        _raise_domain_http_error(error)
    return _response(visit)


@router.patch("/visitas/{visit_id}", response_model=VisitResponse)
async def update_visit(
    visit_id: UUID,
    request: VisitUpdateRequest,
    actor: UserAccount = Depends(
        require_roles(UserRole.ADMIN, UserRole.PASTOR, UserRole.LIDER)
    ),
    management: ManageVisits = Depends(get_visit_management),
) -> VisitResponse:
    try:
        visit = await management.update(
            UpdateVisitCommand(
                actor=actor,
                visit_id=visit_id,
                changes=request.model_dump(exclude_unset=True),
            )
        )
    except DomainException as error:
        _raise_domain_http_error(error)
    except IntegrityError as error:
        _raise_integrity_conflict(error)
    return _response(visit)


@router.delete("/visitas/{visit_id}", status_code=204)
async def cancel_visit(
    visit_id: UUID,
    request: VisitCancelRequest,
    actor: UserAccount = Depends(
        require_roles(UserRole.ADMIN, UserRole.PASTOR, UserRole.LIDER)
    ),
    management: ManageVisits = Depends(get_visit_management),
) -> Response:
    try:
        await management.cancel(
            CancelVisitCommand(actor=actor, visit_id=visit_id, reason=request.reason)
        )
    except DomainException as error:
        _raise_domain_http_error(error)
    except IntegrityError as error:
        _raise_integrity_conflict(error)
    return Response(status_code=204)


@router.get("/visitas/{visit_id}/history", response_model=list[VisitHistoryResponse])
async def visit_history(
    visit_id: UUID,
    actor: UserAccount = Depends(require_roles(UserRole.ADMIN, UserRole.PASTOR)),
    management: ManageVisits = Depends(get_visit_management),
) -> list[VisitHistoryResponse]:
    try:
        entries = await management.history(actor, visit_id)
    except DomainException as error:
        _raise_domain_http_error(error)
    return [_history_response(entry) for entry in entries]