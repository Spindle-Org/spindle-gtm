"""Decision log persistence + pre-apply recheck against the DB."""

from __future__ import annotations

import json

from sqlmodel import Session, select

from spindle_gtm.gates import GateResult, log_decision, preapply_recheck
from spindle_gtm.models import (
    Account,
    AccountLock,
    AccountLockState,
    ComplianceDecision,
    Contact,
    EmailDraft,
    GateDecision,
    OutreachBatch,
    OutreachBatchItem,
    SuppressionEntry,
)


def _batch_with_item(session: Session, account: Account, contact: Contact) -> OutreachBatch:
    assert account.id is not None and contact.id is not None
    draft = EmailDraft(
        account_id=account.id, contact_id=contact.id, subject="s", body="b", status="APPROVED"
    )
    batch = OutreachBatch(name="b1")
    session.add(draft)
    session.add(batch)
    session.flush()
    assert draft.id is not None and batch.id is not None
    session.add(
        OutreachBatchItem(
            batch_id=batch.id, draft_id=draft.id, contact_id=contact.id, account_id=account.id
        )
    )
    session.commit()
    return batch


def test_log_decision_persists_reason_codes(session: Session, contact: Contact) -> None:
    result = GateResult(GateDecision.BLOCK, ["CASL_NO_CONSENT"])
    record = log_decision(session, result, contact_id=contact.id)
    session.commit()
    stored = session.get(ComplianceDecision, record.id)
    assert stored is not None and stored.decision == "BLOCK"
    assert json.loads(stored.reason_codes_json) == ["CASL_NO_CONSENT"]


def test_preapply_recheck_clean_batch_passes(
    session: Session, account: Account, contact: Contact
) -> None:
    batch = _batch_with_item(session, account, contact)
    assert batch.id is not None
    assert preapply_recheck(session, batch.id) == []


def test_preapply_recheck_catches_late_suppression(
    session: Session, account: Account, contact: Contact
) -> None:
    batch = _batch_with_item(session, account, contact)
    assert batch.id is not None
    session.add(SuppressionEntry(email=contact.email, scope="email", reason="late unsub"))
    session.commit()
    reasons = preapply_recheck(session, batch.id)
    assert any(r.startswith("SUPPRESSED_CONTACT_") for r in reasons)
    # ...and the block was logged with context pre_apply_recheck.
    logged = session.exec(
        select(ComplianceDecision).where(ComplianceDecision.batch_id == batch.id)
    ).one()
    assert logged.context == "pre_apply_recheck"


def test_preapply_recheck_catches_late_account_lock(
    session: Session, account: Account, contact: Contact
) -> None:
    batch = _batch_with_item(session, account, contact)
    assert batch.id is not None and account.id is not None
    session.add(AccountLock(account_id=account.id, state=AccountLockState.REPLIED))
    session.commit()
    reasons = preapply_recheck(session, batch.id)
    assert any(r.startswith("ACCOUNT_LOCKED_") for r in reasons)


def test_preapply_recheck_catches_unapproved_draft(
    session: Session, account: Account, contact: Contact
) -> None:
    batch = _batch_with_item(session, account, contact)
    assert batch.id is not None
    draft = session.exec(select(EmailDraft)).one()
    draft.status = "DRAFT"
    session.commit()
    reasons = preapply_recheck(session, batch.id)
    assert any(r.startswith("DRAFT_NOT_APPROVED_") for r in reasons)
