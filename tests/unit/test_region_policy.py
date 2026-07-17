"""Region policy config loads and covers the declared target regions."""

from __future__ import annotations

from spindle_gtm.models import ColdEmailPolicy
from spindle_gtm.region_policy import load_region_policies

EXPECTED = {"US", "CA", "UK", "EU", "AU", "IN", "KR", "JP"}


def test_all_target_regions_present() -> None:
    policies = load_region_policies()
    assert set(policies) >= EXPECTED


def test_us_is_permissive_kr_is_blocked() -> None:
    policies = load_region_policies()
    assert policies["US"].cold_email_allowed == ColdEmailPolicy.YES
    assert policies["KR"].cold_email_allowed == ColdEmailPolicy.NO


def test_every_region_requires_unsubscribe() -> None:
    for policy in load_region_policies().values():
        assert policy.unsubscribe_required
