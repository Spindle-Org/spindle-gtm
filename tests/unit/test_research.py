"""Evidence scoring, guards, and brief rendering."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from spindle_gtm.models import ClaimType
from spindle_gtm.qualification.loader import load_app_config
from spindle_gtm.research import (
    EvidenceInput,
    ResearchBrief,
    SensitiveDataError,
    build_claim,
    finalize_claim_type,
    freshness_score,
    write_brief,
)

CFG = load_app_config()


def _ago(days: int) -> datetime:
    return datetime.now(UTC) - timedelta(days=days)


def test_freshness_recent_is_high() -> None:
    assert freshness_score(_ago(10), "reputable_media", CFG) > 0.8


def test_freshness_old_is_zero() -> None:
    assert freshness_score(_ago(1000), "reputable_media", CFG) == 0.0


def test_freshness_unknown_date_is_moderate() -> None:
    assert freshness_score(None, "reputable_media", CFG) == 0.4


def test_finalize_downgrades_unsourced_fact() -> None:
    assert (
        finalize_claim_type(ClaimType.VERIFIED_FACT, has_source=False, trust=0.9, freshness=0.9)
        == ClaimType.REASONABLE_HYPOTHESIS
    )


def test_finalize_keeps_well_sourced_fact() -> None:
    assert (
        finalize_claim_type(ClaimType.VERIFIED_FACT, has_source=True, trust=0.9, freshness=0.9)
        == ClaimType.VERIFIED_FACT
    )


def test_unsourced_tool_claim_becomes_hypothesis_question() -> None:
    inp = EvidenceInput(
        claim="They use spreadsheets for costing",
        claim_type=ClaimType.VERIFIED_FACT,
        category="operating_system_signals",
    )
    claim = build_claim(1, inp, CFG)
    assert claim.claim_type == ClaimType.REASONABLE_HYPOTHESIS
    assert claim.claim.endswith("(sector hypothesis)")


def test_sensitive_person_claim_rejected() -> None:
    inp = EvidenceInput(
        claim="Active in their local church and coaches kids soccer",
        claim_type=ClaimType.UNKNOWN,
        category="why_persona",
        contact_id=7,
    )
    with pytest.raises(SensitiveDataError):
        build_claim(1, inp, CFG)


def test_well_sourced_fact_keeps_type_and_bounded_confidence() -> None:
    inp = EvidenceInput(
        claim="Launched a new footwear category in 2026",
        claim_type=ClaimType.VERIFIED_FACT,
        category="recent_expansion",
        source_url="https://brand.example.com/press/footwear",
        source_title="Press release",
        source_tier="company_primary",
        published_date=_ago(30),
        raw_confidence=0.9,
    )
    c = build_claim(1, inp, CFG)
    assert c.claim_type == ClaimType.VERIFIED_FACT
    assert 0.0 <= (c.confidence or 0) <= 1.0
    assert (c.freshness_score or 0) > 0.8


def test_brief_has_all_sections_and_untrusted_note() -> None:
    inp = EvidenceInput(
        claim="HQ in London with wholesale in the US",
        claim_type=ClaimType.VERIFIED_FACT,
        category="geographic_footprint",
        source_url="https://brand.example.com/about",
        source_tier="company_primary",
        published_date=_ago(20),
    )
    md = ResearchBrief("Meridian Apparel", [build_claim(1, inp, CFG)]).render()
    assert "VERIFIED FACT" in md and "REASONABLE HYPOTHESIS" in md and "UNKNOWN" in md
    assert "untrusted data" in md


def test_write_brief_to_dir(tmp_path: Path) -> None:
    brief = ResearchBrief("Coastline Denim", [])
    path = write_brief(brief, tmp_path)
    assert path.exists() and path.name == "coastline-denim.md"
