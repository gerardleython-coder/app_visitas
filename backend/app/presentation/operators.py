from __future__ import annotations

from uuid import UUID
from typing import NoReturn

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.exc import IntegrityError

from app.application.create_operator import CreateOperator
from app.application.manage_operators import OperatorManagement
from app.domain.authentication import UserAccount, UserRole
from app.domain.errors import (
    ConflictException,
    DomainException,
    ForbiddenException,
    NotFoundException,
)
from app.domain.operator import OperatorProfile
from app.presentation.dependencies import (
    get_create_operator,
    get_operator_management,
    require_roles,
)


class OperatorRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    surname: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=3, max_length=150)
    password: str = Field(min_length=1, max_length=1024)
    district_id: UUID
    church_id: UUID


class OperatorResponse(BaseModel):
    id: UUID
    name: str
    surname: str
    email: str
    role: UserRole
    active: bool
    district_id: UUID
    church_id: UUID
    phone: str | None = None
    address: str | None = None
    is_primary_pastor: bool = False


class OperatorUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=100)
    surname: str | None = Field(default=None, min_length=1, max_length=100)
    email: str | None = Field(default=None, min_length=3, max_length=150)
    phone: str | None = Field(default=None, max_length=30)
    address: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_changes(self) -> OperatorUpdateRequest:
        if not self.model_fields_set:
            raise ValueError("Debe indicar al menos un dato para actualizar")
        for field in ("name", "surname", "email"):
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"{field} no puede ser nulo")
        return self


class PrimaryPastorRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pastor_id: UUID


router = APIRouter(tags=["operators"])


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


def _operator_response(operator: OperatorProfile) -> OperatorResponse:
    return OperatorResponse(
        id=operator.id,
        name=operator.name,
        surname=operator.surname,
        email=operator.email,
        role=operator.role,
        active=operator.active,
        district_id=operator.district_id,
        church_id=operator.church_id,
        phone=operator.phone,
        address=operator.address,
        is_primary_pastor=operator.is_primary_pastor,
    )


async def _create_operator(
    request: OperatorRequest,
    *,
    role: UserRole,
    actor: UserAccount,
    use_case: CreateOperator,
) -> OperatorResponse:
    try:
        account = await use_case.execute(
            actor_role=actor.role,
            actor_id=actor.id,
            name=request.name,
            surname=request.surname,
            email=request.email,
            password=request.password,
            role=role,
            district_id=request.district_id,
            church_id=request.church_id,
        )
    except ForbiddenException as error:
        _raise_domain_http_error(error)
    except DomainException as error:
        _raise_domain_http_error(error)
    except IntegrityError as error:
        raise HTTPException(
            status_code=409,
            detail={"code": "conflict", "message": "Conflicto al crear el usuario"},
        ) from error

    return OperatorResponse(
        id=account.id,
        name=request.name,
        surname=request.surname,
        email=account.email,
        role=account.role,
        active=account.active,
        district_id=request.district_id,
        church_id=request.church_id,
    )


async def _update_operator(
    request: OperatorUpdateRequest,
    *,
    actor: UserAccount,
    operator_id: UUID,
    role: UserRole,
    management: OperatorManagement,
) -> OperatorResponse:
    try:
        operator = await management.update_operator(
            actor,
            operator_id,
            role,
            request.model_dump(exclude_unset=True),
        )
    except DomainException as error:
        _raise_domain_http_error(error)
    except IntegrityError as error:
        raise HTTPException(
            status_code=409,
            detail={"code": "conflict", "message": "Conflicto al actualizar el usuario"},
        ) from error
    return _operator_response(operator)


async def _deactivate_operator(
    *,
    actor: UserAccount,
    operator_id: UUID,
    role: UserRole,
    management: OperatorManagement,
) -> Response:
    try:
        await management.deactivate_operator(actor, operator_id, role)
    except DomainException as error:
        _raise_domain_http_error(error)
    except IntegrityError as error:
        raise HTTPException(
            status_code=409,
            detail={"code": "conflict", "message": "Conflicto al desactivar el usuario"},
        ) from error
    return Response(status_code=204)


@router.post("/users/pastores", response_model=OperatorResponse, status_code=201)
async def create_pastor(
    request: OperatorRequest,
    actor: UserAccount = Depends(require_roles(UserRole.ADMIN)),
    use_case: CreateOperator = Depends(get_create_operator),
) -> OperatorResponse:
    return await _create_operator(
        request,
        role=UserRole.PASTOR,
        actor=actor,
        use_case=use_case,
    )


@router.post("/users/lideres", response_model=OperatorResponse, status_code=201)
async def create_leader(
    request: OperatorRequest,
    actor: UserAccount = Depends(require_roles(UserRole.ADMIN)),
    use_case: CreateOperator = Depends(get_create_operator),
) -> OperatorResponse:
    return await _create_operator(
        request,
        role=UserRole.LIDER,
        actor=actor,
        use_case=use_case,
    )


@router.get("/users/pastores", response_model=list[OperatorResponse])
async def list_pastors(
    actor: UserAccount = Depends(require_roles(UserRole.ADMIN)),
    management: OperatorManagement = Depends(get_operator_management),
) -> list[OperatorResponse]:
    try:
        operators = await management.list_operators(actor, UserRole.PASTOR)
    except DomainException as error:
        _raise_domain_http_error(error)
    return [_operator_response(operator) for operator in operators]


@router.get("/users/lideres", response_model=list[OperatorResponse])
async def list_leaders(
    actor: UserAccount = Depends(require_roles(UserRole.ADMIN, UserRole.PASTOR)),
    management: OperatorManagement = Depends(get_operator_management),
) -> list[OperatorResponse]:
    try:
        operators = await management.list_operators(actor, UserRole.LIDER)
    except DomainException as error:
        _raise_domain_http_error(error)
    return [_operator_response(operator) for operator in operators]


@router.patch("/users/pastores/{operator_id}", response_model=OperatorResponse)
async def update_pastor(
    operator_id: UUID,
    request: OperatorUpdateRequest,
    actor: UserAccount = Depends(require_roles(UserRole.ADMIN)),
    management: OperatorManagement = Depends(get_operator_management),
) -> OperatorResponse:
    return await _update_operator(
        request,
        actor=actor,
        operator_id=operator_id,
        role=UserRole.PASTOR,
        management=management,
    )


@router.patch("/users/lideres/{operator_id}", response_model=OperatorResponse)
async def update_leader(
    operator_id: UUID,
    request: OperatorUpdateRequest,
    actor: UserAccount = Depends(require_roles(UserRole.ADMIN, UserRole.PASTOR)),
    management: OperatorManagement = Depends(get_operator_management),
) -> OperatorResponse:
    return await _update_operator(
        request,
        actor=actor,
        operator_id=operator_id,
        role=UserRole.LIDER,
        management=management,
    )


@router.delete("/users/pastores/{operator_id}", status_code=204)
async def deactivate_pastor(
    operator_id: UUID,
    actor: UserAccount = Depends(require_roles(UserRole.ADMIN)),
    management: OperatorManagement = Depends(get_operator_management),
) -> Response:
    return await _deactivate_operator(
        actor=actor,
        operator_id=operator_id,
        role=UserRole.PASTOR,
        management=management,
    )


@router.delete("/users/lideres/{operator_id}", status_code=204)
async def deactivate_leader(
    operator_id: UUID,
    actor: UserAccount = Depends(require_roles(UserRole.ADMIN, UserRole.PASTOR)),
    management: OperatorManagement = Depends(get_operator_management),
) -> Response:
    return await _deactivate_operator(
        actor=actor,
        operator_id=operator_id,
        role=UserRole.LIDER,
        management=management,
    )


@router.patch(
    "/admin/iglesias/{church_id}/pastor-principal",
    response_model=OperatorResponse,
)
async def set_primary_pastor(
    church_id: UUID,
    request: PrimaryPastorRequest,
    actor: UserAccount = Depends(require_roles(UserRole.ADMIN)),
    management: OperatorManagement = Depends(get_operator_management),
) -> OperatorResponse:
    try:
        operator = await management.set_primary_pastor(actor, church_id, request.pastor_id)
    except DomainException as error:
        _raise_domain_http_error(error)
    except IntegrityError as error:
        raise HTTPException(
            status_code=409,
            detail={"code": "conflict", "message": "Conflicto al asignar pastor principal"},
        ) from error
    return _operator_response(operator)