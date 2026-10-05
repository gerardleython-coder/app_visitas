from __future__ import annotations

from typing import NoReturn
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.exc import IntegrityError

from app.application.manage_brothers import ManageBrothers
from app.domain.authentication import UserAccount, UserRole
from app.domain.brother import BrotherProfile
from app.domain.errors import (
    ConflictException,
    DomainException,
    ForbiddenException,
    NotFoundException,
)
from app.presentation.dependencies import get_brother_management, require_roles


class BrotherCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=100)
    surname: str = Field(min_length=1, max_length=100)
    phone: str = Field(min_length=1, max_length=30)
    address: str = Field(min_length=1, max_length=2000)
    district_id: UUID
    church_id: UUID
    leader_id: UUID | None = None


class BrotherUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=100)
    surname: str | None = Field(default=None, min_length=1, max_length=100)
    phone: str | None = Field(default=None, min_length=1, max_length=30)
    address: str | None = Field(default=None, min_length=1, max_length=2000)

    @model_validator(mode="after")
    def validate_changes(self) -> BrotherUpdateRequest:
        if not self.model_fields_set:
            raise ValueError("Debe indicar al menos un dato para actualizar")
        for field in ("name", "surname", "phone", "address"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} no puede ser nulo")
        return self


class LeaderAssignmentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    leader_id: UUID


class BrotherResponse(BaseModel):
    id: UUID
    name: str
    surname: str
    phone: str
    address: str
    district_id: UUID
    church_id: UUID
    leader_id: UUID
    role: UserRole = UserRole.HERMANO
    active: bool


router = APIRouter(tags=["brothers"])


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


def _response(brother: BrotherProfile) -> BrotherResponse:
    return BrotherResponse(
        id=brother.id,
        name=brother.name,
        surname=brother.surname,
        phone=brother.phone,
        address=brother.address,
        district_id=brother.district_id,
        church_id=brother.church_id,
        leader_id=brother.leader_id,
        active=brother.active,
    )


def _raise_integrity_conflict(error: IntegrityError) -> NoReturn:
    raise HTTPException(
        status_code=409,
        detail={"code": "conflict", "message": "Conflicto con las asignaciones del hermano"},
    ) from error


@router.post("/hermanos", response_model=BrotherResponse, status_code=201)
async def create_brother(
    request: BrotherCreateRequest,
    actor: UserAccount = Depends(
        require_roles(UserRole.ADMIN, UserRole.PASTOR, UserRole.LIDER)
    ),
    management: ManageBrothers = Depends(get_brother_management),
) -> BrotherResponse:
    try:
        brother = await management.create_brother(
            actor,
            name=request.name,
            surname=request.surname,
            phone=request.phone,
            address=request.address,
            district_id=request.district_id,
            church_id=request.church_id,
            leader_id=request.leader_id,
        )
    except DomainException as error:
        _raise_domain_http_error(error)
    except IntegrityError as error:
        _raise_integrity_conflict(error)
    return _response(brother)


@router.get("/hermanos", response_model=list[BrotherResponse])
async def list_brothers(
    actor: UserAccount = Depends(
        require_roles(UserRole.ADMIN, UserRole.PASTOR, UserRole.LIDER)
    ),
    management: ManageBrothers = Depends(get_brother_management),
) -> list[BrotherResponse]:
    try:
        brothers = await management.list_brothers(actor)
    except DomainException as error:
        _raise_domain_http_error(error)
    return [_response(brother) for brother in brothers]


@router.get("/hermanos/{brother_id}", response_model=BrotherResponse)
async def get_brother(
    brother_id: UUID,
    actor: UserAccount = Depends(
        require_roles(UserRole.ADMIN, UserRole.PASTOR, UserRole.LIDER)
    ),
    management: ManageBrothers = Depends(get_brother_management),
) -> BrotherResponse:
    try:
        brother = await management.get_brother(actor, brother_id)
    except DomainException as error:
        _raise_domain_http_error(error)
    return _response(brother)


@router.patch("/hermanos/{brother_id}", response_model=BrotherResponse)
async def update_brother(
    brother_id: UUID,
    request: BrotherUpdateRequest,
    actor: UserAccount = Depends(
        require_roles(UserRole.ADMIN, UserRole.PASTOR, UserRole.LIDER)
    ),
    management: ManageBrothers = Depends(get_brother_management),
) -> BrotherResponse:
    try:
        brother = await management.update_brother(
            actor,
            brother_id,
            request.model_dump(exclude_unset=True),
        )
    except DomainException as error:
        _raise_domain_http_error(error)
    except IntegrityError as error:
        _raise_integrity_conflict(error)
    return _response(brother)


@router.delete("/hermanos/{brother_id}", status_code=204)
async def deactivate_brother(
    brother_id: UUID,
    actor: UserAccount = Depends(
        require_roles(UserRole.ADMIN, UserRole.PASTOR, UserRole.LIDER)
    ),
    management: ManageBrothers = Depends(get_brother_management),
) -> Response:
    try:
        await management.deactivate_brother(actor, brother_id)
    except DomainException as error:
        _raise_domain_http_error(error)
    except IntegrityError as error:
        _raise_integrity_conflict(error)
    return Response(status_code=204)


@router.patch("/hermanos/{brother_id}/lider", response_model=BrotherResponse)
async def reassign_brother_leader(
    brother_id: UUID,
    request: LeaderAssignmentRequest,
    actor: UserAccount = Depends(require_roles(UserRole.ADMIN, UserRole.PASTOR)),
    management: ManageBrothers = Depends(get_brother_management),
) -> BrotherResponse:
    try:
        brother = await management.reassign_leader(
            actor,
            brother_id,
            request.leader_id,
        )
    except DomainException as error:
        _raise_domain_http_error(error)
    except IntegrityError as error:
        _raise_integrity_conflict(error)
    return _response(brother)