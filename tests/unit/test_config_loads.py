"""Every qualification config file loads and validates against its schema."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from spindle_gtm.qualification.loader import load_app_config
from spindle_gtm.qualification.schemas import Persona


def test_app_config_validates() -> None:
    cfg = load_app_config()
    assert cfg.icp.revenue.min == 20_000_000
    assert cfg.icp.revenue.max == 200_000_000
    assert {"US", "UK", "EU", "IN", "MX", "BR", "CA", "JP", "KR"} <= set(cfg.icp.countries)


def test_all_five_personas_defined() -> None:
    cfg = load_app_config()
    defined = set(cfg.personas.personas)
    assert {
        Persona.OPERATIONAL_CHAMPION,
        Persona.EXECUTIVE_SPONSOR,
        Persona.TECHNICAL_APPROVER,
        Persona.COMPLIANCE_STAKEHOLDER,
    } <= defined


def test_exclusions_present() -> None:
    cfg = load_app_config()
    joined = " ".join(cfg.personas.exclusion_titles).lower()
    for term in ["marketing", "intern", "assistant", "finance", "legal", "human resources"]:
        assert term in joined


def test_outreach_policy_cold_email_is_string_not_bool() -> None:
    # Guards the classic YAML `yes` -> bool footgun.
    cfg = load_app_config()
    assert cfg.outreach_policy.countries["US"].cold_email_allowed == "yes"
    assert cfg.outreach_policy.countries["KR"].cold_email_allowed == "no"


def test_thresholds_are_ordered() -> None:
    cfg = load_app_config()
    assert cfg.account_scoring.review_threshold <= cfg.account_scoring.qualify_threshold
    assert cfg.mailbox_limits.default_daily_cap <= cfg.mailbox_limits.max_daily_cap


def test_every_seniority_term_has_a_bonus_key() -> None:
    # Regression: a seniority term with no bonus key is detected but silently scores 0
    # (e.g. spelled-out "vice president" losing 1.5 vs. "vp").
    cfg = load_app_config()
    bonus_keys = {k.lower() for k in cfg.contact_scoring.seniority_bonus}
    missing = [t for t in cfg.personas.seniority_terms if t.lower() not in bonus_keys]
    assert not missing, f"seniority_terms missing a bonus key: {missing}"


def test_appconfig_rejects_seniority_term_without_bonus() -> None:
    # The invariant must fail loudly at load, not silently score 0.
    cfg = load_app_config()
    bad = cfg.model_dump()
    bad["personas"]["seniority_terms"] = [*cfg.personas.seniority_terms, "archduke"]
    with pytest.raises(ValidationError, match="seniority_bonus key"):
        type(cfg).model_validate(bad)
