"""Apollo write gateway — mocks only, no live Apollo."""

from __future__ import annotations

from typing import Any

import pytest
from sqlmodel import Session

from spindle_gtm.apollo_gateway import (
    GatewayError,
    PlannedWrite,
    RealApolloClient,
    WriteAction,
    cancel_outbound,
    default_writes_for_batch,
    execute_outbound,
    expected_outbound_confirmation,
    plan_writes,
    verify_outbound,
)
from spindle_gtm.approvals import approve_batch, current_batch_hash, mark_reviewed
from spindle_gtm.config import Settings
from spindle_gtm.domain import build_manifest
from spindle_gtm.models import (
    Account,
    ActionState,
    BatchStatus,
    Contact,
    EmailDraft,
    ExternalActionManifest,
    OutreachBatch,
    OutreachBatchItem,
)
from spindle_gtm.qualification.loader import load_app_config

CFG = load_app_config()
LIVE_SETTINGS = Settings(OUTBOUND_ENABLED=True)
INBOXES = {"inbox_123"}
SEQUENCES = {"seq_456"}


class MockClient:
    def __init__(self, fail_targets: set[str] | None = None) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.fail_targets = fail_targets or set()

    def apply(self, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        if str(payload.get("contact_id")) in self.fail_targets:
            raise RuntimeError("simulated API failure")
        self.calls.append((action, payload))
        return {"ok": True}


def _approved_batch(session: Session, account: Account, contact: Contact) -> OutreachBatch:
    assert account.id is not None and contact.id is not None
    batch = OutreachBatch(
        name="b", sender_mailbox="inbox_123", schedule="2026-08-01", sequence_ref="seq_456"
    )
    session.add(batch)
    session.flush()
    assert batch.id is not None
    draft = EmailDraft(
        account_id=account.id,
        contact_id=contact.id,
        batch_id=batch.id,
        subject="s",
        body="b",
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
    session.flush()
    contact.region_code = "US"
    mark_reviewed(session, batch, "reviewer")
    approval_manifest = build_manifest("outreach_batch", f"batch:{batch.id}", {}, batch_id=batch.id)
    approval_manifest.manifest_hash = current_batch_hash(session, batch)
    session.add(approval_manifest)
    session.flush()
    approve_batch(session, batch, approval_manifest, "ayush", ["ayush"])
    session.commit()
    return batch


def _plan(session: Session, batch: OutreachBatch) -> list[ExternalActionManifest]:
    manifests = plan_writes(session, batch, default_writes_for_batch(session, batch))
    session.commit()
    return manifests


def _execute(session, batch, manifests, client, **kw):  # type: ignore[no-untyped-def]
    kw.setdefault("verified_inbox_ids", INBOXES)
    kw.setdefault("verified_sequence_ids", SEQUENCES)
    kw.setdefault("settings", LIVE_SETTINGS)
    kw.setdefault("cfg", CFG)
    kw.setdefault("typed_confirm", expected_outbound_confirmation(session, batch))
    return execute_outbound(session, batch, manifests, client, **kw)


def test_dry_run_is_default_and_never_calls_client(
    session: Session, account: Account, contact: Contact
) -> None:
    batch = _approved_batch(session, account, contact)
    manifests = _plan(session, batch)
    client = MockClient()
    report = execute_outbound(session, batch, manifests, client)  # defaults: dry_run=True
    assert report.dry_run and client.calls == []


def test_one_off_send_not_a_v1_action(session: Session, account: Account, contact: Contact) -> None:
    batch = _approved_batch(session, account, contact)
    assert "send" not in {a.value for a in WriteAction}
    with pytest.raises(GatewayError, match="not permitted"):
        # Even constructed by force, plan_writes refuses a send action.
        bogus = PlannedWrite("send_one_off_email", "contact:1", {})  # type: ignore[arg-type]
        plan_writes(session, batch, [bogus])


def test_verify_passes_on_clean_approved_batch(
    session: Session, account: Account, contact: Contact
) -> None:
    batch = _approved_batch(session, account, contact)
    manifests = _plan(session, batch)
    report = verify_outbound(
        session,
        batch,
        manifests,
        verified_inbox_ids=INBOXES,
        verified_sequence_ids=SEQUENCES,
        settings=LIVE_SETTINGS,
        cfg=CFG,
    )
    assert report.ok, report.errors


def test_verify_fails_without_approval_and_with_kill_switch(
    session: Session, account: Account, contact: Contact
) -> None:
    batch = _approved_batch(session, account, contact)
    manifests = _plan(session, batch)
    # Kill switch engaged (default settings) + batch content changed (stale approval).
    batch.schedule = "2026-09-09"
    session.commit()
    report = verify_outbound(
        session,
        batch,
        manifests,
        verified_inbox_ids=INBOXES,
        verified_sequence_ids=SEQUENCES,
        cfg=CFG,
        settings=Settings(OUTBOUND_ENABLED=False),
    )
    assert not report.ok
    assert "APPROVAL_MISSING_OR_STALE" in report.errors
    assert "KILL_SWITCH_ENGAGED" in report.errors


def test_verify_fails_on_unverified_sequence_and_inbox_ids(
    session: Session, account: Account, contact: Contact
) -> None:
    batch = _approved_batch(session, account, contact)
    manifests = _plan(session, batch)
    report = verify_outbound(
        session,
        batch,
        manifests,
        verified_inbox_ids=set(),
        verified_sequence_ids=set(),
        settings=LIVE_SETTINGS,
        cfg=CFG,
    )
    assert any(e.startswith("SEQUENCE_ID_NOT_VERIFIED") for e in report.errors)
    assert any(e.startswith("INBOX_ID_NOT_VERIFIED") for e in report.errors)


def test_verify_fails_on_blocked_region(
    session: Session, account: Account, contact: Contact
) -> None:
    batch = _approved_batch(session, account, contact)
    manifests = _plan(session, batch)
    contact.region_code = "KR"  # cold email blocked
    session.commit()
    report = verify_outbound(
        session,
        batch,
        manifests,
        verified_inbox_ids=INBOXES,
        verified_sequence_ids=SEQUENCES,
        settings=LIVE_SETTINGS,
        cfg=CFG,
    )
    assert any(e.startswith("REGION_BLOCKED_KR") for e in report.errors)


def test_verify_enforces_mailbox_daily_cap(
    session: Session, account: Account, contact: Contact
) -> None:
    batch = _approved_batch(session, account, contact)
    manifests = _plan(session, batch)
    report = verify_outbound(
        session,
        batch,
        manifests,
        verified_inbox_ids=INBOXES,
        verified_sequence_ids=SEQUENCES,
        mailbox_sent_today=CFG.mailbox_limits.default_daily_cap,  # already at cap
        settings=LIVE_SETTINGS,
        cfg=CFG,
    )
    assert any(e.startswith("MAILBOX_DAILY_CAP_EXCEEDED") for e in report.errors)


def test_execute_requires_exact_confirmation(
    session: Session, account: Account, contact: Contact
) -> None:
    batch = _approved_batch(session, account, contact)
    manifests = _plan(session, batch)
    assert expected_outbound_confirmation(session, batch) == f"SEND 1 {batch.id}"
    with pytest.raises(GatewayError, match="confirmation mismatch"):
        _execute(session, batch, manifests, MockClient(), dry_run=False, typed_confirm="SEND 99 1")


def test_execute_applies_and_marks_batch(
    session: Session, account: Account, contact: Contact
) -> None:
    batch = _approved_batch(session, account, contact)
    manifests = _plan(session, batch)
    client = MockClient()
    report = _execute(session, batch, manifests, client, dry_run=False)
    session.commit()
    assert report.applied == 1 and report.failed == 0
    assert client.calls[0][0] == "enroll_sequence"
    assert batch.status == BatchStatus.APPLIED
    assert manifests[0].state == ActionState.APPLIED


def test_retry_skips_already_applied_no_duplicate_enrollment(
    session: Session, account: Account, contact: Contact
) -> None:
    batch = _approved_batch(session, account, contact)
    manifests = _plan(session, batch)
    client = MockClient()
    _execute(session, batch, manifests, client, dry_run=False)
    session.commit()
    # Second run: batch is APPLIED so re-approve pathway isn't needed; verify skip logic directly.
    batch.status = BatchStatus.APPROVED
    report2 = _execute(session, batch, manifests, client, dry_run=False)
    assert report2.skipped_duplicates == 1 and report2.applied == 0
    assert len(client.calls) == 1  # never enrolled twice


def test_partial_failure_recovery(session: Session, account: Account, contact: Contact) -> None:
    batch = _approved_batch(session, account, contact)
    # Second contact at the same account.
    assert account.id is not None
    other = Contact(account_id=account.id, email="bob@example.com", region_code="US")
    session.add(other)
    session.flush()
    assert other.id is not None
    draft2 = EmailDraft(
        account_id=account.id,
        contact_id=other.id,
        batch_id=batch.id,
        subject="s",
        body="b",
        status="APPROVED",
    )
    session.add(draft2)
    session.flush()
    assert draft2.id is not None and batch.id is not None
    session.add(
        OutreachBatchItem(
            batch_id=batch.id, draft_id=draft2.id, contact_id=other.id, account_id=account.id
        )
    )
    session.commit()
    # Re-approve after content change.
    batch.status = BatchStatus.DRAFTED
    mark_reviewed(session, batch, "reviewer")
    m = build_manifest("outreach_batch", f"batch:{batch.id}", {"v": 2}, batch_id=batch.id)
    m.manifest_hash = current_batch_hash(session, batch)
    session.add(m)
    session.flush()
    approve_batch(session, batch, m, "ayush", ["ayush"])
    session.commit()

    manifests = _plan(session, batch)
    failing = MockClient(fail_targets={str(contact.id)})
    report = _execute(session, batch, manifests, failing, dry_run=False)
    session.commit()
    assert report.applied == 1 and report.failed == 1
    assert batch.status != BatchStatus.APPLIED  # partial => not fully applied

    # Recovery: retry with a working client; only the failed item is re-attempted.
    batch.status = BatchStatus.APPROVED
    ok_client = MockClient()
    report2 = _execute(session, batch, manifests, ok_client, dry_run=False)
    assert report2.applied == 1 and report2.skipped_duplicates == 1


def test_real_client_refuses_until_rollout_signoff() -> None:
    with pytest.raises(NotImplementedError, match="rollout"):
        RealApolloClient().apply("create_task", {})


def test_cancel_cancels_pending_manifests(
    session: Session, account: Account, contact: Contact
) -> None:
    batch = _approved_batch(session, account, contact)
    manifests = _plan(session, batch)
    n = cancel_outbound(session, batch, manifests)
    session.commit()
    assert n == 1 and batch.status == BatchStatus.CANCELLED
    assert manifests[0].state == ActionState.CANCELLED
