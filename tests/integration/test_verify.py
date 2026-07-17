"""Independent verification gating + normalized persistence."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlmodel import Session, select

from spindle_gtm.models import Account, ClaimType, ResearchFinding, ResearchSource
from spindle_gtm.research import EvidenceInput, build_claim, persist_research
from spindle_gtm.verify import is_usable_for_outreach, record_verification, usable_claims


def _fact(account_id: int) -> EvidenceInput:
    return EvidenceInput(
        claim="Opened a US flagship store in 2026",
        claim_type=ClaimType.VERIFIED_FACT,
        category="recent_expansion",
        source_url="https://brand.example.com/press/flagship",
        source_tier="company_primary",
        published_date=datetime.now(UTC) - timedelta(days=20),
        raw_confidence=0.9,
    )


def test_unverified_fact_not_usable(session: Session, account: Account) -> None:
    assert account.id is not None
    claim = build_claim(account.id, _fact(account.id))
    session.add(claim)
    session.commit()
    assert not is_usable_for_outreach(session, claim)


def test_verified_fact_becomes_usable(session: Session, account: Account) -> None:
    assert account.id is not None
    claim = build_claim(account.id, _fact(account.id))
    session.add(claim)
    session.commit()
    record_verification(session, claim, "evidence-verifier", "verified", "confirmed on press page")
    session.commit()
    assert is_usable_for_outreach(session, claim)
    assert [c.id for c in usable_claims(session, account.id)] == [claim.id]


def test_contradicted_claim_unusable(session: Session, account: Account) -> None:
    assert account.id is not None
    claim = build_claim(account.id, _fact(account.id))
    session.add(claim)
    session.commit()
    record_verification(session, claim, "evidence-verifier", "verified")
    record_verification(session, claim, "evidence-verifier-2", "contradicted", "source 404s")
    session.commit()
    assert not is_usable_for_outreach(session, claim)


def test_hypothesis_never_usable(session: Session, account: Account) -> None:
    assert account.id is not None
    inp = EvidenceInput(
        claim="Probably scaling sourcing",
        claim_type=ClaimType.REASONABLE_HYPOTHESIS,
        category="hiring_signals",
    )
    claim = build_claim(account.id, inp)
    session.add(claim)
    session.commit()
    record_verification(session, claim, "evidence-verifier", "verified")
    session.commit()
    assert not is_usable_for_outreach(session, claim)  # only VERIFIED_FACT is usable


def test_persist_writes_normalized_records(session: Session, account: Account) -> None:
    assert account.id is not None
    claims = persist_research(session, account.id, [_fact(account.id)])
    session.commit()
    assert len(claims) == 1 and claims[0].id is not None
    assert session.exec(select(ResearchFinding)).first() is not None
    assert session.exec(select(ResearchSource)).first() is not None
