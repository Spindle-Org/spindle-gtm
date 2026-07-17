"""Deterministic account + contact scoring from config."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from spindle_gtm.qualification.schemas import (
    AccountScoringConfig,
    ContactScoringConfig,
    Persona,
    PersonaRulesConfig,
)


@dataclass
class AccountScoreResult:
    score: float
    qualified: bool
    needs_review: bool
    matched_signals: list[str]


def size_band(headcount: int | None) -> str | None:
    if headcount is None:
        return None
    if headcount <= 50:
        return "25-50"
    if headcount <= 200:
        return "51-200"
    return "201-500"


def score_account(
    present_signals: Iterable[str], headcount: int | None, cfg: AccountScoringConfig
) -> AccountScoreResult:
    """Score an account by its matched ICP signals, weighted by size band."""
    signals = list(present_signals)
    base = sum(cfg.signal_weights.get(s, 0.0) for s in signals)
    multiplier = cfg.size_band_weights.get(size_band(headcount) or "", 1.0)
    score = round(base * multiplier, 4)
    return AccountScoreResult(
        score=score,
        qualified=score >= cfg.qualify_threshold,
        needs_review=cfg.review_threshold <= score < cfg.qualify_threshold,
        matched_signals=sorted(s for s in signals if s in cfg.signal_weights),
    )


def exec_size_multiplier(headcount: int | None, personas: PersonaRulesConfig) -> float:
    """Company-size-aware weighting for executive sponsors."""
    if headcount is None:
        return 1.0
    if headcount < 50:
        return personas.exec_size_weighting.get("lt50", 1.0)
    if headcount <= 200:
        return personas.exec_size_weighting.get("50-200", 1.0)
    return personas.exec_size_weighting.get("gt200", 1.0)


def score_contact(
    persona: Persona,
    seniority_present: Iterable[str],
    cfg: ContactScoringConfig,
    *,
    exec_multiplier: float = 1.0,
) -> float:
    """Score a classified contact: persona base + best seniority bonus, exec-weighted."""
    base = cfg.persona_base_scores.get(persona, 0.0)
    bonus = max((cfg.seniority_bonus.get(t.lower(), 0.0) for t in seniority_present), default=0.0)
    score = base + bonus
    if persona == Persona.EXECUTIVE_SPONSOR:
        score *= exec_multiplier
    return round(score, 4)
