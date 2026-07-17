"""Compliance gate — table-driven per region. See docs/adr/0002."""

from __future__ import annotations

import pytest

from spindle_gtm.compliance import GateContext, compliance_gate
from spindle_gtm.region_policy import load_region_policies

POLICIES = load_region_policies()


def test_us_passes_with_footer() -> None:
    ctx = GateContext(region_code="US", has_unsubscribe=True, has_physical_address=True)
    assert compliance_gate(ctx, POLICIES).passed


def test_us_holds_without_unsubscribe() -> None:
    ctx = GateContext(region_code="US", has_physical_address=True)
    result = compliance_gate(ctx, POLICIES)
    assert result.held
    assert "unsubscribe" in result.reason


@pytest.mark.parametrize("region", ["CA", "AU", "IN", "JP"])
def test_consent_regions_hold_without_lawful_basis(region: str) -> None:
    ctx = GateContext(region_code=region, has_unsubscribe=True, has_physical_address=True)
    assert compliance_gate(ctx, POLICIES).held


@pytest.mark.parametrize("region", ["CA", "AU", "IN", "JP"])
def test_consent_regions_pass_with_lawful_basis(region: str) -> None:
    ctx = GateContext(
        region_code=region,
        has_lawful_basis=True,
        has_unsubscribe=True,
        has_physical_address=True,
    )
    assert compliance_gate(ctx, POLICIES).passed


def test_korea_email_blocked_even_with_footer() -> None:
    ctx = GateContext(region_code="KR", has_unsubscribe=True, has_physical_address=True)
    assert compliance_gate(ctx, POLICIES).held


def test_suppression_always_wins() -> None:
    ctx = GateContext(
        region_code="US",
        suppressed=True,
        has_unsubscribe=True,
        has_physical_address=True,
    )
    result = compliance_gate(ctx, POLICIES)
    assert result.held
    assert result.reason == "suppressed"


def test_unknown_region_holds() -> None:
    ctx = GateContext(region_code="ZZ", has_unsubscribe=True, has_physical_address=True)
    assert compliance_gate(ctx, POLICIES).held


def test_linkedin_manual_bypasses_email_gate() -> None:
    # KR blocks cold email, but the manual human channel is always allowed.
    ctx = GateContext(region_code="KR", channel="linkedin_manual")
    assert compliance_gate(ctx, POLICIES).passed
