from uuid import UUID

from app.domain.authentication import UserRole
from app.domain.brother import BrotherProfile
from app.infrastructure.models import UserModel


class BrotherFactory:
    @staticmethod
    def create_model(
        *,
        name: str,
        surname: str,
        phone: str,
        address: str,
        district_id: UUID,
        church_id: UUID,
        leader_id: UUID,
    ) -> UserModel:
        return UserModel(
            name=name,
            surname=surname,
            phone=phone,
            address=address,
            district_id=district_id,
            church_id=church_id,
            leader_id=leader_id,
            email=None,
            password_hash=None,
            role=UserRole.HERMANO,
            active=True,
        )

    @staticmethod
    def from_model(model: UserModel) -> BrotherProfile:
        if (
            model.district_id is None
            or model.church_id is None
            or model.leader_id is None
            or model.phone is None
            or model.address is None
        ):
            raise RuntimeError("El registro HERMANO no cumple sus datos obligatorios")
        if model.role is not UserRole.HERMANO:
            raise RuntimeError("El registro persistido no tiene rol HERMANO")
        return BrotherProfile(
            id=model.id,
            name=model.name,
            surname=model.surname,
            phone=model.phone,
            address=model.address,
            district_id=model.district_id,
            church_id=model.church_id,
            leader_id=model.leader_id,
            active=model.active,
        )