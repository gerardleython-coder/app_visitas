from typing import Protocol
from uuid import UUID

from app.application.audit import AuditRepository
from app.domain.audit import AuditRecord
from app.domain.authentication import UserAccount, UserRole
from app.domain.errors import ConflictException, DomainException, ForbiddenException, NotFoundException
from app.domain.organization import Church, District


class TerritoryRepository(Protocol):
    async def list_districts(self) -> list[District]: ...

    async def get_district(self, district_id: UUID) -> District | None: ...

    async def create_district(self, name: str) -> District: ...

    async def update_district(
        self,
        district_id: UUID,
        changes: dict[str, object],
    ) -> District | None: ...

    async def district_has_churches(self, district_id: UUID) -> bool: ...

    async def delete_district(self, district_id: UUID) -> bool: ...

    async def list_churches(self, district_id: UUID | None = None) -> list[Church]: ...

    async def get_church(self, church_id: UUID) -> Church | None: ...

    async def create_church(
        self,
        *,
        district_id: UUID,
        name: str,
        address: str | None,
    ) -> Church: ...

    async def update_church(
        self,
        church_id: UUID,
        changes: dict[str, object],
    ) -> Church | None: ...

    async def church_has_active_users(self, church_id: UUID) -> bool: ...

    async def deactivate_church(self, church_id: UUID) -> Church | None: ...


class ManageTerritories:
    _editable_district_fields = frozenset({"name"})
    _editable_church_fields = frozenset({"name", "address"})

    def __init__(self, territories: TerritoryRepository, audit: AuditRepository) -> None:
        self._territories = territories
        self._audit = audit

    async def list_districts(self, actor: UserAccount) -> list[District]:
        self._require_admin(actor)
        return await self._territories.list_districts()

    async def create_district(self, actor: UserAccount, name: str) -> District:
        self._require_admin(actor)
        normalized_name = self._required_text(name, "El nombre del distrito es obligatorio")
        district = await self._territories.create_district(normalized_name)
        await self._audit.record_event(
            AuditRecord(
                actor_id=actor.id,
                resource="DISTRITO",
                resource_id=district.id,
                action="CREADO",
                church_id=None,
                new_values={"name": district.name},
            )
        )
        return district

    async def update_district(
        self,
        actor: UserAccount,
        district_id: UUID,
        changes: dict[str, object],
    ) -> District:
        self._require_admin(actor)
        if not changes or not changes.keys() <= self._editable_district_fields:
            raise DomainException("Los datos editables del distrito no son válidos")
        district = await self._territories.get_district(district_id)
        if district is None:
            raise NotFoundException("Distrito no encontrado")
        normalized_changes = dict(changes)
        if "name" in normalized_changes:
            value = normalized_changes["name"]
            if not isinstance(value, str):
                raise DomainException("El nombre del distrito no es válido")
            normalized_changes["name"] = self._required_text(
                value,
                "El nombre del distrito es obligatorio",
            )
        updated = await self._territories.update_district(district_id, normalized_changes)
        if updated is None:
            raise NotFoundException("Distrito no encontrado")
        await self._audit.record_event(
            AuditRecord(
                actor_id=actor.id,
                resource="DISTRITO",
                resource_id=updated.id,
                action="MODIFICADO",
                church_id=None,
                previous_values={"name": district.name},
                new_values={"name": updated.name},
            )
        )
        return updated

    async def delete_district(self, actor: UserAccount, district_id: UUID) -> None:
        self._require_admin(actor)
        district = await self._territories.get_district(district_id)
        if district is None:
            raise NotFoundException("Distrito no encontrado")
        if await self._territories.district_has_churches(district_id):
            raise ConflictException("No se puede eliminar un distrito con iglesias asociadas")
        if not await self._territories.delete_district(district_id):
            raise NotFoundException("Distrito no encontrado")
        await self._audit.record_event(
            AuditRecord(
                actor_id=actor.id,
                resource="DISTRITO",
                resource_id=district.id,
                action="ELIMINADO",
                church_id=None,
                previous_values={"name": district.name},
            )
        )

    async def list_churches(
        self,
        actor: UserAccount,
        *,
        district_id: UUID | None = None,
    ) -> list[Church]:
        self._require_admin(actor)
        return await self._territories.list_churches(district_id)

    async def create_church(
        self,
        actor: UserAccount,
        *,
        district_id: UUID,
        name: str,
        address: str | None,
    ) -> Church:
        self._require_admin(actor)
        district = await self._territories.get_district(district_id)
        if district is None:
            raise NotFoundException("Distrito no encontrado")
        normalized_name = self._required_text(name, "El nombre de la iglesia es obligatorio")
        normalized_address = address.strip() or None if address is not None else None
        church = await self._territories.create_church(
            district_id=district_id,
            name=normalized_name,
            address=normalized_address,
        )
        await self._audit.record_event(
            AuditRecord(
                actor_id=actor.id,
                resource="IGLESIA",
                resource_id=church.id,
                action="CREADO",
                church_id=church.id,
                new_values=self._church_values(church),
            )
        )
        return church

    async def update_church(
        self,
        actor: UserAccount,
        church_id: UUID,
        changes: dict[str, object],
    ) -> Church:
        self._require_admin(actor)
        if not changes or not changes.keys() <= self._editable_church_fields:
            raise DomainException("Los datos editables de la iglesia no son válidos")
        church = await self._territories.get_church(church_id)
        if church is None:
            raise NotFoundException("Iglesia no encontrada")
        if not church.active:
            raise NotFoundException("Iglesia no encontrada")
        normalized_changes = dict(changes)
        if "name" in normalized_changes:
            value = normalized_changes["name"]
            if not isinstance(value, str):
                raise DomainException("El nombre de la iglesia no es válido")
            normalized_changes["name"] = self._required_text(
                value,
                "El nombre de la iglesia es obligatorio",
            )
        if "address" in normalized_changes:
            value = normalized_changes["address"]
            if value is not None and not isinstance(value, str):
                raise DomainException("La dirección de la iglesia no es válida")
            normalized_changes["address"] = value.strip() or None if isinstance(value, str) else None
        updated = await self._territories.update_church(church_id, normalized_changes)
        if updated is None:
            raise NotFoundException("Iglesia no encontrada")
        await self._audit.record_event(
            AuditRecord(
                actor_id=actor.id,
                resource="IGLESIA",
                resource_id=updated.id,
                action="MODIFICADO",
                church_id=updated.id,
                previous_values=self._church_values(church),
                new_values=self._church_values(updated),
            )
        )
        return updated

    async def delete_church(self, actor: UserAccount, church_id: UUID) -> Church:
        self._require_admin(actor)
        church = await self._territories.get_church(church_id)
        if church is None:
            raise NotFoundException("Iglesia no encontrada")
        if not church.active:
            return church
        if await self._territories.church_has_active_users(church_id):
            raise ConflictException("No se puede desactivar una iglesia con usuarios activos")
        deactivated = await self._territories.deactivate_church(church_id)
        if deactivated is None:
            raise NotFoundException("Iglesia no encontrada")
        await self._audit.record_event(
            AuditRecord(
                actor_id=actor.id,
                resource="IGLESIA",
                resource_id=deactivated.id,
                action="DESACTIVADO",
                church_id=deactivated.id,
                previous_values=self._church_values(church),
                new_values=self._church_values(deactivated),
            )
        )
        return deactivated

    @staticmethod
    def _require_admin(actor: UserAccount) -> None:
        if actor.role is not UserRole.ADMIN or not actor.active:
            raise ForbiddenException("Solo ADMIN puede gestionar distritos e iglesias")

    @staticmethod
    def _required_text(value: str, error_message: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise DomainException(error_message)
        return normalized

    @staticmethod
    def _church_values(church: Church) -> dict[str, object]:
        return {
            "district_id": str(church.district_id),
            "name": church.name,
            "address": church.address,
            "active": church.active,
        }