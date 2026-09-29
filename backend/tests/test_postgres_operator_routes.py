import asyncio
import os
from secrets import token_urlsafe
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.domain.authentication import UserRole
from app.infrastructure.database import create_database_engine
from app.infrastructure.models import (
    AuditModel,
    ChurchModel,
    DistrictModel,
    RefreshSessionModel,
    UserModel,
)
from app.infrastructure.password_service import Argon2PasswordService
from app.main import app


pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_POSTGRES_INTEGRATION") != "1",
    reason="Set RUN_POSTGRES_INTEGRATION=1 to run against configured PostgreSQL",
)


def test_admin_operator_routes_persist_assignment_and_enforce_role_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret_key = token_urlsafe(48)
    monkeypatch.setenv("SECRET_KEY", secret_key)
    email_prefix = f"operator-route-{uuid4().hex}"
    admin_email = f"{email_prefix}-admin@example.invalid"
    pastor_email = f"{email_prefix}-pastor@example.invalid"
    replacement_pastor_email = f"{email_prefix}-replacement-pastor@example.invalid"
    leader_email = f"{email_prefix}-leader@example.invalid"
    other_church_leader_email = f"{email_prefix}-other-leader@example.invalid"
    admin_password = token_urlsafe(24)
    pastor_password = token_urlsafe(24)
    replacement_pastor_password = token_urlsafe(24)
    leader_password = token_urlsafe(24)
    district_id = uuid4()
    church_id = uuid4()
    other_church_id = uuid4()
    wrong_district_id = uuid4()

    async def create_test_territory_and_admin() -> None:
        engine = create_database_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                async with session.begin():
                    session.add(DistrictModel(id=district_id, name=email_prefix))
                    await session.flush()
                    session.add(
                        ChurchModel(
                            id=church_id,
                            district_id=district_id,
                            name=f"{email_prefix}-main",
                        )
                    )
                    await session.flush()
                    session.add(
                        ChurchModel(
                            id=other_church_id,
                            district_id=district_id,
                            name=f"{email_prefix}-other",
                        )
                    )
                    await session.flush()
                    session.add(
                        UserModel(
                            name="Integration",
                            surname="Admin",
                            email=admin_email,
                            password_hash=Argon2PasswordService().hash(admin_password),
                            role=UserRole.ADMIN,
                            active=True,
                        )
                    )
        finally:
            await engine.dispose()

    async def get_created_operators() -> list[UserModel]:
        engine = create_database_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                result = await session.scalars(
                    select(UserModel).where(
                        UserModel.email.in_(
                            [
                                pastor_email,
                                replacement_pastor_email,
                                leader_email,
                                other_church_leader_email,
                            ]
                        )
                    )
                )
                return list(result.all())
        finally:
            await engine.dispose()

    async def remove_test_data() -> None:
        engine = create_database_engine()
        try:
            async with engine.begin() as connection:
                user_ids = select(UserModel.id).where(
                    UserModel.email.like(f"{email_prefix}%")
                )
                await connection.execute(
                    text("ALTER TABLE auditoria DISABLE TRIGGER trg_proteger_auditoria")
                )
                await connection.execute(
                    delete(AuditModel).where(
                        AuditModel.actor_id.in_(user_ids)
                        | AuditModel.resource_id.in_(user_ids)
                    )
                )
                await connection.execute(
                    text("ALTER TABLE auditoria ENABLE TRIGGER trg_proteger_auditoria")
                )
                await connection.execute(
                    delete(RefreshSessionModel).where(
                        RefreshSessionModel.user_id.in_(user_ids)
                    )
                )
                await connection.execute(
                    delete(UserModel).where(UserModel.email.like(f"{email_prefix}%"))
                )
                await connection.execute(
                    delete(ChurchModel).where(ChurchModel.name.like(f"{email_prefix}%"))
                )
                await connection.execute(
                    delete(DistrictModel).where(DistrictModel.id == district_id)
                )
        finally:
            await engine.dispose()

    asyncio.run(create_test_territory_and_admin())
    try:
        with TestClient(app) as client:
            admin_login = client.post(
                "/api/v1/auth/login",
                json={"email": admin_email, "password": admin_password},
            )
            assert admin_login.status_code == 200
            admin_headers = {
                "Authorization": f"Bearer {admin_login.json()['access_token']}"
            }
            admin_identity = client.get("/api/v1/auth/me", headers=admin_headers)
            assert admin_identity.status_code == 200

            role_escalation_response = client.post(
                "/api/v1/users/pastores",
                headers=admin_headers,
                json={
                    "name": "Integration",
                    "surname": "Pastor",
                    "email": pastor_email,
                    "password": pastor_password,
                    "district_id": str(district_id),
                    "church_id": str(church_id),
                    "role": UserRole.ADMIN.value,
                },
            )
            assert role_escalation_response.status_code == 422

            pastor_response = client.post(
                "/api/v1/users/pastores",
                headers=admin_headers,
                json={
                    "name": "Integration",
                    "surname": "Pastor",
                    "email": pastor_email,
                    "password": pastor_password,
                    "district_id": str(district_id),
                    "church_id": str(church_id),
                },
            )
            assert pastor_response.status_code == 201
            assert pastor_response.json()["role"] == UserRole.PASTOR.value

            pastor_login = client.post(
                "/api/v1/auth/login",
                json={"email": pastor_email, "password": pastor_password},
            )
            assert pastor_login.status_code == 200
            pastor_headers = {
                "Authorization": f"Bearer {pastor_login.json()['access_token']}"
            }
            forbidden_response = client.post(
                "/api/v1/users/lideres",
                headers=pastor_headers,
                json={
                    "name": "Integration",
                    "surname": "Forbidden",
                    "email": f"{email_prefix}-forbidden@example.invalid",
                    "password": token_urlsafe(24),
                    "district_id": str(district_id),
                    "church_id": str(church_id),
                },
            )
            assert forbidden_response.status_code == 403

            leader_response = client.post(
                "/api/v1/users/lideres",
                headers=admin_headers,
                json={
                    "name": "Integration",
                    "surname": "Leader",
                    "email": leader_email,
                    "password": leader_password,
                    "district_id": str(district_id),
                    "church_id": str(church_id),
                },
            )
            assert leader_response.status_code == 201
            assert leader_response.json()["role"] == UserRole.LIDER.value

            mismatch_response = client.post(
                "/api/v1/users/lideres",
                headers=admin_headers,
                json={
                    "name": "Integration",
                    "surname": "Mismatch",
                    "email": f"{email_prefix}-mismatch@example.invalid",
                    "password": token_urlsafe(24),
                    "district_id": str(wrong_district_id),
                    "church_id": str(church_id),
                },
            )
            assert mismatch_response.status_code == 422

            duplicate_response = client.post(
                "/api/v1/users/lideres",
                headers=admin_headers,
                json={
                    "name": "Integration",
                    "surname": "Duplicate",
                    "email": pastor_email,
                    "password": token_urlsafe(24),
                    "district_id": str(district_id),
                    "church_id": str(church_id),
                },
            )
            assert duplicate_response.status_code == 409

            other_church_leader_response = client.post(
                "/api/v1/users/lideres",
                headers=admin_headers,
                json={
                    "name": "Integration",
                    "surname": "Other Church",
                    "email": other_church_leader_email,
                    "password": token_urlsafe(24),
                    "district_id": str(district_id),
                    "church_id": str(other_church_id),
                },
            )
            assert other_church_leader_response.status_code == 201

            primary_response = client.patch(
                f"/api/v1/admin/iglesias/{church_id}/pastor-principal",
                headers=admin_headers,
                json={"pastor_id": pastor_response.json()["id"]},
            )
            assert primary_response.status_code == 200
            assert primary_response.json()["is_primary_pastor"] is True

            pastors_response = client.get("/api/v1/users/pastores", headers=admin_headers)
            assert pastors_response.status_code == 200
            assert any(
                pastor["id"] == pastor_response.json()["id"]
                and pastor["is_primary_pastor"]
                for pastor in pastors_response.json()
            )

            cannot_remove_sole_primary = client.delete(
                f"/api/v1/users/pastores/{pastor_response.json()['id']}",
                headers=admin_headers,
            )
            assert cannot_remove_sole_primary.status_code == 409

            replacement_pastor_response = client.post(
                "/api/v1/users/pastores",
                headers=admin_headers,
                json={
                    "name": "Integration",
                    "surname": "Replacement",
                    "email": replacement_pastor_email,
                    "password": replacement_pastor_password,
                    "district_id": str(district_id),
                    "church_id": str(church_id),
                },
            )
            assert replacement_pastor_response.status_code == 201

            replacement_response = client.patch(
                f"/api/v1/admin/iglesias/{church_id}/pastor-principal",
                headers=admin_headers,
                json={"pastor_id": replacement_pastor_response.json()["id"]},
            )
            assert replacement_response.status_code == 200
            assert replacement_response.json()["is_primary_pastor"] is True

            removed_pastor_response = client.delete(
                f"/api/v1/users/pastores/{pastor_response.json()['id']}",
                headers=admin_headers,
            )
            assert removed_pastor_response.status_code == 204
            assert client.post(
                "/api/v1/auth/login",
                json={"email": pastor_email, "password": pastor_password},
            ).status_code == 401

            patch_pastor_response = client.patch(
                f"/api/v1/users/pastores/{replacement_pastor_response.json()['id']}",
                headers=admin_headers,
                json={"name": "Updated Pastor"},
            )
            assert patch_pastor_response.status_code == 200
            assert patch_pastor_response.json()["name"] == "Updated Pastor"

            replacement_login = client.post(
                "/api/v1/auth/login",
                json={"email": replacement_pastor_email, "password": replacement_pastor_password},
            )
            assert replacement_login.status_code == 200
            pastor_headers = {
                "Authorization": f"Bearer {replacement_login.json()['access_token']}"
            }
            pastor_leaders = client.get("/api/v1/users/lideres", headers=pastor_headers)
            assert pastor_leaders.status_code == 200
            assert {leader["id"] for leader in pastor_leaders.json()} == {
                leader_response.json()["id"]
            }
            assert client.get("/api/v1/users/pastores", headers=pastor_headers).status_code == 403

            patch_leader_response = client.patch(
                f"/api/v1/users/lideres/{leader_response.json()['id']}",
                headers=pastor_headers,
                json={"surname": "Updated Leader", "phone": "3001234567"},
            )
            assert patch_leader_response.status_code == 200
            assert patch_leader_response.json()["surname"] == "Updated Leader"
            assert patch_leader_response.json()["phone"] == "3001234567"

            foreign_leader_id = other_church_leader_response.json()["id"]
            assert client.patch(
                f"/api/v1/users/lideres/{foreign_leader_id}",
                headers=pastor_headers,
                json={"surname": "Out of Scope"},
            ).status_code == 404
            assert client.delete(
                f"/api/v1/users/lideres/{foreign_leader_id}",
                headers=pastor_headers,
            ).status_code == 403
            assert client.patch(
                f"/api/v1/users/lideres/{leader_response.json()['id']}",
                headers=pastor_headers,
                json={"role": UserRole.ADMIN.value},
            ).status_code == 422

            pastor_deactivation = client.delete(
                f"/api/v1/users/lideres/{leader_response.json()['id']}",
                headers=pastor_headers,
            )
            assert pastor_deactivation.status_code == 403
            deactivated_leader = client.delete(
                f"/api/v1/users/lideres/{leader_response.json()['id']}",
                headers=admin_headers,
            )
            assert deactivated_leader.status_code == 204
            assert client.post(
                "/api/v1/auth/login",
                json={"email": leader_email, "password": leader_password},
            ).status_code == 401

            audit_response = client.get("/api/v1/audit", headers=admin_headers)
            assert audit_response.status_code == 200
            leader_events = [
                event
                for event in audit_response.json()
                if event["resource_id"] == leader_response.json()["id"]
            ]
            deactivation_event = next(
                event for event in leader_events if event["action"] == "DESACTIVADO"
            )
            assert {event["action"] for event in leader_events} >= {"CREADO", "DESACTIVADO"}
            assert deactivation_event["actor_id"] == admin_identity.json()["id"]
            assert deactivation_event["previous_values"]["active"] is True
            assert deactivation_event["new_values"]["active"] is False

        operators = asyncio.run(get_created_operators())
        assert {operator.email for operator in operators} == {
            pastor_email,
            replacement_pastor_email,
            leader_email,
            other_church_leader_email,
        }
        assert all(operator.district_id == district_id for operator in operators)
        operators_by_email = {operator.email: operator for operator in operators}
        assert operators_by_email[pastor_email].church_id == church_id
        assert operators_by_email[pastor_email].active is False
        assert operators_by_email[replacement_pastor_email].church_id == church_id
        assert operators_by_email[replacement_pastor_email].active is True
        assert operators_by_email[replacement_pastor_email].is_primary_pastor is True
        assert operators_by_email[leader_email].church_id == church_id
        assert operators_by_email[leader_email].active is False
        assert operators_by_email[other_church_leader_email].church_id == other_church_id
        assert operators_by_email[other_church_leader_email].active is True
        assert all(operator.password_hash for operator in operators)
        assert all(
            operator.password_hash not in {pastor_password, leader_password}
            for operator in operators
        )
    finally:
        asyncio.run(remove_test_data())


def test_postgresql_rejects_direct_deactivation_of_sole_primary_pastor() -> None:
    church_name = f"primary-guard-{uuid4().hex}"
    district_id = uuid4()
    church_id = uuid4()
    pastor_id = uuid4()

    async def create_primary_pastor() -> None:
        engine = create_database_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                async with session.begin():
                    session.add(DistrictModel(id=district_id, name=church_name))
                    await session.flush()
                    session.add(
                        ChurchModel(
                            id=church_id,
                            district_id=district_id,
                            name=church_name,
                        )
                    )
                    await session.flush()
                    session.add(
                        UserModel(
                            id=pastor_id,
                            district_id=district_id,
                            church_id=church_id,
                            name="Primary",
                            surname="Pastor",
                            email=f"{church_name}@example.invalid",
                            password_hash="test-only-hash",
                            role=UserRole.PASTOR,
                            active=True,
                            is_primary_pastor=True,
                        )
                    )
        finally:
            await engine.dispose()

    async def deactivate_primary_pastor() -> None:
        engine = create_database_engine()
        try:
            session_factory = async_sessionmaker(engine, expire_on_commit=False)
            async with session_factory() as session:
                async with session.begin():
                    pastor = await session.get(UserModel, pastor_id)
                    assert pastor is not None
                    pastor.active = False
                    pastor.is_primary_pastor = False
                    await session.flush()
        finally:
            await engine.dispose()

    async def remove_primary_pastor() -> None:
        engine = create_database_engine()
        try:
            async with engine.begin() as connection:
                await connection.execute(delete(UserModel).where(UserModel.id == pastor_id))
                await connection.execute(delete(ChurchModel).where(ChurchModel.id == church_id))
                await connection.execute(
                    delete(DistrictModel).where(DistrictModel.id == district_id)
                )
        finally:
            await engine.dispose()

    asyncio.run(create_primary_pastor())
    try:
        with pytest.raises(IntegrityError):
            asyncio.run(deactivate_primary_pastor())
    finally:
        asyncio.run(remove_primary_pastor())