"""Independent evidence-verification pass.

A claim may only be used in outreach if it is a VERIFIED_FACT whose status is VERIFIED
via an independent verification record with a 'verified' verdict and no contradiction.
The re-checking itself is performed by the separate evidence-verifier agent; this module
is the deterministic gate.
"""

from __future__ import annotations

from sqlmodel import Session, select

from spindle_gtm.models import (
    ClaimStatus,
    ClaimType,
    EvidenceClaim,
    EvidenceVerification,
    utcnow,
)

VERDICT_VERIFIED = "verified"
VERDICT_CONTRADICTED = "contradicted"
VERDICT_UNVERIFIED = "unverified"


def record_verification(
    session: Session,
    claim: EvidenceClaim,
    verifier: str,
    verdict: str,
    note: str | None = None,
    source_id: int | None = None,
) -> EvidenceVerification:
    """Record an independent verdict and update the claim's verification status."""
    verification = EvidenceVerification(
        claim_id=claim.id,
        verifier=verifier,
        verdict=verdict,
        note=note,
        source_id=source_id,
        verified_at=utcnow(),
    )
    session.add(verification)
    if verdict == VERDICT_VERIFIED:
        claim.status = ClaimStatus.VERIFIED
    elif verdict == VERDICT_CONTRADICTED:
        claim.status = ClaimStatus.CONTRADICTED
    else:
        claim.status = ClaimStatus.UNVERIFIED
    session.flush()
    return verification


def is_usable_for_outreach(session: Session, claim: EvidenceClaim) -> bool:
    if claim.status != ClaimStatus.VERIFIED or claim.claim_type != ClaimType.VERIFIED_FACT:
        return False
    verdicts = list(
        session.exec(select(EvidenceVerification).where(EvidenceVerification.claim_id == claim.id))
    )
    return any(v.verdict == VERDICT_VERIFIED for v in verdicts) and not any(
        v.verdict == VERDICT_CONTRADICTED for v in verdicts
    )


def usable_claims(session: Session, account_id: int) -> list[EvidenceClaim]:
    claims = session.exec(select(EvidenceClaim).where(EvidenceClaim.account_id == account_id))
    return [c for c in claims if is_usable_for_outreach(session, c)]
