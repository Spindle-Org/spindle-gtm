"""Ambiguous-title resolvers.

Deterministic classification is primary. Only genuinely ambiguous titles reach a
resolver, and every resolver MUST explain its decision (``rationale`` is required).
The default resolver uses no LLM. An optional Claude-backed resolver is provided for
production use; it is never exercised in CI and only ever sees the job title plus
non-sensitive company context — never protected characteristics.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from spindle_gtm.qualification.schemas import Persona

_ALLOWED = [
    Persona.OPERATIONAL_CHAMPION,
    Persona.EXECUTIVE_SPONSOR,
    Persona.TECHNICAL_APPROVER,
    Persona.COMPLIANCE_STAKEHOLDER,
    Persona.EXCLUDED,
]


@dataclass
class ResolverDecision:
    persona: Persona
    confidence: float
    rationale: str  # required — a resolver must always explain itself


@runtime_checkable
class TitleResolver(Protocol):
    def resolve(self, title: str, context: dict[str, str]) -> ResolverDecision: ...


class NullResolver:
    """No LLM. Ambiguous titles stay UNKNOWN and route to human review."""

    def resolve(self, title: str, context: dict[str, str]) -> ResolverDecision:
        return ResolverDecision(
            Persona.UNKNOWN,
            0.0,
            f"No LLM configured; title {title!r} is ambiguous and needs human review.",
        )


class ClaudeTitleResolver:
    """Optional LLM tiebreaker (production only; requires `anthropic` + API key).

    Uses a small, fast model. Receives ONLY the title + non-sensitive company context.
    """

    def __init__(self, model: str = "claude-haiku-4-5", max_tokens: int = 300) -> None:
        self.model = model
        self.max_tokens = max_tokens

    def resolve(self, title: str, context: dict[str, str]) -> ResolverDecision:
        import json

        import anthropic  # lazy, optional dependency

        allowed = [p.value for p in _ALLOWED]
        system = (
            "You classify a fashion/apparel brand job TITLE into exactly one persona. "
            "Use ONLY the job title and non-sensitive company context provided. Never infer "
            "or use protected characteristics or sensitive personal information. Respond with "
            'strict JSON: {"persona": one of '
            f"{allowed}, "
            '"confidence": number 0..1, "rationale": short string}.'
        )
        client = anthropic.Anthropic()
        message = client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=[
                {"role": "user", "content": json.dumps({"title": title, "context": context})}
            ],
        )
        data = json.loads(message.content[0].text)
        return ResolverDecision(
            persona=Persona(data["persona"]),
            confidence=float(data["confidence"]),
            rationale=str(data["rationale"]),
        )
