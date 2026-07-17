"""Buying-group discovery for a qualified account.

Classifies employees deterministically, selects at most one operational champion and
one executive sponsor for INITIAL outreach (<= 2 people, never contacted simultaneously),
saves an optional technical approver for later, estimates enrichment credits, and reports
missing roles instead of forcing a poor match. Uses only role/title text — never protected
characteristics. Email enrichment is only planned for selected candidates once the account
has passed the ICP threshold; low email confidence yields a research task, never a guess.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from spindle_gtm.qualification.classify import classify_title, extract_seniority
from spindle_gtm.qualification.schemas import ContactScoringConfig, Persona, PersonaRulesConfig
from spindle_gtm.qualification.scoring import exec_size_multiplier, score_contact

MAX_INITIAL_OUTREACH = 2


@dataclass
class Candidate:
    name: str
    title: str
    function: str | None = None
    location: str | None = None
    is_current: bool = True
    email: str | None = None
    email_confidence: float | None = None


@dataclass
class ScoredCandidate:
    candidate: Candidate
    persona: Persona
    score: float
    confidence: float
    rationale: str


@dataclass
class Selection:
    candidate: Candidate
    persona: Persona
    order: int  # 1 = first touch, 2 = staggered second touch (never simultaneous)
    confidence: float
    rationale: str
    email_status: str  # ready | enrich | research_task | deferred


@dataclass
class BuyingGroupResult:
    selected: list[Selection]  # initial outreach, <= 2, sequential
    saved_for_later: list[ScoredCandidate]  # optional technical approver
    stakeholders: list[ScoredCandidate]  # compliance etc. (not initial outreach)
    rejected: list[tuple[Candidate, str]]  # (candidate, reason)
    missing_roles: list[str]
    enrichment_credit_estimate: int
    notes: list[str] = field(default_factory=list)

    def render_table(self) -> str:
        lines = ["order | persona | name | confidence | email_status | title"]
        for s in sorted(self.selected, key=lambda x: x.order):
            lines.append(
                f"{s.order} | {s.persona.value} | {s.candidate.name} | {s.confidence:.2f} | "
                f"{s.email_status} | {s.candidate.title}"
            )
        for sc in self.saved_for_later:
            lines.append(
                f"- | {sc.persona.value} (saved) | {sc.candidate.name} | {sc.confidence:.2f} | "
                f"deferred | {sc.candidate.title}"
            )
        if self.missing_roles:
            lines.append(f"MISSING: {', '.join(self.missing_roles)}")
        lines.append(f"enrichment credits (est.): {self.enrichment_credit_estimate}")
        return "\n".join(lines)


def _confidence(score: float) -> float:
    return round(min(1.0, score / 6.0), 2)


def _email_status(cand: Candidate, account_passed_icp: bool, floor: float) -> str:
    if not account_passed_icp:
        return "deferred"  # do not enrich until ICP threshold is passed
    if cand.email and (cand.email_confidence or 0.0) >= floor:
        return "ready"
    if cand.email and (cand.email_confidence or 0.0) < floor:
        return "research_task"  # low confidence -> task, never guess
    return "enrich"  # no email on a qualified account -> enrichment (1 credit)


def discover_buying_group(
    candidates: list[Candidate],
    personas_cfg: PersonaRulesConfig,
    contact_cfg: ContactScoringConfig,
    *,
    headcount: int | None = None,
    plm_heavy: bool = False,
    account_passed_icp: bool = True,
) -> BuyingGroupResult:
    exec_mult = exec_size_multiplier(headcount, personas_cfg)
    floor = contact_cfg.email_confidence_floor

    scored: list[ScoredCandidate] = []
    rejected: list[tuple[Candidate, str]] = []
    for cand in candidates:
        result = classify_title(
            cand.title, personas_cfg, function=cand.function, is_current=cand.is_current
        )
        if result.persona == Persona.EXCLUDED:
            rejected.append((cand, f"excluded: {result.rationale}"))
            continue
        if result.persona == Persona.UNKNOWN:
            rejected.append((cand, "ambiguous title — routed to review, not auto-selected"))
            continue
        seniority = extract_seniority(
            f"{cand.title} {cand.function or ''}", personas_cfg.seniority_terms
        )
        score = score_contact(result.persona, seniority, contact_cfg, exec_multiplier=exec_mult)
        scored.append(
            ScoredCandidate(cand, result.persona, score, _confidence(score), result.rationale)
        )

    def best(persona: Persona) -> ScoredCandidate | None:
        pool = [s for s in scored if s.persona == persona]
        return max(pool, key=lambda s: s.score) if pool else None

    champion = best(Persona.OPERATIONAL_CHAMPION)
    sponsor = best(Persona.EXECUTIVE_SPONSOR)
    technical = best(Persona.TECHNICAL_APPROVER)
    stakeholders = [s for s in scored if s.persona == Persona.COMPLIANCE_STAKEHOLDER]

    # Ordering: small companies => founder/COO-first; larger or PLM-heavy => champion-first.
    founder_first = headcount is not None and headcount < 50 and not plm_heavy
    ordered_picks = [sponsor, champion] if founder_first else [champion, sponsor]

    selected: list[Selection] = []
    notes: list[str] = []
    order = 1
    for pick in ordered_picks:
        if pick is None:
            continue
        if len(selected) >= MAX_INITIAL_OUTREACH:
            break
        selected.append(
            Selection(
                candidate=pick.candidate,
                persona=pick.persona,
                order=order,
                confidence=pick.confidence,
                rationale=pick.rationale,
                email_status=_email_status(pick.candidate, account_passed_icp, floor),
            )
        )
        order += 1

    if len(selected) == MAX_INITIAL_OUTREACH:
        notes.append("Do NOT contact both simultaneously — send order 1 first, stagger order 2.")

    # Selected but not champion/sponsor picks that lost out are rejected with a reason.
    selected_ids = {id(s.candidate) for s in selected}
    for sc in scored:
        if id(sc.candidate) in selected_ids:
            continue
        if technical is not None and sc is technical:
            continue
        if sc in stakeholders:
            continue
        rejected.append(
            (sc.candidate, f"not selected: {sc.persona.value} role already filled or lower score")
        )

    missing_roles: list[str] = []
    if champion is None:
        missing_roles.append("operational_champion")
    if sponsor is None:
        missing_roles.append("executive_sponsor")
    if technical is None:
        notes.append(
            "No technical approver found — leave the slot open rather than forcing a match."
        )

    # Enrichment credits: only for SELECTED candidates that need an email, and only once
    # the account has passed the ICP threshold.
    enrichment_estimate = sum(1 for s in selected if s.email_status == "enrich")

    return BuyingGroupResult(
        selected=selected,
        saved_for_later=[technical] if technical is not None else [],
        stakeholders=stakeholders,
        rejected=rejected,
        missing_roles=missing_roles,
        enrichment_credit_estimate=enrichment_estimate,
        notes=notes,
    )
