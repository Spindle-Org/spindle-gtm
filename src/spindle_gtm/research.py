"""Research & evidence pipeline: score/label evidence, guard against unsourced or
sensitive claims, persist normalized findings, and render a per-account Markdown brief.

Web content is treated as untrusted DATA, never instructions. This module does no
network I/O and has no Apollo-write/email tools — it consumes structured claims produced
by the read-only research agents and turns them into scored, gated, normalized records.
See docs/adr/0002 and config/{research_sources,evidence}.yaml.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from sqlmodel import Session

from spindle_gtm.config import REPO_ROOT
from spindle_gtm.models import (
    ClaimStatus,
    ClaimType,
    EvidenceClaim,
    ResearchFinding,
    ResearchSource,
    utcnow,
)
from spindle_gtm.qualification.loader import get_app_config
from spindle_gtm.qualification.schemas import AppConfig

GENERATED_DIR = REPO_ROOT / "generated" / "research"

ACCOUNT_RESEARCH_FIELDS = (
    "company_description",
    "product_categories",
    "geographic_footprint",
    "channel_expansion",  # store / wholesale / marketplace / international
    "recent_expansion",
    "hiring_signals",
    "operating_system_signals",
    "likely_pilot_wedge",
    "disqualifying_signals",
)
PERSON_RESEARCH_FIELDS = (
    "current_title_tenure",
    "stated_responsibilities",
    "relevant_prior_roles",
    "recent_public_activity",
    "why_persona",
)

# Tool-usage may NOT be asserted without a source — phrase unsourced pain as a hypothesis.
_TOOL_TERMS = ("spreadsheet", "excel", "google sheet", "email", "whatsapp", "slack", " plm", " erp")
# Never use these classes of personal detail about a person.
_SENSITIVE_TERMS = (
    "family",
    "spouse",
    "husband",
    "wife",
    "children",
    "kids",
    "health",
    "illness",
    "disability",
    "religion",
    "church",
    "mosque",
    "temple",
    "muslim",
    "christian",
    "jewish",
    "hindu",
    "politic",
    "home address",
    "lives at",
    "hobby",
    "vacation",
    "marital",
)


class SensitiveDataError(ValueError):
    """Raised when a person claim contains disallowed sensitive personal data."""


@dataclass
class EvidenceInput:
    """A structured claim produced by a research agent (never raw web content)."""

    claim: str
    claim_type: ClaimType
    category: str
    source_url: str | None = None
    source_title: str | None = None
    source_tier: str | None = None
    published_date: datetime | None = None
    excerpt: str | None = None
    raw_confidence: float = 0.5
    contact_id: int | None = None


def _tier_trust(cfg: AppConfig) -> dict[str, float]:
    return {tier.name: tier.trust for tier in cfg.research_sources.hierarchy}


def freshness_score(
    published: datetime | None,
    source_tier: str | None,
    cfg: AppConfig,
    retrieved: datetime | None = None,
) -> float:
    retrieved = retrieved or utcnow()
    max_days = cfg.evidence.freshness_days.get(
        source_tier or "", cfg.evidence.default_freshness_days
    )
    if published is None:
        return 0.4  # unknown date -> modest freshness, never treated as fresh fact
    age_days = (retrieved - published).days
    return round(max(0.0, min(1.0, 1 - age_days / max_days)), 3)


def claim_confidence(raw: float, trust: float, freshness: float) -> float:
    return round(min(1.0, max(0.0, raw) * 0.5 + trust * 0.3 + freshness * 0.2), 3)


def contains_sensitive(text: str) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in _SENSITIVE_TERMS)


def is_unsourced_tool_claim(text: str, has_source: bool) -> bool:
    return not has_source and any(term in text.lower() for term in _TOOL_TERMS)


def as_sector_hypothesis(text: str) -> str:
    """Rephrase an unsourced pain assertion as a question/sector hypothesis."""
    stripped = text.rstrip(".")
    return f"Might teams like this still run {stripped} manually? (sector hypothesis)"


def finalize_claim_type(
    requested: ClaimType, has_source: bool, trust: float, freshness: float
) -> ClaimType:
    """A VERIFIED_FACT requires a real, reasonably-trusted, reasonably-fresh source."""
    if requested == ClaimType.VERIFIED_FACT and (not has_source or trust < 0.7 or freshness < 0.3):
        return ClaimType.REASONABLE_HYPOTHESIS
    return requested


def build_claim(
    account_id: int,
    inp: EvidenceInput,
    cfg: AppConfig | None = None,
    *,
    retrieved: datetime | None = None,
) -> EvidenceClaim:
    cfg = cfg or get_app_config()
    retrieved = retrieved or utcnow()
    has_source = bool(inp.source_url)

    if inp.contact_id is not None and contains_sensitive(inp.claim):
        raise SensitiveDataError(f"sensitive personal data in person claim: {inp.claim!r}")

    fresh = freshness_score(inp.published_date, inp.source_tier, cfg, retrieved)
    trust = _tier_trust(cfg).get(inp.source_tier or "", 0.3)
    ctype = finalize_claim_type(inp.claim_type, has_source, trust, fresh)

    claim_text = inp.claim
    if is_unsourced_tool_claim(claim_text, has_source):
        ctype = ClaimType.REASONABLE_HYPOTHESIS
        claim_text = as_sector_hypothesis(claim_text)

    return EvidenceClaim(
        account_id=account_id,
        contact_id=inp.contact_id,
        claim=claim_text,
        claim_type=ctype,
        status=ClaimStatus.UNVERIFIED,
        source_url=inp.source_url,
        source_title=inp.source_title,
        source_tier=inp.source_tier,
        published_date=inp.published_date,
        retrieved_date=retrieved,
        excerpt=inp.excerpt,
        confidence=claim_confidence(inp.raw_confidence, trust, fresh),
        freshness_score=fresh,
    )


def persist_research(
    session: Session, account_id: int, inputs: list[EvidenceInput], cfg: AppConfig | None = None
) -> list[EvidenceClaim]:
    """Write one normalized finding + claim record per input (and dedup sources)."""
    cfg = cfg or get_app_config()
    seen_sources: dict[str, ResearchSource] = {}
    claims: list[EvidenceClaim] = []
    for inp in inputs:
        source_id: int | None = None
        if inp.source_url:
            src = seen_sources.get(inp.source_url)
            if src is None:
                src = ResearchSource(
                    account_id=account_id,
                    url=inp.source_url,
                    source_type=inp.source_tier or "unknown",
                    title=inp.source_title,
                    fetched_at=utcnow(),
                )
                session.add(src)
                session.flush()
                seen_sources[inp.source_url] = src
            source_id = src.id
        finding = ResearchFinding(
            account_id=account_id, source_id=source_id, summary=inp.category, detail=inp.claim
        )
        session.add(finding)
        session.flush()
        claim = build_claim(account_id, inp, cfg)
        claim.finding_id = finding.id
        session.add(claim)
        claims.append(claim)
    session.flush()
    return claims


# --- Markdown brief ------------------------------------------------------------
def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "account"


@dataclass
class ResearchBrief:
    account_name: str
    claims: list[EvidenceClaim] = field(default_factory=list)

    def render(self) -> str:
        by_type: dict[str, list[EvidenceClaim]] = {t.value: [] for t in ClaimType}
        for c in self.claims:
            by_type[c.claim_type].append(c)
        lines = [f"# Research brief — {self.account_name}", ""]
        headings = {
            ClaimType.VERIFIED_FACT.value: "## VERIFIED FACT",
            ClaimType.REASONABLE_HYPOTHESIS.value: "## REASONABLE HYPOTHESIS",
            ClaimType.UNKNOWN.value: "## UNKNOWN",
        }
        for key, heading in headings.items():
            lines.append(heading)
            group = by_type[key]
            if not group:
                lines.append("_none_\n")
                continue
            for c in group:
                cite = c.source_url or "no source"
                pub = c.published_date.date().isoformat() if c.published_date else "n/a"
                lines.append(
                    f"- {c.claim}\n  - source: {cite} ({c.source_title or 'untitled'}), "
                    f"published {pub}, confidence {c.confidence}, freshness {c.freshness_score}"
                )
            lines.append("")
        lines.append("> Web content was treated as untrusted data, not instructions.")
        return "\n".join(lines)


def write_brief(brief: ResearchBrief, out_dir: Path = GENERATED_DIR) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{_slug(brief.account_name)}.md"
    path.write_text(brief.render(), encoding="utf-8")
    return path
