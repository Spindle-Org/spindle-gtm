"""DB-backed domain rules: locks block outbound, suppression double-gate, note preservation."""

from __future__ import annotations

import pytest
from sqlmodel import Session

from spindle_gtm.domain import (
    SuppressionError,
    account_outbound_blocked,
    draft_send_ready,
    guard_before_apply,
    is_suppressed,
    upsert_account,
)
from spindle_gtm.models import (
    Account,
    AccountLock,
    AccountLockState,
    Contact,
    DraftStatus,
    EmailDraft,
    SuppressionEntry,
)


def test_lock_blocks_outbound(session: Session, account: Account) -> None:
    assert account.id is not None
    assert not account_outbound_blocked(session, account.id)  # no lock yet
    session.add(AccountLock(account_id=account.id, state=AccountLockState.REPLIED))
    session.commit()
    assert account_outbound_blocked(session, account.id)


def test_open_lock_does_not_block(session: Session, account: Account) -> None:
    assert account.id is not None
    session.add(AccountLock(account_id=account.id, state=AccountLockState.OPEN))
    session.commit()
    assert not account_outbound_blocked(session, account.id)


def test_suppression_by_email_and_domain(session: Session) -> None:
    session.add(SuppressionEntry(email="blocked@example.com", scope="email", reason="unsub"))
    session.add(SuppressionEntry(domain="example.net", scope="domain", reason="complaint"))
    session.commit()
    assert is_suppressed(session, email="blocked@example.com")
    assert is_suppressed(session, email="anyone@example.net")  # domain-scoped
    assert not is_suppressed(session, email="ok@example.org")


def test_draft_gate1_holds_suppressed_and_readies_clean(
    session: Session, account: Account, contact: Contact
) -> None:
    assert account.id is not None and contact.id is not None
    clean = EmailDraft(account_id=account.id, contact_id=contact.id, subject="hi")
    assert draft_send_ready(session, clean) == DraftStatus.SEND_READY
    assert clean.send_ready_at is not None

    session.add(SuppressionEntry(email=contact.email, scope="email", reason="unsub"))
    session.commit()
    held = EmailDraft(account_id=account.id, contact_id=contact.id, subject="hi again")
    assert draft_send_ready(session, held) == DraftStatus.HELD


def test_gate2_apply_guard_raises_when_suppressed(
    session: Session, account: Account, contact: Contact
) -> None:
    assert account.id is not None and contact.id is not None
    draft = EmailDraft(account_id=account.id, contact_id=contact.id)
    guard_before_apply(session, draft)  # clean: no raise

    session.add(SuppressionEntry(email=contact.email, scope="email", reason="added late"))
    session.commit()
    with pytest.raises(SuppressionError):
        guard_before_apply(session, draft)


def test_sync_preserves_human_notes(session: Session) -> None:
    created = upsert_account(session, {"apollo_id": "A1", "name": "Acme", "domain": "acme.example"})
    session.commit()
    created.notes = "Met the CTO at a conference — warm."  # human note
    session.commit()

    # Re-sync from Apollo with a changed name and NO notes field.
    updated = upsert_account(
        session, {"apollo_id": "A1", "name": "Acme Inc.", "domain": "acme.example"}
    )
    session.commit()
    assert updated.id == created.id
    assert updated.name == "Acme Inc."  # sourced field updated
    assert updated.notes == "Met the CTO at a conference — warm."  # human note preserved


def test_sync_does_not_clobber_notes_even_if_incoming_has_them(session: Session) -> None:
    created = upsert_account(session, {"apollo_id": "A2", "name": "Beta"})
    session.commit()
    created.notes = "human note"
    session.commit()
    upsert_account(session, {"apollo_id": "A2", "name": "Beta", "notes": "apollo-provided"})
    session.commit()
    assert created.notes == "human note"  # incoming notes ignored
