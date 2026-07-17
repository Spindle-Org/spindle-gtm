"""Apollo account sync — recorded sanitized fixtures only, no live Apollo."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlmodel import Session, select

from spindle_gtm.models import Account, SyncStatus
from spindle_gtm.sync import (
    AccountRecord,
    ApolloApiAccountSource,
    CsvAccountSource,
    FixtureAccountSource,
    SyncScope,
    apply_sync,
    compute_diff,
    plan_sync,
    redact_mapping,
    redact_text,
    with_retries,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _scope() -> SyncScope:
    return SyncScope(mode="A", scope_type="list", scope_value="Q3 Fashion", workspace="ws-1")


def _src(records: list[AccountRecord]) -> FixtureAccountSource:
    return FixtureAccountSource(records=records, scope=_scope())


def _rec(apollo_id: str, name: str, **kw: object) -> AccountRecord:
    return AccountRecord(apollo_account_id=apollo_id, name=name, **kw)  # type: ignore[arg-type]


# --- redaction + retry ---------------------------------------------------------
def test_redaction() -> None:
    assert redact_text("mail me at ada@example.com now") == "mail me at <redacted-email> now"
    red = redact_mapping({"email": "x@example.com", "name": "Acme", "first_name": "Ada"})
    assert (
        red["email"] == "<redacted>" and red["first_name"] == "<redacted>" and red["name"] == "Acme"
    )


def test_with_retries_recovers() -> None:
    calls = {"n": 0}

    def flaky() -> str:
        calls["n"] += 1
        if calls["n"] < 3:
            raise OSError("transient")
        return "ok"

    assert with_retries(flaky, attempts=3) == "ok"


def test_with_retries_exhausts() -> None:
    with pytest.raises(OSError):
        with_retries(lambda: (_ for _ in ()).throw(OSError("always")), attempts=2)


# --- sources -------------------------------------------------------------------
def test_csv_source_parses_export() -> None:
    src = CsvAccountSource(FIXTURES / "apollo_accounts_export.csv", _scope())
    records = list(src.fetch())
    assert [r.apollo_account_id for r in records] == ["acc_1001", "acc_1002", "acc_1003"]
    assert records[0].headcount == 180 and records[0].domain == "meridian.example.com"


def test_api_source_paginates_and_checkpoints() -> None:
    pages = {
        1: json.loads((FIXTURES / "apollo_accounts_api_page1.json").read_text()),
        2: json.loads((FIXTURES / "apollo_accounts_api_page2.json").read_text()),
    }
    checkpoint: dict[str, int] = {}
    src = ApolloApiAccountSource(
        fetch_page=lambda p: pages[p], scope=_scope(), checkpoint=checkpoint
    )
    records = list(src.fetch())
    assert [r.apollo_account_id for r in records] == ["acc_1001", "acc_1002", "acc_1003"]
    assert checkpoint["Q3 Fashion"] == 2  # checkpoint advanced to last page


# --- diff + apply --------------------------------------------------------------
def test_plan_and_apply_creates_accounts(session: Session) -> None:
    src = _src([_rec("acc_1", "Meridian", domain="m.example.com"), _rec("acc_2", "Coastline")])
    diff, manifest = plan_sync(session, src)
    assert len(diff.added) == 2 and manifest.id is not None
    run = apply_sync(session, src, manifest.id)
    session.commit()
    assert run.status == SyncStatus.SUCCESS and run.scope_value == "Q3 Fashion"
    got = {a.apollo_id for a in session.exec(select(Account))}
    assert got == {"acc_1", "acc_2"}


def test_removed_account_is_inactivated_not_deleted(session: Session) -> None:
    full = _src([_rec("acc_1", "A"), _rec("acc_2", "B")])
    _, m1 = plan_sync(session, full)
    apply_sync(session, full, m1.id)  # type: ignore[arg-type]
    session.commit()

    subset = _src([_rec("acc_1", "A")])  # acc_2 no longer returned
    _, m2 = plan_sync(session, subset)
    apply_sync(session, subset, m2.id)  # type: ignore[arg-type]
    session.commit()

    accounts = {a.apollo_id: a for a in session.exec(select(Account))}
    assert set(accounts) == {"acc_1", "acc_2"}  # acc_2 still present
    assert accounts["acc_2"].active is False  # ...but inactive
    assert accounts["acc_1"].active is True


def test_sync_preserves_human_overrides(session: Session) -> None:
    src1 = _src([_rec("acc_1", "Meridian")])
    _, m1 = plan_sync(session, src1)
    apply_sync(session, src1, m1.id)  # type: ignore[arg-type]
    session.commit()

    acct = session.exec(select(Account).where(Account.apollo_id == "acc_1")).one()
    acct.qualification_override = "disqualified"
    acct.notes = "spoke to founder; not a fit this year"
    session.commit()

    src2 = _src([_rec("acc_1", "Meridian Inc.")])  # name changed upstream
    _, m2 = plan_sync(session, src2)
    apply_sync(session, src2, m2.id)  # type: ignore[arg-type]
    session.commit()

    refreshed = session.exec(select(Account).where(Account.apollo_id == "acc_1")).one()
    assert refreshed.name == "Meridian Inc."  # sourced field updated
    assert refreshed.qualification_override == "disqualified"  # human override preserved
    assert (refreshed.notes or "").startswith("spoke to founder")  # human note preserved


def test_apply_rejects_stale_manifest(session: Session) -> None:
    planned = _src([_rec("acc_1", "A"), _rec("acc_2", "B")])
    _, manifest = plan_sync(session, planned)
    session.commit()
    changed = _src([_rec("acc_1", "A")])  # data changed since planning
    with pytest.raises(ValueError, match="manifest invalidated"):
        apply_sync(session, changed, manifest.id)  # type: ignore[arg-type]


def test_updated_field_detected(session: Session) -> None:
    src1 = _src([_rec("acc_1", "Meridian", industry="Apparel")])
    _, m1 = plan_sync(session, src1)
    apply_sync(session, src1, m1.id)  # type: ignore[arg-type]
    session.commit()
    src2 = _src([_rec("acc_1", "Meridian", industry="Footwear")])
    diff = compute_diff(session, list(src2.fetch()), src2.scope)
    assert len(diff.updated) == 1
    _existing, _record, changed = diff.updated[0]
    assert changed == {"industry": "Footwear"}
