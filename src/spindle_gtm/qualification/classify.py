"""Deterministic persona classification from title/function/seniority.

Exclusions are checked first. Personas are scored by keyword hits; ties break by
configured ``priority``; genuinely close calls (within ``ambiguity_margin`` at equal
priority) are marked ambiguous and routed to a resolver. Uses ONLY job/role text —
never protected characteristics or sensitive personal data.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from spindle_gtm.qualification.resolver import NullResolver, ResolverDecision, TitleResolver
from spindle_gtm.qualification.schemas import Persona, PersonaRulesConfig

_TITLE_WEIGHT = 1.0
_FUNCTION_WEIGHT = 0.5
_SENIORITY_BONUS = 0.25


@dataclass
class ClassificationResult:
    persona: Persona
    score: float
    rationale: str
    scores: dict[Persona, float] = field(default_factory=dict)
    matched_exclusion: str | None = None
    needs_resolver: bool = False


def extract_seniority(text: str, seniority_terms: list[str]) -> list[str]:
    lowered = text.lower()
    return [t for t in seniority_terms if t.lower() in lowered]


def _hits(text: str, keywords: list[str]) -> list[str]:
    return [k for k in keywords if k.lower() in text]


def classify_title(
    title: str,
    cfg: PersonaRulesConfig,
    *,
    function: str | None = None,
    is_current: bool = True,
) -> ClassificationResult:
    """Classify a single title deterministically. Former employees are excluded."""
    if not is_current:
        return ClassificationResult(
            Persona.EXCLUDED, 0.0, "former employee (not current)", matched_exclusion="__former__"
        )

    text = f"{title} {function or ''}".lower().strip()

    for term in cfg.exclusion_titles:
        if term.lower() in text:
            return ClassificationResult(
                Persona.EXCLUDED, 0.0, f"exclusion match: {term!r}", matched_exclusion=term
            )

    scores: dict[Persona, float] = {}
    matched: dict[Persona, list[str]] = {}
    for persona, rule in cfg.personas.items():
        title_hits = _hits(text, rule.title_keywords)
        func_hits = _hits(text, rule.function_keywords)
        score = (len(title_hits) * _TITLE_WEIGHT + len(func_hits) * _FUNCTION_WEIGHT) * rule.weight
        if any(s.lower() in text for s in rule.seniority):
            score += _SENIORITY_BONUS
        scores[persona] = score
        matched[persona] = title_hits + func_hits

    ranked = sorted(
        scores.items(), key=lambda kv: (kv[1], cfg.personas[kv[0]].priority), reverse=True
    )
    top_persona, top_score = ranked[0]
    if top_score == 0:
        return ClassificationResult(
            Persona.UNKNOWN, 0.0, "no persona keywords matched", scores, needs_resolver=True
        )

    if len(ranked) > 1:
        runner_persona, runner_score = ranked[1]
        close = (top_score - runner_score) < cfg.ambiguity_margin
        same_priority = cfg.personas[top_persona].priority == cfg.personas[runner_persona].priority
        if close and same_priority and runner_score > 0:
            return ClassificationResult(
                Persona.UNKNOWN,
                top_score,
                f"ambiguous between {top_persona.value} and {runner_persona.value}",
                scores,
                needs_resolver=True,
            )

    return ClassificationResult(top_persona, top_score, f"matched {matched[top_persona]}", scores)


def classify_with_resolver(
    title: str,
    cfg: PersonaRulesConfig,
    resolver: TitleResolver | None = None,
    *,
    function: str | None = None,
    is_current: bool = True,
    context: dict[str, str] | None = None,
) -> tuple[ClassificationResult, ResolverDecision | None]:
    """Deterministic classification; consult a resolver only when ambiguous."""
    result = classify_title(title, cfg, function=function, is_current=is_current)
    if not result.needs_resolver:
        return result, None
    decision = (resolver or NullResolver()).resolve(title, context or {})
    return result, decision
