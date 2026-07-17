"""Synthetic end-to-end demo: account -> qualify -> buying group -> research ->
verify -> draft -> compliance -> batch -> approval -> gateway verify (dry-run) ->
reply lock. NO external writes, NO Apollo, NO email — everything runs on an in-memory
SQLite DB with synthetic example.com data. Used by `make run` and the release gate.
"""

from __future__ import annotations

import json
from datetime import timedelta
from typing import Any

from sqlmodel import Session

from spindle_gtm.activity_sync import ActivityEvent, ingest_events
from spindle_gtm.apollo_gateway import (
    RealApolloClient,
    default_writes_for_batch,
    plan_writes,
    verify_outbound,
)
from spindle_gtm.approvals import (
    approve_batch,
    batch_payload,
    current_batch_hash,
    mark_reviewed,
)
from spindle_gtm.buying_group import Candidate, discover_buying_group
from spindle_gtm.config import Settings
from spindle_gtm.domain import account_outbound_blocked, build_manifest
from spindle_gtm.gates import ContactComplianceInput, contact_gate
from spindle_gtm.models import (
    Account,
    AccountContactRole,
    AccountScore,
    ClaimType,
    Contact,
    EmailDraft,
    OutreachBatch,
    OutreachBatchItem,
    utcnow,
)
from spindle_gtm.outreach import (
    DraftContext,
    SenderIdentity,
    assign_variant,
    champion_first_email,
    validate_draft,
)
from spindle_gtm.qualification.loader import load_app_config
from spindle_gtm.qualification.scoring import score_account
from spindle_gtm.research import EvidenceInput, persist_research
from spindle_gtm.verify import is_usable_for_outreach, record_verification


def run_demo(session: Session) -> dict[str, Any]:
    cfg = load_app_config()

    # 1) account + ICP score
    account = Account(
        apollo_id="demo-acct-1",
        name="Meridian Apparel",
        domain="meridian.example.com",
        region_code="US",
        industry="apparel",
        hq_country="US",
    )
    session.add(account)
    session.commit()
    session.refresh(account)
    assert account.id is not None
    score = score_account(
        {
            "industry_fit",
            "operational_complexity",
            "seasonal_or_drop_based",
            "outsourced_or_distributed_suppliers",
            "high_style_or_sku_volume",
        },
        180,
        cfg.account_scoring,
    )
    session.add(AccountScore(account_id=account.id, model="det-v1", score=score.score))
    assert score.qualified, "synthetic account should qualify"

    # 2) buying group (champion + sponsor; marketing excluded)
    bg = discover_buying_group(
        [
            Candidate(
                "Ada", "Head of Product Development", email="ada@example.com", email_confidence=0.9
            ),
            Candidate(
                "Bo", "Chief Operating Officer", email="bo@example.com", email_confidence=0.9
            ),
            Candidate("Cy", "Marketing Manager"),
        ],
        cfg.personas,
        cfg.contact_scoring,
        headcount=180,
        account_passed_icp=True,
    )
    assert len(bg.selected) == 2

    champion = Contact(
        account_id=account.id,
        first_name="Ada",
        email="ada@example.com",
        email_status="verified",
        region_code="US",
        title="Head of Product Development",
    )
    sponsor = Contact(
        account_id=account.id,
        first_name="Bo",
        email="bo@example.com",
        email_status="verified",
        region_code="US",
        title="Chief Operating Officer",
    )
    session.add(champion)
    session.add(sponsor)
    session.commit()
    session.refresh(champion)
    session.refresh(sponsor)
    assert champion.id is not None and sponsor.id is not None
    session.add(
        AccountContactRole(
            account_id=account.id,
            contact_id=champion.id,
            role="champion",
            confidence=bg.selected[0].confidence,
        )
    )

    # 3) research + independent verification
    claim = persist_research(
        session,
        account.id,
        [
            EvidenceInput(
                claim="opened a US flagship store in 2026",
                claim_type=ClaimType.VERIFIED_FACT,
                category="recent_expansion",
                source_url="https://meridian.example.com/press/flagship",
                source_title="Press release",
                source_tier="company_primary",
                published_date=utcnow() - timedelta(days=20),
                raw_confidence=0.9,
            )
        ],
        cfg,
    )[0]
    record_verification(session, claim, "evidence-verifier", "verified", "confirmed on press page")
    session.commit()
    assert is_usable_for_outreach(session, claim)
    assert claim.id is not None

    # 4) draft (grounded in the verified claim) + deterministic validation
    sender = SenderIdentity(
        "Ayush", "Spindle", "1 Example St, City", "https://example.com/unsubscribe"
    )
    variant = assign_variant(account.id, ["A", "B"])
    ctx = DraftContext(
        account_id=account.id,
        account_name=account.name,
        first_name="Ada",
        segment="apparel",
        region="US",
        wedge=cfg.pilot_wedges.wedges[0],
        sender=sender,
        variant=variant,
        usable_claim_ids=[claim.id],
        trigger_claim=claim,
    )
    drafted = champion_first_email(ctx, cfg)
    violations = validate_draft(drafted, [claim.id], cfg, is_first_email=True)
    assert violations == [], violations
    draft = EmailDraft(
        account_id=account.id,
        contact_id=champion.id,
        subject=drafted.subject,
        body=drafted.body,
        variant=variant,
        trigger_type="verified_trigger",
        status="APPROVED",
        evidence_claim_ids_json=json.dumps(drafted.evidence_claim_ids),
    )
    session.add(draft)
    session.commit()
    session.refresh(draft)
    assert draft.id is not None

    # 5) compliance gate
    gate = contact_gate(
        ContactComplianceInput(
            country="US",
            company_type="corporate",
            business_email_status="verified",
            legal_basis_status="none",
            region_policy_status="configured",
            optout_status="none",
            suppressed=False,
            sender_mailbox="inbox_1",
            domain_auth_status="verified",
            deliverability_status="ready",
        ),
        cfg,
    )
    assert gate.allowed

    # 6) batch + hash-bound approval
    batch = OutreachBatch(
        name="demo-batch", sender_mailbox="inbox_1", schedule="2026-09-01", sequence_ref="seq_1"
    )
    session.add(batch)
    session.commit()
    session.refresh(batch)
    assert batch.id is not None
    session.add(
        OutreachBatchItem(
            batch_id=batch.id,
            draft_id=draft.id,
            contact_id=champion.id,
            account_id=account.id,
            gate_result="ALLOW",
        )
    )
    session.commit()
    mark_reviewed(session, batch, "reviewer")
    approval_manifest = build_manifest(
        "outreach_batch", f"batch:{batch.id}", batch_payload(session, batch), batch_id=batch.id
    )
    approval_manifest.manifest_hash = current_batch_hash(session, batch)
    session.add(approval_manifest)
    session.flush()
    approve_batch(session, batch, approval_manifest, "ayush", ["ayush"])
    session.commit()

    # 7) gateway plan + verify (dry-run only — nothing is ever written)
    manifests = plan_writes(session, batch, default_writes_for_batch(session, batch))
    session.commit()
    verify_report = verify_outbound(
        session,
        batch,
        manifests,
        verified_inbox_ids={"inbox_1"},
        verified_sequence_ids={"seq_1"},
        settings=Settings(OUTBOUND_ENABLED=True),
        cfg=cfg,
    )
    assert verify_report.ok, verify_report.errors
    # real writes stay blocked regardless
    try:
        RealApolloClient().apply("enroll_sequence", {})
        raise AssertionError("real client must refuse")
    except NotImplementedError:
        pass

    # 8) simulate a reply -> account lock + prepared removal for the other contact
    reply = ingest_events(
        session, [ActivityEvent(type="reply", contact_id=champion.id, classification="positive")]
    )
    session.commit()
    assert account_outbound_blocked(session, account.id)

    return {
        "qualified": score.qualified,
        "icp_score": score.score,
        "buying_group_selected": len(bg.selected),
        "usable_claims": 1,
        "draft_violations": len(violations),
        "compliance_decision": gate.decision.value,
        "batch_status": batch.status,
        "gateway_verify_ok": verify_report.ok,
        "real_writes_blocked": True,
        "reply_lock_engaged": True,
        "removal_manifests_prepared": reply.removal_manifests,
    }


def _main() -> None:
    from sqlalchemy.pool import StaticPool
    from sqlmodel import SQLModel, create_engine

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        summary = run_demo(session)
    print(json.dumps(summary, indent=2, default=str))
    print("E2E DEMO: PASS")


if __name__ == "__main__":
    _main()
