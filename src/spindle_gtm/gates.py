"""Compliance + deliverability gates. Operational risk control, NOT legal advice.

Deterministic, config-informed decisions with reason codes. Defaults to BLOCK when
policy data is missing; unconfigured countries require legal review. Every decision can
be persisted to the compliance decision log. Suppression and account locks are re-checked
immediately before a batch is applied (preapply_recheck).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from sqlmodel import Session, select

from spindle_gtm.domain import account_outbound_blocked, is_suppressed
from spindle_gtm.models import (
    ComplianceDecision,
    Contact,
    EmailDraft,
    GateDecision,
    OutreachBatchItem,
)
from spindle_gtm.qualification.loader import get_app_config
from spindle_gtm.qualification.schemas import AppConfig

# EU/EEA countries routed to the EU rule (country-specific review + documented basis).
EU_COUNTRIES = frozenset(
    [
        "AT",
        "BE",
        "BG",
        "HR",
        "CY",
        "CZ",
        "DK",
        "EE",
        "FI",
        "FR",
        "DE",
        "GR",
        "HU",
        "IE",
        "IT",
        "LV",
        "LT",
        "LU",
        "MT",
        "NL",
        "PL",
        "PT",
        "RO",
        "SK",
        "SI",
        "ES",
        "SE",
        "IS",
        "LI",
        "NO",
    ]
)

# Every contact must have these populated; any missing value -> BLOCK (fail closed).
REQUIRED_CONTACT_FIELDS = (
    "country",
    "business_email_status",
    "legal_basis_status",
    "region_policy_status",
    "optout_status",
    "suppressed",
    "sender_mailbox",
    "domain_auth_status",
    "deliverability_status",
)

_CA_VALID_BASES = {"express_consent", "implied_consent_documented"}
_EU_DOCUMENTED_BASES = {"documented", "legitimate_interest_documented"}


@dataclass
class ContactComplianceInput:
    """The per-contact compliance record. None = unknown = blocked."""

    country: str | None = None
    company_type: str | None = None  # corporate | sole_trader | individual (relevant for UK)
    business_email_status: str | None = None  # verified | guessed
    legal_basis_status: str | None = None  # none | express_consent | ... | documented
    region_policy_status: str | None = None  # configured | reviewed | unconfigured
    optout_status: str | None = None  # none | opted_out
    suppressed: bool | None = None
    sender_mailbox: str | None = None
    domain_auth_status: str | None = None  # verified | unverified
    deliverability_status: str | None = None  # ready | not_ready


@dataclass
class GateResult:
    decision: GateDecision
    reason_codes: list[str] = field(default_factory=list)

    @property
    def allowed(self) -> bool:
        return self.decision == GateDecision.ALLOW


def _missing_fields(inp: ContactComplianceInput) -> list[str]:
    return [f for f in REQUIRED_CONTACT_FIELDS if getattr(inp, f) is None]


def _country_decision(inp: ContactComplianceInput, cfg: AppConfig) -> GateResult:
    country = (inp.country or "").upper()

    if country == "US":
        # Tightly targeted B2B only, with CAN-SPAM fields + opt-out satisfied.
        codes = []
        if inp.business_email_status != "verified":
            codes.append("US_EMAIL_UNVERIFIED")
        if inp.deliverability_status != "ready":
            codes.append("US_CANSPAM_FIELDS_INCOMPLETE")
        if codes:
            return GateResult(GateDecision.BLOCK, codes)
        return GateResult(GateDecision.ALLOW, ["US_CANSPAM_OK"])

    if country in {"UK", "GB"}:
        # Corporate B2B only under the configured PECR/UK GDPR policy; anything else reviews.
        if inp.company_type == "corporate":
            return GateResult(GateDecision.ALLOW, ["UK_CORPORATE_OK"])
        return GateResult(
            GateDecision.REVIEW,
            [
                "UK_NON_CORPORATE_REVIEW",
                f"UK_COMPANY_TYPE_{(inp.company_type or 'unknown').upper()}",
            ],
        )

    if country == "CA":
        if inp.legal_basis_status in _CA_VALID_BASES:
            return GateResult(GateDecision.ALLOW, ["CASL_CONSENT_RECORDED"])
        return GateResult(GateDecision.BLOCK, ["CASL_NO_CONSENT"])

    if country in EU_COUNTRIES or country == "EU":
        # Country-specific review + documented legal basis before send.
        if (
            inp.region_policy_status == "reviewed"
            and inp.legal_basis_status in _EU_DOCUMENTED_BASES
        ):
            return GateResult(GateDecision.ALLOW, [f"EU_{country}_REVIEWED_DOCUMENTED"])
        return GateResult(
            GateDecision.REVIEW, ["EU_LEGAL_REVIEW_REQUIRED", f"EU_COUNTRY_{country}"]
        )

    configured = cfg.outreach_policy.countries.get(country)
    if configured is not None:
        if configured.cold_email_allowed == "yes":
            return GateResult(GateDecision.ALLOW, [f"{country}_POLICY_OK"])
        if configured.cold_email_allowed == "no":
            return GateResult(GateDecision.BLOCK, [f"{country}_COLD_EMAIL_BLOCKED"])
        return GateResult(GateDecision.REVIEW, [f"{country}_POLICY_CAUTION_REVIEW"])

    # Unconfigured country: never guess.
    return GateResult(GateDecision.REVIEW, ["LEGAL_REVIEW_REQUIRED", "COUNTRY_UNCONFIGURED"])


def contact_gate(inp: ContactComplianceInput, cfg: AppConfig | None = None) -> GateResult:
    """The full per-contact compliance decision, fail-closed."""
    cfg = cfg or get_app_config()

    missing = _missing_fields(inp)
    if missing:
        return GateResult(GateDecision.BLOCK, [f"MISSING_{f.upper()}" for f in missing])

    if inp.suppressed:
        return GateResult(GateDecision.BLOCK, ["SUPPRESSED"])
    if inp.optout_status == "opted_out":
        return GateResult(GateDecision.BLOCK, ["OPTED_OUT"])

    return _country_decision(inp, cfg)


# --- deliverability -------------------------------------------------------------
@dataclass
class DeliverabilityInput:
    spf_verified: bool = False
    dkim_verified: bool = False
    dmarc_present: bool = False
    rdns_or_provider_ok: bool = False
    sender_identity_complete: bool = False
    postal_address_configured: bool = False
    optout_mechanism_configured: bool = False
    mailbox_health_ok: bool = False
    daily_cap: int | None = None
    kill_switch_available: bool = False
    bounce_complaint_monitoring: bool = False


_DELIVERABILITY_CODES = {
    "spf_verified": "SPF_UNVERIFIED",
    "dkim_verified": "DKIM_UNVERIFIED",
    "dmarc_present": "DMARC_MISSING",
    "rdns_or_provider_ok": "RDNS_OR_PROVIDER_FAIL",
    "sender_identity_complete": "SENDER_IDENTITY_INCOMPLETE",
    "postal_address_configured": "POSTAL_ADDRESS_MISSING",
    "optout_mechanism_configured": "OPTOUT_MECHANISM_MISSING",
    "mailbox_health_ok": "MAILBOX_HEALTH_BAD",
    "kill_switch_available": "KILL_SWITCH_UNAVAILABLE",
    "bounce_complaint_monitoring": "BOUNCE_COMPLAINT_MONITORING_OFF",
}


def deliverability_gate(inp: DeliverabilityInput, cfg: AppConfig | None = None) -> GateResult:
    cfg = cfg or get_app_config()
    codes = [code for attr, code in _DELIVERABILITY_CODES.items() if not getattr(inp, attr)]
    limits = cfg.mailbox_limits
    if inp.daily_cap is None or inp.daily_cap <= 0:
        codes.append("DAILY_CAP_MISSING")
    elif inp.daily_cap > limits.max_daily_cap:
        codes.append("DAILY_CAP_EXCEEDS_MAX")
    if codes:
        return GateResult(GateDecision.BLOCK, codes)
    return GateResult(GateDecision.ALLOW, ["DELIVERABILITY_READY"])


# --- tracking (off by default) --------------------------------------------------
def tracking_allowed(experiment_key: str | None, cfg: AppConfig | None = None) -> bool:
    """Open/click tracking is disabled unless an allow-listed experiment enables it."""
    cfg = cfg or get_app_config()
    if not experiment_key:
        return False
    return experiment_key in cfg.mailbox_limits.tracking_experiment_allowlist


# --- decision log ----------------------------------------------------------------
def log_decision(
    session: Session,
    result: GateResult,
    *,
    contact_id: int | None = None,
    batch_id: int | None = None,
    context: str = "pre_send",
) -> ComplianceDecision:
    record = ComplianceDecision(
        contact_id=contact_id,
        batch_id=batch_id,
        decision=result.decision,
        reason_codes_json=json.dumps(result.reason_codes),
        context=context,
    )
    session.add(record)
    session.flush()
    return record


# --- pre-apply recheck ------------------------------------------------------------
def preapply_recheck(session: Session, batch_id: int) -> list[str]:
    """Re-check suppression + account lock for every batch item immediately before apply.

    Returns blocking reasons (empty = safe to proceed). Each block is logged.
    """
    reasons: list[str] = []
    items = list(
        session.exec(select(OutreachBatchItem).where(OutreachBatchItem.batch_id == batch_id))
    )
    for item in items:
        contact = session.get(Contact, item.contact_id)
        email = contact.email if contact else None
        if is_suppressed(session, email=email):
            reasons.append(f"SUPPRESSED_CONTACT_{item.contact_id}")
        if account_outbound_blocked(session, item.account_id):
            reasons.append(f"ACCOUNT_LOCKED_{item.account_id}")
        draft = session.get(EmailDraft, item.draft_id)
        if draft is not None and draft.status not in {"APPROVED", "SEND_READY"}:
            reasons.append(f"DRAFT_NOT_APPROVED_{item.draft_id}")
    if reasons:
        log_decision(
            session,
            GateResult(GateDecision.BLOCK, reasons),
            batch_id=batch_id,
            context="pre_apply_recheck",
        )
    return reasons
