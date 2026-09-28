from typing import NoReturn
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.exc import IntegrityError

from app.application.manage_territories import ManageTerritories
from app.domain.authentication import UserAccount, UserRole
from app.domain.errors import (
    ConflictException,
    DomainException,
    ForbiddenException,
    NotFoundException,
)
from app.domain.organization import Church, District
from app.presentation.dependencies import get_territory_management, require_roles


class DistrictCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=100)


class DistrictUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_changes(self) -> "DistrictUpdateRequest":
        if not self.model_fields_set:
            raise ValueError("Debe indicar al menos un dato para actualizar")
        if "name" in self.model_fields_set and self.name is None:
            raise ValueError("name no puede ser nulo")
        return self


class ChurchCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    district_id: UUID
    name: str = Field(min_length=1, max_length=150)
    address: str | None = Field(default=None, max_length=2000)


class ChurchUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=150)
    address: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_changes(self) -> "ChurchUpdateRequest":
        if not self.model_fields_set:
            raise ValueError("Debe indicar al menos un dato para actualizar")
        if "name" in self.model_fields_set and self.name is None:
            raise ValueError("name no puede ser nulo")
        return self


class DistrictResponse(BaseModel):
    id: UUID
    name: str


class ChurchResponse(BaseModel):
    id: UUID
    district_id: UUID
    name: str
    address: str | None
    active: bool


router = APIRouter(tags=["territories"])


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


def _district_response(district: District) -> DistrictResponse:
    return DistrictResponse(id=district.id, name=district.name)


def _church_response(church: Church) -> ChurchResponse:
    return ChurchResponse(
        id=church.id,
        district_id=church.district_id,
        name=church.name,
        address=church.address,
        active=church.active,
    )


def _raise_integrity_conflict(error: IntegrityError) -> NoReturn:
    raise HTTPException(
        status_code=409,
        detail={"code": "conflict", "message": "Conflicto con las asignaciones territoriales"},
    ) from error


@router.get("/admin/distritos", response_model=list[DistrictResponse])
async def list_districts(
    actor: UserAccount = Depends(require_roles(UserRole.ADMIN)),
    management: ManageTerritories = Depends(get_territory_management),
) -> list[DistrictResponse]:
    try:
        districts = await management.list_districts(actor)
    except DomainException as error:
        _raise_domain_http_error(error)
    return [_district_response(district) for district in districts]


@router.post("/admin/distritos", response_model=DistrictResponse, status_code=201)
async def create_district(
    request: DistrictCreateRequest,
    actor: UserAccount = Depends(require_roles(UserRole.ADMIN)),
    management: ManageTerritories = Depends(get_territory_management),
) -> DistrictResponse:
    try:
        district = await management.create_district(actor, request.name)
    except DomainException as error:
        _raise_domain_http_error(error)
    except IntegrityError as error:
        _raise_integrity_conflict(error)
    return _district_response(district)


@router.patch("/admin/distritos/{district_id}", response_model=DistrictResponse)
async def update_district(
    district_id: UUID,
    request: DistrictUpdateRequest,
    actor: UserAccount = Depends(require_roles(UserRole.ADMIN)),
    management: ManageTerritories = Depends(get_territory_management),
) -> DistrictResponse:
    try:
        district = await management.update_district(
            actor,
            district_id,
            request.model_dump(exclude_unset=True),
        )
    except DomainException as error:
        _raise_domain_http_error(error)
    except IntegrityError as error:
        _raise_integrity_conflict(error)
    return _district_response(district)


@router.delete("/admin/distritos/{district_id}", status_code=204)
async def delete_district(
    district_id: UUID,
    actor: UserAccount = Depends(require_roles(UserRole.ADMIN)),
    management: ManageTerritories = Depends(get_territory_management),
) -> Response:
    try:
        await management.delete_district(actor, district_id)
    except DomainException as error:
        _raise_domain_http_error(error)
    except IntegrityError as error:
        _raise_integrity_conflict(error)
    return Response(status_code=204)


@router.get("/admin/iglesias", response_model=list[ChurchResponse])
async def list_churches(
    district_id: UUID | None = Query(default=None),
    actor: UserAccount = Depends(require_roles(UserRole.ADMIN)),
    management: ManageTerritories = Depends(get_territory_management),
) -> list[ChurchResponse]:
    try:
        churches = await management.list_churches(actor, district_id=district_id)
    except DomainException as error:
        _raise_domain_http_error(error)
    return [_church_response(church) for church in churches]


@router.post("/admin/iglesias", response_model=ChurchResponse, status_code=201)
async def create_church(
    request: ChurchCreateRequest,
    actor: UserAccount = Depends(require_roles(UserRole.ADMIN)),
    management: ManageTerritories = Depends(get_territory_management),
) -> ChurchResponse:
    try:
        church = await management.create_church(
            actor,
            district_id=request.district_id,
            name=request.name,
            address=request.address,
        )
    except DomainException as error:
        _raise_domain_http_error(error)
    except IntegrityError as error:
        _raise_integrity_conflict(error)
    return _church_response(church)


@router.patch("/admin/iglesias/{church_id}", response_model=ChurchResponse)
async def update_church(
    church_id: UUID,
    request: ChurchUpdateRequest,
    actor: UserAccount = Depends(require_roles(UserRole.ADMIN)),
    management: ManageTerritories = Depends(get_territory_management),
) -> ChurchResponse:
    try:
        church = await management.update_church(
            actor,
            church_id,
            request.model_dump(exclude_unset=True),
        )
    except DomainException as error:
        _raise_domain_http_error(error)
    except IntegrityError as error:
        _raise_integrity_conflict(error)
    return _church_response(church)


@router.delete("/admin/iglesias/{church_id}", status_code=204)
async def delete_church(
    church_id: UUID,
    actor: UserAccount = Depends(require_roles(UserRole.ADMIN)),
    management: ManageTerritories = Depends(get_territory_management),
) -> Response:
    try:
        await management.delete_church(actor, church_id)
    except DomainException as error:
        _raise_domain_http_error(error)
    except IntegrityError as error:
        _raise_integrity_conflict(error)
    return Response(status_code=204)