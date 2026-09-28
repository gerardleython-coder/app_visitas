from uuid import uuid4

import pytest

from app.application.brother_access import (
    AdminStrategy,
    BrotherScope,
    LiderStrategy,
    PastorStrategy,
    strategy_for,
)
from app.domain.authentication import UserAccount, UserRole
from app.domain.brother import BrotherProfile
from app.domain.errors import ForbiddenException
from app.domain.operator import OperatorProfile


def actor(role: UserRole, actor_id=None) -> UserAccount:
    return UserAccount(
        id=actor_id or uuid4(),
        email=f"{uuid4().hex}@example.test",
        password_hash="test-only-hash",
        role=role,
        active=True,
    )


def operator(role: UserRole, church_id, district_id) -> OperatorProfile:
    return OperatorProfile(
        id=uuid4(),
        name="Test",
        surname=role.value,
        email=f"{uuid4().hex}@example.test",
        role=role,
        active=True,
        district_id=district_id,
        church_id=church_id,
    )


def brother(church_id, district_id, leader_id) -> BrotherProfile:
    return BrotherProfile(
        id=uuid4(),
        name="Test",
        surname="Brother",
        phone="3000000000",
        address="Address",
        district_id=district_id,
        church_id=church_id,
        leader_id=leader_id,
        active=True,
    )


def test_admin_strategy_has_global_scope_and_keeps_requested_leader() -> None:
    admin = actor(UserRole.ADMIN)
    leader_id = uuid4()
    strategy = AdminStrategy()

    assert strategy.scope(admin, None) == BrotherScope()
    assert strategy.assignment_leader_id(
        admin,
        None,
        district_id=uuid4(),
        church_id=uuid4(),
        requested_leader_id=leader_id,
    ) == leader_id
    strategy.authorize_reassignment(admin, None)


def test_pastor_strategy_scopes_and_assigns_only_in_own_church() -> None:
    district_id = uuid4()
    church_id = uuid4()
    pastor = operator(UserRole.PASTOR, church_id, district_id)
    account = actor(UserRole.PASTOR, pastor.id)
    leader_id = uuid4()
    strategy = PastorStrategy()

    assert strategy.scope(account, pastor) == BrotherScope(church_id=church_id)
    assert strategy.assignment_leader_id(
        account,
        pastor,
        district_id=district_id,
        church_id=church_id,
        requested_leader_id=leader_id,
    ) == leader_id
    assert strategy.can_access(account, pastor, brother(church_id, district_id, leader_id))
    assert not strategy.can_access(
        account,
        pastor,
        brother(uuid4(), district_id, leader_id),
    )
    with pytest.raises(ForbiddenException):
        strategy.assignment_leader_id(
            account,
            pastor,
            district_id=district_id,
            church_id=uuid4(),
            requested_leader_id=leader_id,
        )


def test_leader_strategy_forces_self_assignment_and_denies_reassignment() -> None:
    district_id = uuid4()
    church_id = uuid4()
    leader = operator(UserRole.LIDER, church_id, district_id)
    account = actor(UserRole.LIDER, leader.id)
    strategy = LiderStrategy()

    assert strategy.scope(account, leader) == BrotherScope(leader_id=leader.id)
    assert strategy.assignment_leader_id(
        account,
        leader,
        district_id=district_id,
        church_id=church_id,
        requested_leader_id=None,
    ) == leader.id
    assert strategy.can_access(account, leader, brother(church_id, district_id, leader.id))
    assert not strategy.can_access(account, leader, brother(church_id, district_id, uuid4()))
    with pytest.raises(ForbiddenException):
        strategy.assignment_leader_id(
            account,
            leader,
            district_id=district_id,
            church_id=church_id,
            requested_leader_id=uuid4(),
        )
    with pytest.raises(ForbiddenException):
        strategy.authorize_reassignment(account, leader)


@pytest.mark.parametrize(
    ("role", "strategy_type"),
    [
        (UserRole.ADMIN, AdminStrategy),
        (UserRole.PASTOR, PastorStrategy),
        (UserRole.LIDER, LiderStrategy),
    ],
)
def test_strategy_factory_selects_by_role(role: UserRole, strategy_type: type) -> None:
    assert isinstance(strategy_for(role), strategy_type)