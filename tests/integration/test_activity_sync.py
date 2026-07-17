"""Activity sync critical behaviors + analytics summaries. Fixtures only, no live Apollo."""

from __future__ import annotations

from datetime import timedelta

from sqlmodel import Session, select

from spindle_gtm import analytics
from spindle_gtm.activity_sync import ActivityEvent, IngestReport, ingest_events
from spindle_gtm.domain import account_outbound_blocked
from spindle_gtm.models import (
    Account,
    AccountLock,
    Activity,
    Contact,
    EmailDraft,
    ExternalActionManifest,
    SuppressionEntry,
    WorkTask,
    utcnow,
)


def _second_contact(session: Session, account: Account) -> Contact:
    assert account.id is not None
    other = Contact(account_id=account.id, email="bob@example.com", email_status="verified")
    session.add(other)
    session.commit()
    session.refresh(other)
    return other


def test_reply_creates_replied_lock_and_removal_manifests(
    session: Session, account: Account, contact: Contact
) -> None:
    other = _second_contact(session, account)
    report = ingest_events(
        session, [ActivityEvent(type="reply", contact_id=contact.id, classification="positive")]
    )
    session.commit()
    assert report.locks_created == 1
    assert account.id is not None
    assert account_outbound_blocked(session, account.id)  # immediately blocks new outreach
    # Removal prepared for the OTHER contact only, as PLANNED manifests (not applied).
    assert report.removal_manifests == 1
    manifest = session.exec(
        select(ExternalActionManifest).where(
            ExternalActionManifest.action_type == "apollo:remove_from_sequence"
        )
    ).one()
    assert f'"contact_id":{other.id}' in manifest.payload_json  # canonical JSON, no spaces
    assert manifest.state == "PLANNED"


def test_referral_creates_research_task_never_sends(
    session: Session, account: Account, contact: Contact
) -> None:
    before = len(list(session.exec(select(ExternalActionManifest))))
    report = ingest_events(
        session,
        [
            ActivityEvent(
                type="reply",
                contact_id=contact.id,
                classification="referral",
                payload="talk to Sam, our head of production",
            )
        ],
    )
    session.commit()
    task = session.exec(select(WorkTask).where(WorkTask.kind == "research_referral")).one()
    assert "before ANY outreach" in (task.detail or "")
    assert report.tasks_created == 1
    # No enroll/send manifests were created by the referral itself.
    enrolls = [
        m
        for m in session.exec(select(ExternalActionManifest))
        if "enroll" in m.action_type or "send" in m.action_type
    ]
    assert len(enrolls) == 0 and before == 0


def test_unsub_creates_immediate_suppression(
    session: Session, account: Account, contact: Contact
) -> None:
    ingest_events(session, [ActivityEvent(type="unsub", contact_id=contact.id)])
    session.commit()
    entry = session.exec(select(SuppressionEntry)).one()
    assert entry.email == contact.email and entry.reason == "unsub"
    assert contact.status == "unsubscribed"


def test_bounce_marks_bad_and_requires_reverification(
    session: Session, account: Account, contact: Contact
) -> None:
    report = ingest_events(session, [ActivityEvent(type="bounce", contact_id=contact.id)])
    session.commit()
    assert report.contacts_marked_bad == 1
    assert contact.email_status == "invalid" and contact.status == "bounced"
    task = session.exec(select(WorkTask).where(WorkTask.kind == "reverify_email")).one()
    assert "re-verify" in (task.detail or "")


def test_meeting_creates_discovery_prep_and_lock(
    session: Session, account: Account, contact: Contact
) -> None:
    ingest_events(session, [ActivityEvent(type="meeting", contact_id=contact.id)])
    session.commit()
    lock = session.exec(select(AccountLock)).one()
    assert lock.state == "MEETING_SET"
    assert (
        session.exec(select(WorkTask).where(WorkTask.kind == "discovery_preparation")).first()
        is not None
    )


def test_reply_then_meeting_upgrades_lock(
    session: Session, account: Account, contact: Contact
) -> None:
    ingest_events(session, [ActivityEvent(type="reply", contact_id=contact.id)])
    ingest_events(session, [ActivityEvent(type="meeting", contact_id=contact.id)])
    session.commit()
    lock = session.exec(select(AccountLock)).one()
    assert lock.state == "MEETING_SET"


def test_stage_update_syncs_account_stage(
    session: Session, account: Account, contact: Contact
) -> None:
    ingest_events(
        session, [ActivityEvent(type="stage_update", contact_id=contact.id, payload="Engaged")]
    )
    session.commit()
    assert account.stage == "Engaged"


# --- analytics -------------------------------------------------------------------
def _seed_funnel(session: Session, account: Account, contact: Contact) -> None:
    assert account.id is not None and contact.id is not None
    now = utcnow()
    session.add(
        EmailDraft(
            account_id=account.id,
            contact_id=contact.id,
            variant="A",
            trigger_type="verified_trigger",
            status="APPROVED",
        )
    )
    session.add(
        Activity(
            account_id=account.id,
            contact_id=contact.id,
            type="sent",
            occurred_at=now - timedelta(hours=30),
        )
    )
    session.add(
        Activity(
            account_id=account.id,
            contact_id=contact.id,
            type="delivered",
            occurred_at=now - timedelta(hours=29),
        )
    )
    session.add(
        Activity(
            account_id=account.id,
            contact_id=contact.id,
            type="positive_reply",
            occurred_at=now - timedelta(hours=6),
        )
    )
    session.add(
        Activity(
            account_id=account.id,
            contact_id=contact.id,
            type="meeting",
            occurred_at=now - timedelta(hours=2),
        )
    )
    session.commit()


def test_core_metrics_have_denominators_and_warnings(
    session: Session, account: Account, contact: Contact
) -> None:
    contact.email_status = "verified"
    _seed_funnel(session, account, contact)
    metrics = analytics.core_metrics(session)
    reply = metrics["positive_reply_rate"]
    assert reply["numerator"] == 1 and reply["denominator"] == 1 and reply["rate"] == 1.0
    assert "low sample" in reply["warning"]  # n=1 < 20
    assert metrics["time_to_first_reply_hours"] == 24.0
    assert "open_rate" not in metrics  # never optimize for opens


def test_summary_breakdowns_by_variant_and_trigger(
    session: Session, account: Account, contact: Contact
) -> None:
    _seed_funnel(session, account, contact)
    s = analytics.summary(session, "weekly")
    assert s["period"] == "weekly" and s["window_days"] == 7
    assert s["by_variant"][0]["group"] == "A"
    assert s["by_trigger_type"][0]["group"] == "verified_trigger"
    assert s["activity_in_window"]["positive_reply"] == 1
    assert s["low_sample_warnings"]
    assert "Open rate" in s["note"]


def test_ingest_report_counts(session: Session, account: Account, contact: Contact) -> None:
    report = ingest_events(
        session,
        [
            ActivityEvent(type="delivered", contact_id=contact.id),
            ActivityEvent(type="reply", contact_id=contact.id, classification="positive"),
        ],
    )
    assert isinstance(report, IngestReport) and report.ingested == 2
