"""Pure, testable data providers for the review dashboard.

Each function takes a Session and returns plain list[dict] rows so the Streamlit layer
stays a thin renderer and everything here is unit-testable with synthetic fixtures.
"""

from __future__ import annotations

import json
from typing import Any

from sqlmodel import Session, select

from spindle_gtm.models import (
    Account,
    AccountContactRole,
    AccountLock,
    AccountScore,
    Activity,
    ClaimStatus,
    Contact,
    ContactScore,
    DiscoveryCall,
    EditHistory,
    EmailDraft,
    EvidenceClaim,
    EvidenceVerification,
    Experiment,
    ExperimentAssignment,
    ExternalActionManifest,
    LinkedinManualTask,
    LoiRecord,
    OutreachBatch,
    OutreachBatchItem,
    PilotProposal,
    SuppressionEntry,
)

Row = dict[str, Any]


def _latest_score(session: Session, account_id: int) -> AccountScore | None:
    scores = list(session.exec(select(AccountScore).where(AccountScore.account_id == account_id)))
    return max(scores, key=lambda s: s.scored_at) if scores else None


def _top_trigger(session: Session, account_id: int) -> EvidenceClaim | None:
    claims = [
        c
        for c in session.exec(select(EvidenceClaim).where(EvidenceClaim.account_id == account_id))
        if c.status == ClaimStatus.VERIFIED
    ]
    return max(claims, key=lambda c: c.confidence or 0) if claims else None


def accounts_view(session: Session) -> list[Row]:
    rows: list[Row] = []
    for acct in session.exec(select(Account).where(Account.active)):
        assert acct.id is not None
        score = _latest_score(session, acct.id)
        trigger = _top_trigger(session, acct.id)
        icp = score.score if score else None
        rows.append(
            {
                "account": acct.name,
                "region": acct.region_code,
                "icp_score": icp,
                "priority": "high" if (icp or 0) >= 7 else ("medium" if (icp or 0) >= 4 else "low"),
                "trigger": trigger.claim if trigger else None,
                "trigger_confidence": trigger.confidence if trigger else None,
                "segment": acct.industry,
                "stage": acct.status,
                "next_action": _next_action(acct.status),
            }
        )
    return rows


def _next_action(status: str) -> str:
    return {
        "pulled": "qualify",
        "researching": "finish research",
        "research_ready": "select buying group",
        "in_batch": "review drafts",
        "contacted": "await reply / follow up",
        "engaged": "prepare discovery",
        "won": "run pilot",
        "disqualified": "none",
    }.get(status, "review")


def buying_groups_view(session: Session) -> list[Row]:
    rows: list[Row] = []
    for role in session.exec(select(AccountContactRole)):
        contact = session.get(Contact, role.contact_id)
        account = session.get(Account, role.account_id)
        cscore = session.exec(
            select(ContactScore).where(ContactScore.contact_id == role.contact_id)
        ).first()
        rows.append(
            {
                "account": account.name if account else role.account_id,
                "contact": f"{contact.first_name or ''} {contact.last_name or ''}".strip()
                if contact
                else role.contact_id,
                "title": contact.title if contact else None,
                "role": role.role,
                "score": cscore.score if cscore else None,
                "confidence": role.confidence,
                "rationale": role.rationale,
            }
        )
    return rows


def research_view(session: Session) -> list[Row]:
    rows: list[Row] = []
    for claim in session.exec(select(EvidenceClaim)):
        verdicts = [
            v.verdict
            for v in session.exec(
                select(EvidenceVerification).where(EvidenceVerification.claim_id == claim.id)
            )
        ]
        rows.append(
            {
                "claim": claim.claim,
                "type": claim.claim_type,
                "source": claim.source_url,
                "excerpt": claim.excerpt,
                "confidence": claim.confidence,
                "freshness": claim.freshness_score,
                "verifier_verdict": verdicts[-1] if verdicts else None,
                "human_approved": claim.human_approved,
            }
        )
    return rows


def drafts_view(session: Session) -> list[Row]:
    rows: list[Row] = []
    for draft in session.exec(select(EmailDraft)):
        contact = session.get(Contact, draft.contact_id)
        role = session.exec(
            select(AccountContactRole).where(AccountContactRole.contact_id == draft.contact_id)
        ).first()
        edits = list(
            session.exec(
                select(EditHistory).where(
                    EditHistory.entity_type == "email_draft",
                    EditHistory.entity_id == draft.id,
                )
            )
        )
        rows.append(
            {
                "draft_id": draft.id,
                "recipient": contact.email if contact else None,
                "persona": role.role if role else None,
                "subject": draft.subject,
                "body": draft.body,
                "evidence_used": draft.evidence_claim_ids_json,
                "policy_flags": draft.gate_result,
                "status": draft.status,
                "edit_count": len(edits),
                "last_edit": edits[-1].new_value if edits else None,
            }
        )
    return rows


def batch_manifest_view(session: Session, batch_id: int) -> Row:
    batch = session.get(OutreachBatch, batch_id)
    if batch is None:
        return {}
    manifest = session.exec(
        select(ExternalActionManifest).where(ExternalActionManifest.batch_id == batch_id)
    ).first()
    items: list[Row] = []
    for item in session.exec(
        select(OutreachBatchItem).where(OutreachBatchItem.batch_id == batch_id)
    ):
        contact = session.get(Contact, item.contact_id)
        draft = session.get(EmailDraft, item.draft_id)
        lock = session.exec(
            select(AccountLock).where(AccountLock.account_id == item.account_id)
        ).first()
        suppressed = (
            session.exec(
                select(SuppressionEntry).where(SuppressionEntry.email == (contact.email or ""))
            ).first()
            is not None
            if contact
            else False
        )
        items.append(
            {
                "recipient": contact.email if contact else None,
                "message_version": draft.updated_at.isoformat() if draft else None,
                "compliance": item.gate_result,
                "suppression": "SUPPRESSED" if suppressed else "clear",
                "account_lock": lock.state if lock else "OPEN",
            }
        )
    return {
        "batch_id": batch.id,
        "status": batch.status,
        "sender": batch.sender_mailbox,
        "sequence_or_action": batch.sequence_ref,
        "schedule": batch.schedule,
        "payload_hash": manifest.manifest_hash if manifest else None,
        "recipients": items,
    }


def tasks_view(session: Session) -> list[Row]:
    rows: list[Row] = []
    for t in session.exec(select(LinkedinManualTask)):
        rows.append(
            {
                "kind": f"linkedin_{t.action}",
                "contact_id": t.contact_id,
                "status": t.status,
                "outcome": t.outcome,
                "note": t.human_note,
            }
        )
    for call in session.exec(select(DiscoveryCall)):
        rows.append(
            {
                "kind": "discovery_preparation",
                "account_id": call.account_id,
                "status": "done" if call.occurred_at else "pending",
                "outcome": call.outcome,
                "note": call.notes,
            }
        )
    for prop in session.exec(select(PilotProposal)):
        rows.append({"kind": "proposal", "account_id": prop.account_id, "status": prop.status})
    for loi in session.exec(select(LoiRecord)):
        rows.append({"kind": "loi", "account_id": loi.account_id, "status": loi.status})
    return rows


_FUNNEL_ACTIVITY_TYPES = (
    "sent",
    "delivered",
    "bounce",
    "positive_reply",
    "referral",
    "meeting",
    "demo",
)


def funnel_view(session: Session) -> Row:
    cfg_threshold = 7.0
    accounts = list(session.exec(select(Account)))
    scores = list(session.exec(select(AccountScore)))
    qualified_ids = {s.account_id for s in scores if s.score >= cfg_threshold}
    approved_contacts = len([d for d in session.exec(select(EmailDraft)) if d.status == "APPROVED"])
    activity_counts = dict.fromkeys(_FUNNEL_ACTIVITY_TYPES, 0)
    for act in session.exec(select(Activity)):
        if act.type in activity_counts:
            activity_counts[act.type] += 1
    proposals = len(list(session.exec(select(PilotProposal))))
    lois = len([r for r in session.exec(select(LoiRecord)) if r.status == "signed"])
    experiments: list[Row] = []
    for exp in session.exec(select(Experiment)):
        n = len(
            list(
                session.exec(
                    select(ExperimentAssignment).where(ExperimentAssignment.experiment_id == exp.id)
                )
            )
        )
        experiments.append({"experiment": exp.key, "status": exp.status, "assignments": n})
    return {
        "qualified_accounts": len(qualified_ids),
        "total_accounts": len(accounts),
        "approved_contacts": approved_contacts,
        **activity_counts,
        "proposals": proposals,
        "lois_signed": lois,
        "experiments": experiments,
    }


def parse_reason_codes(reason_codes_json: str) -> list[str]:
    try:
        return list(json.loads(reason_codes_json))
    except (json.JSONDecodeError, TypeError):
        return []
