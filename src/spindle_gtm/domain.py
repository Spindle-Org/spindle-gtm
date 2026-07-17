"""Domain rules over the local model: idempotency/hashing, state machines,
account-lock gating, approval validity, suppression, and note-preserving sync.

Pure/deterministic where possible so the rules are unit-testable. See the principles
in docs/IMPLEMENTATION_PLAN.md and docs/adr/0002.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlmodel import Session, select

from spindle_gtm.models import (
    Account,
    AccountLock,
    AccountLockState,
    ActionState,
    Approval,
    Contact,
    DraftStatus,
    EmailDraft,
    ExternalActionManifest,
    SuppressionEntry,
    utcnow,
)


class TransitionError(ValueError):
    """Raised on an illegal state transition."""


class SuppressionError(RuntimeError):
    """Raised when an action targets a suppressed recipient."""


# --- deterministic hashing / idempotency ---------------------------------------
def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def payload_hash(payload: Any) -> str:
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()


def idempotency_key(action_type: str, target_ref: str, payload: Any) -> str:
    basis = f"{action_type}|{target_ref}|{payload_hash(payload)}"
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()


def manifest_hash(action_type: str, target_ref: str, payload: Any) -> str:
    return payload_hash({"action_type": action_type, "target_ref": target_ref, "payload": payload})


def build_manifest(
    action_type: str, target_ref: str, payload: Any, batch_id: int | None = None
) -> ExternalActionManifest:
    """Construct a manifest with deterministic idempotency key + hashes (not persisted)."""
    return ExternalActionManifest(
        batch_id=batch_id,
        action_type=action_type,
        idempotency_key=idempotency_key(action_type, target_ref, payload),
        payload_json=canonical_json(payload),
        payload_hash=payload_hash(payload),
        manifest_hash=manifest_hash(action_type, target_ref, payload),
        state=ActionState.PLANNED,
    )


# --- action state machine ------------------------------------------------------
ALLOWED_ACTION_TRANSITIONS: dict[ActionState, set[ActionState]] = {
    ActionState.PLANNED: {ActionState.REVIEWED, ActionState.CANCELLED},
    ActionState.REVIEWED: {ActionState.APPROVED, ActionState.PLANNED, ActionState.CANCELLED},
    ActionState.APPROVED: {ActionState.APPLYING, ActionState.CANCELLED},
    ActionState.APPLYING: {ActionState.APPLIED, ActionState.PARTIAL, ActionState.FAILED},
    ActionState.PARTIAL: {ActionState.APPLYING, ActionState.FAILED, ActionState.CANCELLED},
    ActionState.FAILED: {ActionState.APPLYING, ActionState.CANCELLED},
    ActionState.APPLIED: set(),  # terminal
    ActionState.CANCELLED: set(),  # terminal
}


def assert_action_transition(current: str, new: str) -> None:
    cur, nxt = ActionState(current), ActionState(new)
    if nxt not in ALLOWED_ACTION_TRANSITIONS[cur]:
        raise TransitionError(f"illegal action transition: {cur.value} -> {nxt.value}")


# --- account locks -------------------------------------------------------------
BLOCKING_LOCKS: set[AccountLockState] = {
    AccountLockState.REPLIED,
    AccountLockState.MEETING_SET,
    AccountLockState.DO_NOT_CONTACT,
    AccountLockState.LEGAL_HOLD,
}


def lock_blocks_outbound(state: str) -> bool:
    return AccountLockState(state) in BLOCKING_LOCKS


def account_outbound_blocked(session: Session, account_id: int) -> bool:
    lock = session.exec(select(AccountLock).where(AccountLock.account_id == account_id)).first()
    return lock is not None and lock_blocks_outbound(lock.state)


# --- approvals bind to an immutable manifest hash ------------------------------
def approval_valid(approval: Approval, manifest: ExternalActionManifest) -> bool:
    return approval.revoked_at is None and approval.approved_manifest_hash == manifest.manifest_hash


# --- suppression ---------------------------------------------------------------
def _suppressed_by_email(session: Session, email: str) -> bool:
    return (
        session.exec(select(SuppressionEntry).where(SuppressionEntry.email == email)).first()
        is not None
    )


def _suppressed_by_domain(session: Session, domain: str) -> bool:
    return (
        session.exec(select(SuppressionEntry).where(SuppressionEntry.domain == domain)).first()
        is not None
    )


def is_suppressed(session: Session, *, email: str | None = None, domain: str | None = None) -> bool:
    if email:
        if _suppressed_by_email(session, email):
            return True
        if "@" in email and domain is None:
            domain = email.split("@", 1)[1]
    return bool(domain and _suppressed_by_domain(session, domain))


def _draft_contact(session: Session, draft: EmailDraft) -> Contact | None:
    return session.get(Contact, draft.contact_id)


def draft_send_ready(session: Session, draft: EmailDraft) -> DraftStatus:
    """Gate #1: check suppression before a draft becomes send-ready.

    Suppressed -> HELD; otherwise SEND_READY (stamped). Returns the new status.
    """
    contact = _draft_contact(session, draft)
    email = contact.email if contact else None
    if is_suppressed(session, email=email):
        draft.status = DraftStatus.HELD
        return DraftStatus.HELD
    draft.status = DraftStatus.SEND_READY
    draft.send_ready_at = utcnow()
    return DraftStatus.SEND_READY


def guard_before_apply(session: Session, draft: EmailDraft) -> None:
    """Gate #2: re-check suppression immediately before apply. Raises if suppressed."""
    contact = _draft_contact(session, draft)
    email = contact.email if contact else None
    if is_suppressed(session, email=email):
        raise SuppressionError(f"contact {draft.contact_id} is suppressed; refusing apply")


# --- note-preserving sync ------------------------------------------------------
_HUMAN_FIELDS = frozenset({"notes", "qualification_override"})


def upsert_account(session: Session, incoming: dict[str, Any]) -> Account:
    """Insert or update an account from Apollo, NEVER overwriting human ``notes``."""
    apollo_id = incoming.get("apollo_id")
    existing = (
        session.exec(select(Account).where(Account.apollo_id == apollo_id)).first()
        if apollo_id
        else None
    )
    if existing is None:
        account = Account(**incoming)
        session.add(account)
        return account
    for key, value in incoming.items():
        if key in _HUMAN_FIELDS:
            continue  # preserve human-authored notes
        setattr(existing, key, value)
    existing.source_updated_at = incoming.get("source_updated_at") or utcnow()
    return existing
