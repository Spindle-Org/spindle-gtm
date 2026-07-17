"""Activity synchronization from Apollo (read-only) + reactive safety behaviors.

Events arrive as normalized, injectable inputs (recorded fixtures in tests — no live
Apollo in CI). Ingest applies the critical behaviors:

- any reply at an account -> account-level REPLIED lock + PLANNED remove-from-sequence
  manifests for every other contact at that account (prepared, never auto-applied),
- referral -> a research task for the referred person (never an automatic send),
- unsubscribe/objection -> immediate suppression record,
- bounce / bad data -> contact marked invalid; no retries until re-verification,
- meeting -> discovery-preparation task (and MEETING_SET lock upgrade).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from sqlmodel import Session, select

from spindle_gtm.apollo_gateway import PlannedWrite, WriteAction, plan_writes
from spindle_gtm.models import (
    Account,
    AccountLock,
    AccountLockState,
    Activity,
    Contact,
    OutreachBatch,
    SuppressionEntry,
    WorkTask,
    utcnow,
)


@dataclass
class ActivityEvent:
    """Normalized event from Apollo (delivery/bounce/reply/meeting/task/sequence/stage)."""

    # sent|delivered|bounce|reply|referral|unsub|objection|meeting|task|
    # sequence_state|stage_update
    type: str
    contact_id: int | None = None
    account_id: int | None = None
    classification: str | None = None  # positive | negative | referral (for replies)
    payload: str | None = None
    occurred_at: datetime = field(default_factory=utcnow)


@dataclass
class IngestReport:
    ingested: int = 0
    locks_created: int = 0
    removal_manifests: int = 0
    tasks_created: int = 0
    suppressions: int = 0
    contacts_marked_bad: int = 0


def _account_id_for(session: Session, event: ActivityEvent) -> int | None:
    if event.account_id is not None:
        return event.account_id
    if event.contact_id is not None:
        contact = session.get(Contact, event.contact_id)
        return contact.account_id if contact else None
    return None


def _lock_account(session: Session, account_id: int, state: AccountLockState, reason: str) -> bool:
    lock = session.exec(select(AccountLock).where(AccountLock.account_id == account_id)).first()
    if lock is None:
        session.add(AccountLock(account_id=account_id, state=state, reason=reason))
        return True
    if lock.state == AccountLockState.OPEN or (
        lock.state == AccountLockState.REPLIED and state == AccountLockState.MEETING_SET
    ):
        lock.state = state
        lock.reason = reason
        return True
    return False


def _prepare_sequence_removals(
    session: Session, account_id: int, exclude_contact_id: int | None
) -> int:
    """PLANNED remove-from-sequence manifests for all other contacts at the account."""
    others = [
        c
        for c in session.exec(select(Contact).where(Contact.account_id == account_id))
        if c.id != exclude_contact_id
    ]
    if not others:
        return 0
    # Attach to (or create) a maintenance batch for lock-driven removals.
    batch = session.exec(
        select(OutreachBatch).where(OutreachBatch.name == f"lock-removals-{account_id}")
    ).first()
    if batch is None:
        batch = OutreachBatch(name=f"lock-removals-{account_id}", sequence_ref="pending")
        session.add(batch)
        session.flush()
    writes = [
        PlannedWrite(
            WriteAction.REMOVE_FROM_SEQUENCE,
            f"contact:{c.id}",
            {"contact_id": c.id, "reason": "account_locked"},
        )
        for c in others
    ]
    return len(plan_writes(session, batch, writes))


def _mark_contact_bad(session: Session, contact_id: int | None, reason: str) -> bool:
    if contact_id is None:
        return False
    contact = session.get(Contact, contact_id)
    if contact is None:
        return False
    contact.email_status = "invalid"  # blocks reuse until re-verified
    contact.status = "bounced"
    session.add(
        WorkTask(
            account_id=contact.account_id,
            contact_id=contact_id,
            kind="reverify_email",
            detail=f"bad data: {reason}; re-verify before any retry",
        )
    )
    return True


def ingest_events(session: Session, events: list[ActivityEvent]) -> IngestReport:
    report = IngestReport()
    for event in events:
        account_id = _account_id_for(session, event)
        session.add(
            Activity(
                account_id=account_id or 0,
                contact_id=event.contact_id,
                type=_activity_type(event),
                payload=event.payload,
                occurred_at=event.occurred_at,
            )
        )
        report.ingested += 1

        if event.type == "reply":
            if account_id is not None:
                if _lock_account(session, account_id, AccountLockState.REPLIED, "reply received"):
                    report.locks_created += 1
                report.removal_manifests += _prepare_sequence_removals(
                    session, account_id, event.contact_id
                )
            if event.classification == "referral":
                session.add(
                    WorkTask(
                        account_id=account_id,
                        contact_id=event.contact_id,
                        kind="research_referral",
                        detail=f"research referred person before ANY outreach: {event.payload}",
                    )
                )
                report.tasks_created += 1

        elif event.type == "referral":
            session.add(
                WorkTask(
                    account_id=account_id,
                    contact_id=event.contact_id,
                    kind="research_referral",
                    detail=f"research referred person before ANY outreach: {event.payload}",
                )
            )
            report.tasks_created += 1

        elif event.type in {"unsub", "objection"}:
            contact = session.get(Contact, event.contact_id) if event.contact_id else None
            if contact and contact.email:
                session.add(SuppressionEntry(email=contact.email, scope="email", reason=event.type))
                contact.status = "unsubscribed"
                report.suppressions += 1

        elif event.type == "bounce":
            if _mark_contact_bad(session, event.contact_id, "hard bounce"):
                report.contacts_marked_bad += 1

        elif event.type == "bad_data":
            if _mark_contact_bad(session, event.contact_id, event.payload or "bad data"):
                report.contacts_marked_bad += 1

        elif event.type == "meeting":
            if account_id is not None:
                if _lock_account(session, account_id, AccountLockState.MEETING_SET, "meeting"):
                    report.locks_created += 1
                session.add(
                    WorkTask(
                        account_id=account_id,
                        contact_id=event.contact_id,
                        kind="discovery_preparation",
                        detail="prepare discovery brief before the call",
                    )
                )
                report.tasks_created += 1

        elif event.type == "stage_update" and account_id is not None:
            account = session.get(Account, account_id)
            if account is not None and event.payload:
                account.stage = event.payload

    session.flush()
    return report


def _activity_type(event: ActivityEvent) -> str:
    if event.type == "reply" and event.classification == "positive":
        return "positive_reply"
    if event.type == "reply" and event.classification == "negative":
        return "negative_reply"
    if event.type == "reply" and event.classification == "referral":
        return "referral"
    return event.type
