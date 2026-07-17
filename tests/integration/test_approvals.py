"""Approval workflow: roles, hash binding, invalidation, typed confirmation, audit."""

from __future__ import annotations

import pytest
from sqlmodel import Session, select

from spindle_gtm import approvals
from spindle_gtm.approvals import (
    ApprovalError,
    approve_batch,
    batch_payload,
    check_approval_still_valid,
    confirm_apply,
    current_batch_hash,
    edit_draft_field,
    expected_confirmation,
    invalidate_if_changed,
    mark_reviewed,
)
from spindle_gtm.domain import build_manifest
from spindle_gtm.models import (
    Account,
    AuditLog,
    BatchStatus,
    Contact,
    EditHistory,
    EmailDraft,
    ExternalActionManifest,
    OutreachBatch,
    OutreachBatchItem,
)

APPROVERS = ["ayush"]


def _make_batch(
    session: Session, account: Account, contact: Contact
) -> tuple[OutreachBatch, EmailDraft]:
    assert account.id is not None and contact.id is not None
    batch = OutreachBatch(
        name="pilot-batch",
        sender_mailbox="founder@example.com",
        schedule="2026-08-01",
        sequence_ref="one-off",
    )
    session.add(batch)
    session.flush()
    assert batch.id is not None
    draft = EmailDraft(
        account_id=account.id,
        contact_id=contact.id,
        batch_id=batch.id,
        subject="s",
        body="hello",
        status="APPROVED",
    )
    session.add(draft)
    session.flush()
    assert draft.id is not None
    session.add(
        OutreachBatchItem(
            batch_id=batch.id, draft_id=draft.id, contact_id=contact.id, account_id=account.id
        )
    )
    session.commit()
    return batch, draft


def _manifest_for(session: Session, batch: OutreachBatch) -> ExternalActionManifest:
    manifest = build_manifest(
        "outreach_batch", f"batch:{batch.id}", batch_payload(session, batch), batch_id=batch.id
    )
    # build_manifest hashes payload under a nested key; bind to the same hash the checker uses.
    manifest.manifest_hash = current_batch_hash(session, batch)
    session.add(manifest)
    session.flush()
    return manifest


def test_happy_path_drafted_reviewed_approved(
    session: Session, account: Account, contact: Contact
) -> None:
    batch, _ = _make_batch(session, account, contact)
    assert batch.status == BatchStatus.DRAFTED  # default
    mark_reviewed(session, batch, "reviewer")
    manifest = _manifest_for(session, batch)
    approval = approve_batch(session, batch, manifest, "ayush", APPROVERS)
    session.commit()
    assert batch.status == BatchStatus.APPROVED
    assert check_approval_still_valid(session, batch, approval)
    actions = [a.action for a in session.exec(select(AuditLog))]
    assert "reviewed" in actions and "approved" in actions


def test_non_approver_cannot_approve(session: Session, account: Account, contact: Contact) -> None:
    batch, _ = _make_batch(session, account, contact)
    mark_reviewed(session, batch, "reviewer")
    manifest = _manifest_for(session, batch)
    with pytest.raises(ApprovalError, match="not an authorized approver"):
        approve_batch(session, batch, manifest, "intern", APPROVERS)


def test_cannot_approve_from_drafted(session: Session, account: Account, contact: Contact) -> None:
    batch, _ = _make_batch(session, account, contact)
    manifest = _manifest_for(session, batch)
    with pytest.raises(ApprovalError, match="must be REVIEWED"):
        approve_batch(session, batch, manifest, "ayush", APPROVERS)


def test_copy_edit_invalidates_approval_and_records_history(
    session: Session, account: Account, contact: Contact
) -> None:
    batch, draft = _make_batch(session, account, contact)
    mark_reviewed(session, batch, "reviewer")
    manifest = _manifest_for(session, batch)
    approval = approve_batch(session, batch, manifest, "ayush", APPROVERS)
    session.commit()

    edit_draft_field(session, draft, "body", "hello v2", editor="ayush")
    session.commit()

    assert approval.revoked_at is not None  # any copy change invalidates approval
    assert batch.status == BatchStatus.REVIEWED  # dropped back for re-approval
    history = session.exec(select(EditHistory)).one()
    assert (
        history.field == "body" and history.old_value == "hello" and history.new_value == "hello v2"
    )


def test_schedule_change_invalidates_approval(
    session: Session, account: Account, contact: Contact
) -> None:
    batch, _ = _make_batch(session, account, contact)
    mark_reviewed(session, batch, "reviewer")
    manifest = _manifest_for(session, batch)
    approval = approve_batch(session, batch, manifest, "ayush", APPROVERS)
    batch.schedule = "2026-09-01"  # schedule change -> hash changes
    session.commit()
    assert invalidate_if_changed(session, batch, approval)
    assert not check_approval_still_valid(session, batch, approval)


def test_stale_manifest_rejected_at_approval(
    session: Session, account: Account, contact: Contact
) -> None:
    batch, draft = _make_batch(session, account, contact)
    mark_reviewed(session, batch, "reviewer")
    manifest = _manifest_for(session, batch)
    draft.body = "changed after manifest was built"
    session.commit()
    with pytest.raises(ApprovalError, match="stale"):
        approve_batch(session, batch, manifest, "ayush", APPROVERS)


def test_typed_confirmation_exact_match_required(
    session: Session, account: Account, contact: Contact
) -> None:
    batch, _ = _make_batch(session, account, contact)
    assert batch.id is not None
    assert expected_confirmation(batch.id, 1) == f"APPLY {batch.id} 1"
    assert confirm_apply(session, batch, f"APPLY {batch.id} 1", "ayush")
    assert not confirm_apply(session, batch, f"APPLY {batch.id} 2", "ayush")  # wrong count
    assert not confirm_apply(session, batch, "yes please", "ayush")
    actions = [a.action for a in session.exec(select(AuditLog))]
    assert "apply_confirmed" in actions and "apply_confirmation_failed" in actions


def test_no_bulk_approve_exists() -> None:
    # First production version: no bulk approve-all operation is exposed.
    assert not [n for n in dir(approvals) if "bulk" in n.lower() or "approve_all" in n.lower()]
