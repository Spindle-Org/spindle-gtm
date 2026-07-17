"""Dashboard data providers — synthetic fixtures only."""

from __future__ import annotations

from sqlmodel import Session

from spindle_gtm import dashboard_data as data
from spindle_gtm.models import (
    Account,
    AccountContactRole,
    AccountScore,
    Activity,
    ClaimStatus,
    ClaimType,
    Contact,
    EmailDraft,
    EvidenceClaim,
    Experiment,
    ExperimentAssignment,
    LinkedinManualTask,
    LoiRecord,
    OutreachBatch,
    OutreachBatchItem,
    PilotProposal,
    utcnow,
)


def _seed(session: Session, account: Account, contact: Contact) -> OutreachBatch:
    assert account.id is not None and contact.id is not None
    session.add(AccountScore(account_id=account.id, model="det-v1", score=8.5, rationale="fit"))
    session.add(
        EvidenceClaim(
            account_id=account.id,
            claim="Opened a Tokyo flagship",
            claim_type=ClaimType.VERIFIED_FACT,
            status=ClaimStatus.VERIFIED,
            source_url="https://brand.example.com/press",
            confidence=0.9,
            freshness_score=0.8,
            human_approved=True,
        )
    )
    session.add(
        AccountContactRole(
            account_id=account.id,
            contact_id=contact.id,
            role="champion",
            rationale="matched product development",
            confidence=0.83,
        )
    )
    session.add(
        AccountContactRole(
            account_id=account.id,
            contact_id=contact.id,
            role="rejected",
            rationale="excluded: marketing title",
        )
    )
    batch = OutreachBatch(
        name="b1",
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
        body="b",
        status="APPROVED",
        gate_result="ALLOW",
    )
    session.add(draft)
    session.flush()
    assert draft.id is not None
    session.add(
        OutreachBatchItem(
            batch_id=batch.id,
            draft_id=draft.id,
            contact_id=contact.id,
            account_id=account.id,
            gate_result="ALLOW",
        )
    )
    session.add(
        LinkedinManualTask(account_id=account.id, contact_id=contact.id, action="verify_role")
    )
    session.add(PilotProposal(account_id=account.id, status="draft"))
    session.add(LoiRecord(account_id=account.id, status="signed", signed_at=utcnow()))
    session.add(Activity(account_id=account.id, type="positive_reply", occurred_at=utcnow()))
    session.add(Activity(account_id=account.id, type="meeting", occurred_at=utcnow()))
    exp = Experiment(key="wedge-test", name="Wedge A/B")
    session.add(exp)
    session.flush()
    assert exp.id is not None
    session.add(
        ExperimentAssignment(
            experiment_id=exp.id, unit_type="account", unit_id=account.id, variant="A"
        )
    )
    session.commit()
    return batch


def test_accounts_view(session: Session, account: Account, contact: Contact) -> None:
    _seed(session, account, contact)
    rows = data.accounts_view(session)
    assert len(rows) == 1
    row = rows[0]
    assert row["icp_score"] == 8.5 and row["priority"] == "high"
    assert row["trigger"] == "Opened a Tokyo flagship" and row["trigger_confidence"] == 0.9
    assert row["next_action"] == "qualify"


def test_buying_groups_view_separates_rejected(
    session: Session, account: Account, contact: Contact
) -> None:
    _seed(session, account, contact)
    rows = data.buying_groups_view(session)
    roles = {r["role"] for r in rows}
    assert roles == {"champion", "rejected"}
    rejected = next(r for r in rows if r["role"] == "rejected")
    assert "excluded" in rejected["rationale"]


def test_research_view(session: Session, account: Account, contact: Contact) -> None:
    _seed(session, account, contact)
    rows = data.research_view(session)
    assert rows[0]["human_approved"] is True and rows[0]["source"]


def test_drafts_view(session: Session, account: Account, contact: Contact) -> None:
    _seed(session, account, contact)
    rows = data.drafts_view(session)
    assert rows[0]["persona"] == "champion" and rows[0]["policy_flags"] == "ALLOW"


def test_batch_manifest_view(session: Session, account: Account, contact: Contact) -> None:
    batch = _seed(session, account, contact)
    assert batch.id is not None
    view = data.batch_manifest_view(session, batch.id)
    assert view["sender"] == "founder@example.com"
    assert view["schedule"] == "2026-08-01"
    assert len(view["recipients"]) == 1
    rec = view["recipients"][0]
    assert rec["suppression"] == "clear" and rec["account_lock"] == "OPEN"


def test_tasks_view_kinds(session: Session, account: Account, contact: Contact) -> None:
    _seed(session, account, contact)
    kinds = {r["kind"] for r in data.tasks_view(session)}
    assert {"linkedin_verify_role", "discovery_preparation", "proposal", "loi"} & kinds >= {
        "linkedin_verify_role",
        "proposal",
        "loi",
    }


def test_funnel_view(session: Session, account: Account, contact: Contact) -> None:
    _seed(session, account, contact)
    funnel = data.funnel_view(session)
    assert funnel["qualified_accounts"] == 1
    assert funnel["approved_contacts"] == 1
    assert funnel["positive_reply"] == 1 and funnel["meeting"] == 1
    assert funnel["lois_signed"] == 1
    assert funnel["experiments"][0]["assignments"] == 1
