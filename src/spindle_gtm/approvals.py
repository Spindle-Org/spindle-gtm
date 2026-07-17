"""Batch approval workflow: DRAFTED -> REVIEWED -> APPROVED, hash-bound, audited.

Rules (docs/adr/0002):
- Only a configured approver may set APPROVED.
- Approval binds to the immutable batch manifest hash; ANY change to recipients, sender,
  copy, schedule, sequence, or policy result changes the hash and invalidates approval.
- Apply requires a second typed confirmation naming the batch id and recipient count.
- There is deliberately NO bulk approve-all operation in this module.
"""

from __future__ import annotations

from sqlmodel import Session, select

from spindle_gtm.domain import manifest_hash
from spindle_gtm.models import (
    Approval,
    AuditLog,
    BatchStatus,
    EditHistory,
    EmailDraft,
    ExternalActionManifest,
    OutreachBatch,
    OutreachBatchItem,
    utcnow,
)


class ApprovalError(RuntimeError):
    pass


# --- manifest of the exact batch content ----------------------------------------
def batch_payload(session: Session, batch: OutreachBatch) -> dict[str, object]:
    """The exact content approval binds to: recipients, sender, copy, schedule, sequence."""
    items = list(
        session.exec(
            select(OutreachBatchItem)
            .where(OutreachBatchItem.batch_id == batch.id)
            .order_by(OutreachBatchItem.id)  # type: ignore[arg-type]
        )
    )
    rows = []
    for item in items:
        draft = session.get(EmailDraft, item.draft_id)
        rows.append(
            {
                "contact_id": item.contact_id,
                "account_id": item.account_id,
                "draft_id": item.draft_id,
                "subject": draft.subject if draft else None,
                "body": draft.body if draft else None,
                "gate_result": item.gate_result,
            }
        )
    return {
        "batch_id": batch.id,
        "sender_mailbox": batch.sender_mailbox,
        "schedule": batch.schedule,
        "sequence_ref": batch.sequence_ref,
        "items": rows,
    }


def current_batch_hash(session: Session, batch: OutreachBatch) -> str:
    return manifest_hash("outreach_batch", f"batch:{batch.id}", batch_payload(session, batch))


def _audit(
    session: Session, actor: str, action: str, batch: OutreachBatch, detail: str = ""
) -> None:
    assert batch.id is not None
    session.add(
        AuditLog(
            actor=actor,
            action=action,
            entity_type="outreach_batch",
            entity_id=batch.id,
            detail=detail,
        )
    )


# --- state transitions -----------------------------------------------------------
def mark_reviewed(session: Session, batch: OutreachBatch, reviewer: str) -> None:
    if batch.status != BatchStatus.DRAFTED:
        raise ApprovalError(f"cannot review from {batch.status}")
    batch.status = BatchStatus.REVIEWED
    _audit(session, reviewer, "reviewed", batch)
    session.flush()


def approve_batch(
    session: Session,
    batch: OutreachBatch,
    manifest: ExternalActionManifest,
    actor: str,
    approvers: list[str],
) -> Approval:
    """Only an approver may approve; the approval snapshots the manifest hash."""
    if actor not in approvers:
        raise ApprovalError(f"{actor!r} is not an authorized approver")
    if batch.status != BatchStatus.REVIEWED:
        raise ApprovalError(f"cannot approve from {batch.status} (must be REVIEWED)")
    if manifest.manifest_hash != current_batch_hash(session, batch):
        raise ApprovalError("manifest is stale: batch content changed since it was built")
    assert manifest.id is not None
    approval = Approval(
        manifest_id=manifest.id,
        approved_manifest_hash=manifest.manifest_hash,
        approved_by=actor,
    )
    session.add(approval)
    batch.status = BatchStatus.APPROVED
    _audit(session, actor, "approved", batch, detail=manifest.manifest_hash)
    session.flush()
    return approval


def check_approval_still_valid(session: Session, batch: OutreachBatch, approval: Approval) -> bool:
    """Approval is valid only while the batch content hash matches the approved hash."""
    if approval.revoked_at is not None:
        return False
    return approval.approved_manifest_hash == current_batch_hash(session, batch)


def invalidate_if_changed(
    session: Session, batch: OutreachBatch, approval: Approval, actor: str = "system"
) -> bool:
    """Revoke approval (and drop back to REVIEWED) if the batch content changed."""
    if check_approval_still_valid(session, batch, approval):
        return False
    if approval.revoked_at is None:
        approval.revoked_at = utcnow()
    if batch.status == BatchStatus.APPROVED:
        batch.status = BatchStatus.REVIEWED
    _audit(session, actor, "approval_revoked", batch, detail="content changed after approval")
    session.flush()
    return True


# --- edits (recorded + approval-invalidating) ------------------------------------
def edit_draft_field(
    session: Session,
    draft: EmailDraft,
    field: str,
    new_value: str,
    editor: str,
) -> None:
    """Edit a draft field with history; any copy change invalidates batch approval."""
    old_value = getattr(draft, field)
    setattr(draft, field, new_value)
    assert draft.id is not None
    session.add(
        EditHistory(
            entity_type="email_draft",
            entity_id=draft.id,
            field=field,
            old_value=old_value,
            new_value=new_value,
            editor=editor,
        )
    )
    if draft.batch_id is not None:
        batch = session.get(OutreachBatch, draft.batch_id)
        if batch is not None:
            for approval in _batch_approvals(session, batch):
                invalidate_if_changed(session, batch, approval, actor=editor)
    session.flush()


def _batch_approvals(session: Session, batch: OutreachBatch) -> list[Approval]:
    manifests = list(
        session.exec(
            select(ExternalActionManifest).where(ExternalActionManifest.batch_id == batch.id)
        )
    )
    ids = [m.id for m in manifests if m.id is not None]
    if not ids:
        return []
    return list(session.exec(select(Approval).where(Approval.manifest_id.in_(ids))))  # type: ignore[attr-defined]


# --- typed apply confirmation ------------------------------------------------------
def expected_confirmation(batch_id: int, recipient_count: int) -> str:
    return f"APPLY {batch_id} {recipient_count}"


def confirm_apply(session: Session, batch: OutreachBatch, typed: str, actor: str) -> bool:
    """Second typed confirmation gate. Must match 'APPLY <batch_id> <recipient_count>'."""
    assert batch.id is not None
    count = len(
        list(session.exec(select(OutreachBatchItem).where(OutreachBatchItem.batch_id == batch.id)))
    )
    ok = typed.strip() == expected_confirmation(batch.id, count)
    _audit(
        session,
        actor,
        "apply_confirmed" if ok else "apply_confirmation_failed",
        batch,
        detail=f"typed={typed!r} expected count={count}",
    )
    session.flush()
    return ok
