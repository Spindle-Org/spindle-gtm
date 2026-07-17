"""Pydantic v2 schemas that validate the YAML config in ``config/``.

These are the contract for the qualification engine. Loading is in loader.py.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field, model_validator


class Persona(StrEnum):
    OPERATIONAL_CHAMPION = "operational_champion"
    EXECUTIVE_SPONSOR = "executive_sponsor"
    TECHNICAL_APPROVER = "technical_approver"
    COMPLIANCE_STAKEHOLDER = "compliance_stakeholder"
    EXCLUDED = "excluded"
    UNKNOWN = "unknown"  # classifier could not decide deterministically -> resolver


# --- ICP -----------------------------------------------------------------------
class RevenueBand(BaseModel):
    currency: str = "USD"
    min: float
    max: float
    uncertainty_allowed: bool = True

    @model_validator(mode="after")
    def _check(self) -> RevenueBand:
        if self.min > self.max:
            raise ValueError("revenue min > max")
        return self


class EmployeeBand(BaseModel):
    min: int
    max: int
    is_proxy: bool = True

    @model_validator(mode="after")
    def _check(self) -> EmployeeBand:
        if self.min > self.max:
            raise ValueError("employees min > max")
        return self


class ICPConfig(BaseModel):
    industries: list[str] = Field(min_length=1)
    revenue: RevenueBand
    employees: EmployeeBand
    signals: list[str] = Field(min_length=1)
    complexity_domains: list[str] = Field(min_length=1)
    countries: list[str] = Field(min_length=1)
    require_accessible_leadership: bool = True
    notes: str = ""


# --- scoring -------------------------------------------------------------------
class AccountScoringConfig(BaseModel):
    signal_weights: dict[str, float]
    size_band_weights: dict[str, float] = Field(default_factory=dict)
    qualify_threshold: float
    review_threshold: float

    @model_validator(mode="after")
    def _check(self) -> AccountScoringConfig:
        if self.review_threshold > self.qualify_threshold:
            raise ValueError("review_threshold must be <= qualify_threshold")
        return self


class PersonaRule(BaseModel):
    title_keywords: list[str] = Field(default_factory=list)
    function_keywords: list[str] = Field(default_factory=list)
    seniority: list[str] = Field(default_factory=list)
    weight: float = 1.0
    priority: int = 0  # higher wins ties


class PersonaRulesConfig(BaseModel):
    personas: dict[Persona, PersonaRule]
    exclusion_titles: list[str] = Field(min_length=1)
    seniority_terms: list[str] = Field(default_factory=list)
    # Executive-sponsor weighting by company size (headcount band -> multiplier).
    exec_size_weighting: dict[str, float] = Field(default_factory=dict)
    ambiguity_margin: float = 1.0  # min score gap between top-2 personas to be confident


class ContactScoringConfig(BaseModel):
    persona_base_scores: dict[Persona, float]
    seniority_bonus: dict[str, float] = Field(default_factory=dict)
    email_confidence_floor: float = 0.6
    select_threshold: float


# --- research + evidence -------------------------------------------------------
class ResearchSourceTier(BaseModel):
    name: str
    trust: float  # 0..1
    examples: list[str] = Field(default_factory=list)


class ResearchSourcesConfig(BaseModel):
    hierarchy: list[ResearchSourceTier] = Field(min_length=1)


class EvidenceConfig(BaseModel):
    freshness_days: dict[str, int]  # source_type -> max age in days
    default_freshness_days: int = 180
    require_source_for_personalization: bool = True


# --- messaging + wedges --------------------------------------------------------
class MessageRulesConfig(BaseModel):
    max_subject_chars: int = 90
    max_body_words: int = 150
    max_links: int = 1
    require_unsubscribe: bool = True
    require_physical_address: bool = True
    forbidden_phrases: list[str] = Field(default_factory=list)
    # First-email word bounds and LinkedIn note cap (user-configurable).
    first_email_min_words: int = 80
    first_email_max_words: int = 130
    linkedin_note_max_chars: int = 300
    lead_ban_terms: list[str] = Field(default_factory=list)
    spindle_one_liner: str = ""


class PilotWedge(BaseModel):
    key: str
    pain: str
    wedge: str
    signals: list[str] = Field(default_factory=list)


class PilotWedgesConfig(BaseModel):
    wedges: list[PilotWedge] = Field(min_length=1)


# --- outreach policy (country/region) ------------------------------------------
class CountryPolicy(BaseModel):
    region_code: str
    legal_basis: str
    cold_email_allowed: str  # yes | caution | no
    requires_consent: bool = False
    preferred_channel: str = "email"  # email | linkedin_manual
    notes: str = ""


class OutreachPolicyConfig(BaseModel):
    countries: dict[str, CountryPolicy] = Field(min_length=1)


# --- mailbox limits + suppression ----------------------------------------------
class MailboxLimitsConfig(BaseModel):
    default_daily_cap: int = 20
    max_daily_cap: int = 40
    warmup_days: int = 14
    warmup_start_cap: int = 5
    min_seconds_between_sends: int = 90
    per_contact_frequency_days: int = 30
    # Open/click tracking is DISABLED by default; only an explicitly allow-listed
    # experiment key may enable it (gates.tracking_allowed).
    open_tracking_default: bool = False
    click_tracking_default: bool = False
    tracking_experiment_allowlist: list[str] = Field(default_factory=list)
    # Outbound gateway hard caps.
    max_contacts_per_account: int = 2
    max_batch_size: int = 50

    @model_validator(mode="after")
    def _check(self) -> MailboxLimitsConfig:
        if self.default_daily_cap > self.max_daily_cap:
            raise ValueError("default_daily_cap > max_daily_cap")
        return self


class SuppressionRulesConfig(BaseModel):
    suppressed_domains: list[str] = Field(default_factory=list)
    role_address_localparts: list[str] = Field(default_factory=list)
    block_role_addresses: bool = True
    honor_unsub_events: bool = True


# --- aggregate -----------------------------------------------------------------
class AppConfig(BaseModel):
    icp: ICPConfig
    account_scoring: AccountScoringConfig
    personas: PersonaRulesConfig
    contact_scoring: ContactScoringConfig
    research_sources: ResearchSourcesConfig
    evidence: EvidenceConfig
    message_rules: MessageRulesConfig
    pilot_wedges: PilotWedgesConfig
    outreach_policy: OutreachPolicyConfig
    mailbox_limits: MailboxLimitsConfig
    suppression_rules: SuppressionRulesConfig
