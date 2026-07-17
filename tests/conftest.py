"""Shared test fixtures. In-memory SQLite with the full schema; synthetic data only."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from spindle_gtm.models import Account, Contact


@pytest.fixture
def session() -> Iterator[Session]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture
def account(session: Session) -> Account:
    acct = Account(apollo_id="synthetic-acct-1", name="Acme Robotics", domain="example.com")
    session.add(acct)
    session.commit()
    session.refresh(acct)
    return acct


@pytest.fixture
def contact(session: Session, account: Account) -> Contact:
    assert account.id is not None
    c = Contact(account_id=account.id, apollo_id="synthetic-c-1", email="ada@example.com")
    session.add(c)
    session.commit()
    session.refresh(c)
    return c
