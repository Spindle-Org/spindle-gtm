"""THE one and only Apollo write gateway.

Every Apollo write flows through here. Research/copywriting agents have no Apollo write
tools (their allowlists exclude them, and the PreToolUse hook denies/asks on any direct
attempt); code-level writes are only possible via this module.

v1 actions: account custom fields, contact upsert, add-to-list, manual tasks, stage
updates, sequence enrollment, sequence removal on lock. ONE-OFF EMAIL SEND IS NOT AN
ACTION IN V1 — it stays blocked until explicit human approval after test-mail validation.

Safeguards: dry-run default, immutable per-item manifests + idempotency keys, approval
record bound to the batch hash, full re-validation immediately before write (suppression,
region policy, account locks, caps, exact Apollo inbox/sequence IDs, kill switch),
structured result log, partial-failure recovery, duplicate-safe retry.

The real Apollo client is deliberately NOT implemented — see docs/runbooks/outbound-rollout.md
for the 6 gated steps required before real writes are enabled.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol

from sqlmodel import Session, select

from spindle_gtm.approvals import current_batch_hash
from spindle_gtm.config import Settings, get_settings
from spindle_gtm.domain import build_manifest
from spindle_gtm.gates import preapply_recheck
from spindle_gtm.models import (
    ActionState,
    Approval,
    BatchStatus,
    Contact,
    ExternalActionManifest,
    ExternalActionResult,
    OutreachBatch,
    OutreachBatchItem,
    utcnow,
)
from spindle_gtm.qualification.loader import get_app_config
from spindle_gtm.qualification.schemas import AppConfig


class WriteAction(StrEnum):
    UPDATE_ACCOUNT_FIELDS = "update_account_fields"
    UPSERT_CONTACT = "upsert_contact"
    ADD_TO_LIST = "add_to_list"
    CREATE_TASK = "create_task"
    UPDATE_STAGE = "update_stage"
    ENROLL_SEQUENCE = "enroll_sequence"
    REMOVE_FROM_SEQUENCE = "remove_from_sequence"


V1_ACTIONS = frozenset(WriteAction)
# Not a WriteAction at all — named here only so the guard can reject it by name.
BLOCKED_ACTION_NAMES = frozenset({"send_one_off_email", "send_email", "email_send"})

_SEQUENCE_ACTIONS = {WriteAction.ENROLL_SEQUENCE, WriteAction.REMOVE_FROM_SEQUENCE}


class GatewayError(RuntimeError):
    pass


class ApolloWriteClient(Protocol):
    """Injected transport. Tests use mocks; the real client stays unimplemented until
    the rollout checklist is signed off."""

    def apply(self, action: str, payload: dict[str, Any]) -> dict[str, Any]: ...


class RealApolloClient:
    """Placeholder that refuses to write until rollout sign-off (runbook steps 1-6)."""

    def apply(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError(
            "Real Apollo writes are not enabled. Complete docs/runbooks/outbound-rollout.md "
            "(mocks -> fixtures -> one internal test task -> one internal test enrollment -> "
            "removal/pause verification -> explicit human sign-off) first."
        )


@dataclass
class PlannedWrite:
    action: WriteAction
    target_ref: str  # e.g. "contact:12" / "account:3"
    payload: dict[str, Any]


@dataclass
class VerifyReport:
    ok: bool
    errors: list[str] = field(default_factory=list)


@dataclass
class ExecReport:
    dry_run: bool
    applied: int = 0
    skipped_duplicates: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)


# --- plan -----------------------------------------------------------------------
def plan_writes(
    session: Session, batch: OutreachBatch, writes: list[PlannedWrite]
) -> list[ExternalActionManifest]:
    """One immutable manifest (with idempotency key) per write. Never touches Apollo."""
    allowed = {a.value for a in V1_ACTIONS}
    manifests: list[ExternalActionManifest] = []
    for write in writes:
        action_name = getattr(write.action, "value", str(write.action))
        if action_name in BLOCKED_ACTION_NAMES or action_name not in allowed:
            raise GatewayError(f"action {action_name!r} is not permitted in v1")
        manifest = build_manifest(
            f"apollo:{action_name}", write.target_ref, write.payload, batch_id=batch.id
        )
        session.add(manifest)
        manifests.append(manifest)
    session.flush()
    return manifests


def default_writes_for_batch(session: Session, batch: OutreachBatch) -> list[PlannedWrite]:
    """Default v1 plan: enroll each approved batch item into the batch's sequence."""
    writes: list[PlannedWrite] = []
    for item in session.exec(
        select(OutreachBatchItem).where(OutreachBatchItem.batch_id == batch.id)
    ):
        writes.append(
            PlannedWrite(
                WriteAction.ENROLL_SEQUENCE,
                f"contact:{item.contact_id}",
                {
                    "contact_id": item.contact_id,
                    "sequence_id": batch.sequence_ref,
                    "from_email_account_id": batch.sender_mailbox,
                },
            )
        )
    return writes


# --- verify (also re-run immediately before write) --------------------------------
def _valid_approval(session: Session, batch: OutreachBatch) -> Approval | None:
    manifests = list(
        session.exec(
            select(ExternalActionManifest).where(ExternalActionManifest.batch_id == batch.id)
        )
    )
    ids = [m.id for m in manifests if m.id is not None]
    if not ids:
        return None
    current = current_batch_hash(session, batch)
    for approval in session.exec(select(Approval).where(Approval.manifest_id.in_(ids))):  # type: ignore[attr-defined]
        if approval.revoked_at is None and approval.approved_manifest_hash == current:
            return approval
    return None


def _region_blocked(session: Session, contact_id: int, cfg: AppConfig) -> str | None:
    contact = session.get(Contact, contact_id)
    code = (contact.region_code or "").upper() if contact else ""
    policy = cfg.outreach_policy.countries.get(code)
    if policy is None:
        return f"REGION_UNCONFIGURED_{code or 'NONE'}"
    if policy.cold_email_allowed == "no":
        return f"REGION_BLOCKED_{code}"
    return None


def verify_outbound(
    session: Session,
    batch: OutreachBatch,
    manifests: list[ExternalActionManifest],
    *,
    verified_inbox_ids: set[str] = frozenset(),  # type: ignore[assignment]
    verified_sequence_ids: set[str] = frozenset(),  # type: ignore[assignment]
    mailbox_sent_today: int = 0,
    settings: Settings | None = None,
    cfg: AppConfig | None = None,
) -> VerifyReport:
    """Full re-validation. Run at verify time AND again immediately before write."""
    cfg = cfg or get_app_config()
    settings = settings or get_settings()
    errors: list[str] = []
    assert batch.id is not None

    if batch.status not in {BatchStatus.APPROVED}:
        errors.append(f"BATCH_NOT_APPROVED:{batch.status}")
    if _valid_approval(session, batch) is None:
        errors.append("APPROVAL_MISSING_OR_STALE")

    errors.extend(preapply_recheck(session, batch.id))  # suppression + locks + draft status

    items = list(
        session.exec(select(OutreachBatchItem).where(OutreachBatchItem.batch_id == batch.id))
    )
    limits = cfg.mailbox_limits
    if len(items) > limits.max_batch_size:
        errors.append(f"BATCH_SIZE_EXCEEDED:{len(items)}>{limits.max_batch_size}")
    per_account = Counter(item.account_id for item in items)
    for account_id, count in per_account.items():
        if count > limits.max_contacts_per_account:
            errors.append(f"MAX_CONTACTS_PER_ACCOUNT_EXCEEDED:account={account_id}:{count}")
    if mailbox_sent_today + len(items) > limits.default_daily_cap:
        errors.append(
            f"MAILBOX_DAILY_CAP_EXCEEDED:{mailbox_sent_today}+{len(items)}>{limits.default_daily_cap}"
        )

    for item in items:
        blocked = _region_blocked(session, item.contact_id, cfg)
        if blocked:
            errors.append(blocked)

    for manifest in manifests:
        action = manifest.action_type.removeprefix("apollo:")
        if action in BLOCKED_ACTION_NAMES:
            errors.append(f"BLOCKED_ACTION:{action}")
            continue
        if action in {a.value for a in _SEQUENCE_ACTIONS}:
            payload = json.loads(manifest.payload_json)
            seq = str(payload.get("sequence_id") or "")
            inbox = str(payload.get("from_email_account_id") or "")
            if seq not in verified_sequence_ids:
                errors.append(f"SEQUENCE_ID_NOT_VERIFIED:{seq or 'missing'}")
            if action == WriteAction.ENROLL_SEQUENCE.value and inbox not in verified_inbox_ids:
                errors.append(f"INBOX_ID_NOT_VERIFIED:{inbox or 'missing'}")

    if not settings.outbound_enabled:
        errors.append("KILL_SWITCH_ENGAGED")

    return VerifyReport(ok=not errors, errors=errors)


# --- execute ----------------------------------------------------------------------
def execute_outbound(
    session: Session,
    batch: OutreachBatch,
    manifests: list[ExternalActionManifest],
    client: ApolloWriteClient,
    *,
    dry_run: bool = True,
    typed_confirm: str = "",
    verified_inbox_ids: set[str] = frozenset(),  # type: ignore[assignment]
    verified_sequence_ids: set[str] = frozenset(),  # type: ignore[assignment]
    mailbox_sent_today: int = 0,
    settings: Settings | None = None,
    cfg: AppConfig | None = None,
) -> ExecReport:
    """Apply the planned writes. Dry-run by default; re-validates immediately before
    writing; skips already-applied items (safe retry, no duplicate enrollment)."""
    assert batch.id is not None
    report = ExecReport(dry_run=dry_run)

    if dry_run:
        report.skipped_duplicates = _already_applied_count(session, manifests)
        return report

    expected = expected_outbound_confirmation(session, batch)
    if typed_confirm.strip() != expected:
        raise GatewayError(f"confirmation mismatch: expected {expected!r}")

    verify = verify_outbound(
        session,
        batch,
        manifests,
        verified_inbox_ids=verified_inbox_ids,
        verified_sequence_ids=verified_sequence_ids,
        mailbox_sent_today=mailbox_sent_today,
        settings=settings,
        cfg=cfg,
    )
    if not verify.ok:
        raise GatewayError(f"re-validation failed: {verify.errors}")

    for manifest in manifests:
        assert manifest.id is not None
        existing = session.exec(
            select(ExternalActionResult).where(
                ExternalActionResult.idempotency_key == manifest.idempotency_key
            )
        ).first()
        if existing is not None and existing.state == ActionState.APPLIED:
            report.skipped_duplicates += 1  # safe retry: never enroll twice
            continue
        manifest.state = ActionState.APPLYING
        try:
            response = client.apply(
                manifest.action_type.removeprefix("apollo:"), json.loads(manifest.payload_json)
            )
        except Exception as exc:  # noqa: BLE001 — record and continue (partial-failure recovery)
            manifest.state = ActionState.FAILED
            report.failed += 1
            report.errors.append(f"{manifest.action_type}[{manifest.idempotency_key[:12]}]: {exc}")
            if existing is None:
                session.add(
                    ExternalActionResult(
                        manifest_id=manifest.id,
                        idempotency_key=manifest.idempotency_key,
                        state=ActionState.FAILED,
                        error=str(exc),
                    )
                )
            else:
                existing.state = ActionState.FAILED
                existing.error = str(exc)
                existing.applied_at = utcnow()
            continue
        manifest.state = ActionState.APPLIED
        report.applied += 1
        if existing is None:
            session.add(
                ExternalActionResult(
                    manifest_id=manifest.id,
                    idempotency_key=manifest.idempotency_key,
                    state=ActionState.APPLIED,
                    response_json=json.dumps(response, default=str),
                )
            )
        else:  # retry of a previously FAILED item
            existing.state = ActionState.APPLIED
            existing.error = None
            existing.response_json = json.dumps(response, default=str)
            existing.applied_at = utcnow()
    session.flush()
    if report.failed == 0:
        batch.status = BatchStatus.APPLIED
    return report


def _already_applied_count(session: Session, manifests: list[ExternalActionManifest]) -> int:
    count = 0
    for manifest in manifests:
        existing = session.exec(
            select(ExternalActionResult).where(
                ExternalActionResult.idempotency_key == manifest.idempotency_key
            )
        ).first()
        if existing is not None and existing.state == ActionState.APPLIED:
            count += 1
    return count


def expected_outbound_confirmation(session: Session, batch: OutreachBatch) -> str:
    count = len(
        list(session.exec(select(OutreachBatchItem).where(OutreachBatchItem.batch_id == batch.id)))
    )
    return f"SEND {count} {batch.id}"


def cancel_outbound(
    session: Session, batch: OutreachBatch, manifests: list[ExternalActionManifest]
) -> int:
    """Cancel all not-yet-applied manifests and the batch."""
    cancelled = 0
    for manifest in manifests:
        if manifest.state in {ActionState.PLANNED, ActionState.REVIEWED, ActionState.APPROVED}:
            manifest.state = ActionState.CANCELLED
            cancelled += 1
    batch.status = BatchStatus.CANCELLED
    session.flush()
    return cancelled
