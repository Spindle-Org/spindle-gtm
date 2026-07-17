"""The single compliance gate every contact must pass before it is sendable.

Pure function over primitive inputs so it is trivially unit-testable without a DB
or network. See docs/IMPLEMENTATION_PLAN.md §11 and docs/adr/0002.
"""

from __future__ import annotations

from pydantic import BaseModel

from spindle_gtm.models import ColdEmailPolicy
from spindle_gtm.region_policy import RegionPolicy


class GateContext(BaseModel):
    """What we know about a contact + our footer at gate time."""

    region_code: str
    channel: str = "email"  # email | linkedin_manual
    suppressed: bool = False
    has_lawful_basis: bool = False
    has_unsubscribe: bool = False
    has_physical_address: bool = False
    email_status: str | None = None  # verified | guessed


class GateResult(BaseModel):
    passed: bool
    reason: str = ""

    @property
    def held(self) -> bool:
        return not self.passed


def compliance_gate(ctx: GateContext, policies: dict[str, RegionPolicy]) -> GateResult:
    """Return pass/hold. Suppression wins over everything; unknown region holds."""
    if ctx.suppressed:
        return GateResult(passed=False, reason="suppressed")

    # LinkedIn manual is a human channel; it never goes through the email gate.
    if ctx.channel == "linkedin_manual":
        return GateResult(passed=True, reason="linkedin_manual (human channel)")

    policy = policies.get(ctx.region_code)
    if policy is None:
        return GateResult(passed=False, reason=f"unknown region: {ctx.region_code!r}")

    if policy.cold_email_allowed == ColdEmailPolicy.NO and not ctx.has_lawful_basis:
        return GateResult(
            passed=False,
            reason=f"{policy.region_code}: cold email not allowed without lawful basis "
            f"({policy.legal_basis}) — use linkedin_manual",
        )

    if policy.requires_consent and not ctx.has_lawful_basis:
        return GateResult(
            passed=False,
            reason=f"{policy.region_code}: consent/lawful basis required ({policy.legal_basis})",
        )

    if policy.unsubscribe_required and not ctx.has_unsubscribe:
        return GateResult(passed=False, reason=f"{policy.region_code}: unsubscribe required")

    if policy.physical_address_required and not ctx.has_physical_address:
        return GateResult(
            passed=False, reason=f"{policy.region_code}: physical postal address required"
        )

    return GateResult(passed=True, reason=f"{policy.region_code}: passed ({policy.legal_basis})")
