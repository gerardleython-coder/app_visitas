from __future__ import annotations

from secrets import compare_digest
from typing import NoReturn, cast
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.exc import IntegrityError

from app.application.manage_administrators import (
    AdministratorManagement,
    BootstrapAdministrator,
)
from app.domain.authentication import UserAccount, UserRole
from app.domain.errors import (
    ConflictException,
    DomainException,
    ForbiddenException,
    NotFoundException,
)
from app.domain.operator import OperatorProfile
from app.infrastructure.security_settings import SecuritySettings
from app.presentation.dependencies import (
    get_administrator_management,
    get_bootstrap_administrator,
    require_roles,
)


class AdministratorRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=100)
    surname: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=3, max_length=150)
    password: str = Field(min_length=1, max_length=1024)


class AdministratorUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=100)
    surname: str | None = Field(default=None, min_length=1, max_length=100)
    email: str | None = Field(default=None, min_length=3, max_length=150)

    @model_validator(mode="after")
    def validate_changes(self) -> AdministratorUpdateRequest:
        if not self.model_fields_set:
            raise ValueError("Debe indicar al menos un dato para actualizar")
        for field in ("name", "surname", "email"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} no puede ser nulo")
        return self


class AdministratorResponse(BaseModel):
    id: UUID
    name: str
    surname: str
    email: str
    role: UserRole
    active: bool
    district_id: UUID | None
    church_id: UUID | None


router = APIRouter(tags=["administrators"])


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


def _response(profile: OperatorProfile) -> AdministratorResponse:
    return AdministratorResponse(
        id=profile.id,
        name=profile.name,
        surname=profile.surname,
        email=profile.email,
        role=profile.role,
        active=profile.active,
        district_id=profile.district_id,
        church_id=profile.church_id,
    )


async def _create(
    request: AdministratorRequest,
    *,
    actor: UserAccount | None,
    use_case: AdministratorManagement | BootstrapAdministrator,
) -> AdministratorResponse:
    try:
        if actor is None:
            profile = await cast(BootstrapAdministrator, use_case).execute(
                name=request.name,
                surname=request.surname,
                email=request.email,
                password=request.password,
            )
            return AdministratorResponse(
                id=profile.id,
                name=request.name,
                surname=request.surname,
                email=profile.email,
                role=profile.role,
                active=profile.active,
                district_id=None,
                church_id=None,
            )

        return _response(
            await cast(AdministratorManagement, use_case).create(
                actor,
                name=request.name,
                surname=request.surname,
                email=request.email,
                password=request.password,
            )
        )
    except DomainException as error:
        _raise_domain_http_error(error)
    except IntegrityError as error:
        raise HTTPException(
            status_code=409,
            detail={"code": "conflict", "message": "Conflicto al crear el administrador"},
        ) from error


@router.post("/auth/bootstrap-admin", response_model=AdministratorResponse, status_code=201)
async def bootstrap_admin(
    request: AdministratorRequest,
    bootstrap_token: str | None = Header(default=None, alias="X-Bootstrap-Token"),
    use_case: BootstrapAdministrator = Depends(get_bootstrap_administrator),
) -> AdministratorResponse:
    configured_token = SecuritySettings().bootstrap_token
    if not configured_token:
        raise HTTPException(status_code=404, detail="Not found")
    if bootstrap_token is None or not compare_digest(bootstrap_token, configured_token):
        raise HTTPException(
            status_code=403,
            detail={"code": "forbidden", "message": "Permisos insuficientes"},
        )
    return await _create(request, actor=None, use_case=use_case)


@router.get("/users/administradores", response_model=list[AdministratorResponse])
async def list_administrators(
    actor: UserAccount = Depends(require_roles(UserRole.ADMIN)),
    management: AdministratorManagement = Depends(get_administrator_management),
) -> list[AdministratorResponse]:
    try:
        return [_response(profile) for profile in await management.list(actor)]
    except DomainException as error:
        _raise_domain_http_error(error)


@router.post(
    "/users/administradores",
    response_model=AdministratorResponse,
    status_code=201,
)
async def create_administrator(
    request: AdministratorRequest,
    actor: UserAccount = Depends(require_roles(UserRole.ADMIN)),
    management: AdministratorManagement = Depends(get_administrator_management),
) -> AdministratorResponse:
    return await _create(request, actor=actor, use_case=management)


@router.patch(
    "/users/administradores/{administrator_id}",
    response_model=AdministratorResponse,
)
async def update_administrator(
    administrator_id: UUID,
    request: AdministratorUpdateRequest,
    actor: UserAccount = Depends(require_roles(UserRole.ADMIN)),
    management: AdministratorManagement = Depends(get_administrator_management),
) -> AdministratorResponse:
    try:
        profile = await management.update(
            actor,
            administrator_id,
            request.model_dump(exclude_unset=True),
        )
    except DomainException as error:
        _raise_domain_http_error(error)
    except IntegrityError as error:
        raise HTTPException(
            status_code=409,
            detail={"code": "conflict", "message": "Conflicto al actualizar el administrador"},
        ) from error
    return _response(profile)


@router.delete("/users/administradores/{administrator_id}", status_code=204)
async def deactivate_administrator(
    administrator_id: UUID,
    actor: UserAccount = Depends(require_roles(UserRole.ADMIN)),
    management: AdministratorManagement = Depends(get_administrator_management),
) -> Response:
    try:
        await management.deactivate(actor, administrator_id)
    except DomainException as error:
        _raise_domain_http_error(error)
    return Response(status_code=204)