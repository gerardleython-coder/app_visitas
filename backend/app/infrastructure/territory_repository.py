from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.organization import Church, District
from app.infrastructure.models import ChurchModel, DistrictModel, UserModel


class SQLAlchemyTerritoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_districts(self) -> list[District]:
        result = await self._session.scalars(
            select(DistrictModel).order_by(DistrictModel.name, DistrictModel.id)
        )
        return [self._to_district(model) for model in result.all()]

    async def get_district(self, district_id: UUID) -> District | None:
        model = await self._session.get(DistrictModel, district_id)
        return self._to_district(model) if model is not None else None

    async def create_district(self, name: str) -> District:
        model = DistrictModel(name=name)
        self._session.add(model)
        await self._session.flush()
        return self._to_district(model)

    async def update_district(
        self,
        district_id: UUID,
        changes: dict[str, object],
    ) -> District | None:
        model = await self._session.get(DistrictModel, district_id)
        if model is None:
            return None
        model.name = str(changes["name"])
        await self._session.flush()
        return self._to_district(model)

    async def district_has_churches(self, district_id: UUID) -> bool:
        church_id = await self._session.scalar(
            select(ChurchModel.id).where(ChurchModel.district_id == district_id).limit(1)
        )
        return church_id is not None

    async def delete_district(self, district_id: UUID) -> bool:
        model = await self._session.get(DistrictModel, district_id)
        if model is None:
            return False
        await self._session.delete(model)
        await self._session.flush()
        return True

    async def list_churches(self, district_id: UUID | None = None) -> list[Church]:
        statement = select(ChurchModel)
        if district_id is not None:
            statement = statement.where(ChurchModel.district_id == district_id)
        result = await self._session.scalars(
            statement.order_by(ChurchModel.name, ChurchModel.id)
        )
        return [self._to_church(model) for model in result.all()]

    async def get_church(self, church_id: UUID) -> Church | None:
        model = await self._session.get(ChurchModel, church_id)
        return self._to_church(model) if model is not None else None

    async def create_church(
        self,
        *,
        district_id: UUID,
        name: str,
        address: str | None,
    ) -> Church:
        model = ChurchModel(district_id=district_id, name=name, address=address)
        self._session.add(model)
        await self._session.flush()
        return self._to_church(model)

    async def update_church(
        self,
        church_id: UUID,
        changes: dict[str, object],
    ) -> Church | None:
        model = await self._session.get(ChurchModel, church_id)
        if model is None:
            return None
        if "name" in changes:
            model.name = str(changes["name"])
        if "address" in changes:
            address = changes["address"]
            model.address = address if isinstance(address, str) or address is None else None
        await self._session.flush()
        return self._to_church(model)

    async def church_has_active_users(self, church_id: UUID) -> bool:
        user_id = await self._session.scalar(
            select(UserModel.id)
            .where(UserModel.church_id == church_id, UserModel.active.is_(True))
            .limit(1)
        )
        return user_id is not None

    async def deactivate_church(self, church_id: UUID) -> Church | None:
        model = await self._session.get(ChurchModel, church_id)
        if model is None:
            return None
        model.active = False
        await self._session.flush()
        return self._to_church(model)

    @staticmethod
    def _to_district(model: DistrictModel) -> District:
        return District(id=model.id, name=model.name)

    @staticmethod
    def _to_church(model: ChurchModel) -> Church:
        return Church(
            id=model.id,
            district_id=model.district_id,
            active=model.active,
            name=model.name,
            address=model.address,
        )