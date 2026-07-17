"""Compliance + deliverability gate engine (operational risk control)."""

from __future__ import annotations

import pytest

from spindle_gtm.gates import (
    ContactComplianceInput,
    DeliverabilityInput,
    contact_gate,
    deliverability_gate,
    tracking_allowed,
)
from spindle_gtm.models import GateDecision
from spindle_gtm.qualification.loader import load_app_config

CFG = load_app_config()


def _complete(**overrides: object) -> ContactComplianceInput:
    base: dict[str, object] = {
        "country": "US",
        "company_type": "corporate",
        "business_email_status": "verified",
        "legal_basis_status": "none",
        "region_policy_status": "configured",
        "optout_status": "none",
        "suppressed": False,
        "sender_mailbox": "founder@example.com",
        "domain_auth_status": "verified",
        "deliverability_status": "ready",
    }
    base.update(overrides)
    return ContactComplianceInput(**base)  # type: ignore[arg-type]


# --- the seven required country cases ------------------------------------------
def test_us_b2b_allowed_when_canspam_satisfied() -> None:
    result = contact_gate(_complete(country="US"), CFG)
    assert result.decision == GateDecision.ALLOW
    assert "US_CANSPAM_OK" in result.reason_codes


def test_uk_corporate_allowed() -> None:
    result = contact_gate(_complete(country="UK", company_type="corporate"), CFG)
    assert result.decision == GateDecision.ALLOW
    assert "UK_CORPORATE_OK" in result.reason_codes


def test_uk_sole_trader_requires_review() -> None:
    result = contact_gate(_complete(country="UK", company_type="sole_trader"), CFG)
    assert result.decision == GateDecision.REVIEW
    assert "UK_NON_CORPORATE_REVIEW" in result.reason_codes


def test_canada_blocked_without_consent() -> None:
    result = contact_gate(_complete(country="CA", legal_basis_status="none"), CFG)
    assert result.decision == GateDecision.BLOCK
    assert "CASL_NO_CONSENT" in result.reason_codes


def test_canada_allowed_with_express_consent() -> None:
    result = contact_gate(_complete(country="CA", legal_basis_status="express_consent"), CFG)
    assert result.decision == GateDecision.ALLOW


def test_france_b2b_requires_review_by_default() -> None:
    result = contact_gate(_complete(country="FR"), CFG)
    assert result.decision == GateDecision.REVIEW
    assert "EU_LEGAL_REVIEW_REQUIRED" in result.reason_codes


def test_france_allowed_once_reviewed_and_documented() -> None:
    result = contact_gate(
        _complete(country="FR", region_policy_status="reviewed", legal_basis_status="documented"),
        CFG,
    )
    assert result.decision == GateDecision.ALLOW


def test_unknown_eu_country_requires_review() -> None:
    result = contact_gate(_complete(country="AT"), CFG)  # not in outreach_policy.yaml
    assert result.decision == GateDecision.REVIEW
    assert "EU_LEGAL_REVIEW_REQUIRED" in result.reason_codes


def test_unknown_country_is_legal_review_required() -> None:
    result = contact_gate(_complete(country="ZZ"), CFG)
    assert result.decision == GateDecision.REVIEW
    assert "LEGAL_REVIEW_REQUIRED" in result.reason_codes
    assert "COUNTRY_UNCONFIGURED" in result.reason_codes


# --- fail-closed + universal blocks ---------------------------------------------
def test_missing_data_defaults_to_block() -> None:
    result = contact_gate(ContactComplianceInput(country="US"), CFG)
    assert result.decision == GateDecision.BLOCK
    assert any(code.startswith("MISSING_") for code in result.reason_codes)


def test_suppression_blocks_everything() -> None:
    result = contact_gate(_complete(suppressed=True), CFG)
    assert result.decision == GateDecision.BLOCK
    assert result.reason_codes == ["SUPPRESSED"]


def test_optout_blocks_everything() -> None:
    result = contact_gate(_complete(optout_status="opted_out"), CFG)
    assert result.decision == GateDecision.BLOCK
    assert result.reason_codes == ["OPTED_OUT"]


def test_korea_blocked_via_configured_policy() -> None:
    result = contact_gate(_complete(country="KR"), CFG)
    assert result.decision == GateDecision.BLOCK


# --- deliverability --------------------------------------------------------------
def _ready() -> DeliverabilityInput:
    return DeliverabilityInput(
        spf_verified=True,
        dkim_verified=True,
        dmarc_present=True,
        rdns_or_provider_ok=True,
        sender_identity_complete=True,
        postal_address_configured=True,
        optout_mechanism_configured=True,
        mailbox_health_ok=True,
        daily_cap=10,
        kill_switch_available=True,
        bounce_complaint_monitoring=True,
    )


def test_deliverability_all_green() -> None:
    assert deliverability_gate(_ready(), CFG).decision == GateDecision.ALLOW


@pytest.mark.parametrize(
    ("attr", "code"),
    [
        ("spf_verified", "SPF_UNVERIFIED"),
        ("dkim_verified", "DKIM_UNVERIFIED"),
        ("dmarc_present", "DMARC_MISSING"),
        ("kill_switch_available", "KILL_SWITCH_UNAVAILABLE"),
        ("bounce_complaint_monitoring", "BOUNCE_COMPLAINT_MONITORING_OFF"),
    ],
)
def test_deliverability_single_failures(attr: str, code: str) -> None:
    inp = _ready()
    setattr(inp, attr, False)
    result = deliverability_gate(inp, CFG)
    assert result.decision == GateDecision.BLOCK and code in result.reason_codes


def test_cap_missing_and_exceeding_max_block() -> None:
    inp = _ready()
    inp.daily_cap = None
    assert "DAILY_CAP_MISSING" in deliverability_gate(inp, CFG).reason_codes
    inp.daily_cap = CFG.mailbox_limits.max_daily_cap + 1
    assert "DAILY_CAP_EXCEEDS_MAX" in deliverability_gate(inp, CFG).reason_codes


# --- tracking defaults ------------------------------------------------------------
def test_tracking_disabled_by_default() -> None:
    assert not tracking_allowed(None, CFG)
    assert not tracking_allowed("random-experiment", CFG)  # not allow-listed
