"""Persona classifier edge cases: exclusions, dual titles, consultants, former, novel."""

from __future__ import annotations

from spindle_gtm.qualification.classify import classify_title, classify_with_resolver
from spindle_gtm.qualification.loader import load_app_config
from spindle_gtm.qualification.schemas import Persona

PERSONAS = load_app_config().personas


def _persona(title: str, **kw: object) -> Persona:
    return classify_title(title, PERSONAS, **kw).persona  # type: ignore[arg-type]


def test_exclusion_checked_first() -> None:
    assert _persona("Marketing Manager") == Persona.EXCLUDED
    assert _persona("Customer Service Lead") == Persona.EXCLUDED
    assert _persona("Finance Controller") == Persona.EXCLUDED


def test_former_employee_excluded() -> None:
    assert _persona("Director of Product Development", is_current=False) == Persona.EXCLUDED


def test_consultant_excluded() -> None:
    assert _persona("Sourcing Consultant") == Persona.EXCLUDED
    assert _persona("Freelance Technical Designer") == Persona.EXCLUDED


def test_dual_title_with_excluded_function_is_excluded() -> None:
    # A blended title that includes an excluded function fails safe to EXCLUDED.
    assert _persona("Head of Production & Marketing") == Persona.EXCLUDED


def test_priority_resolves_champion_over_sponsor_when_both_match() -> None:
    # "COO of Product Development" matches sponsor (coo) + champion (product development);
    # operational champion has higher priority and more signal -> champion.
    assert _persona("COO of Product Development") == Persona.OPERATIONAL_CHAMPION


def test_novel_title_is_unknown_and_routes_to_resolver() -> None:
    result = classify_title("Innovation Catalyst", PERSONAS)
    assert result.persona == Persona.UNKNOWN
    assert result.needs_resolver


def test_null_resolver_explains_itself() -> None:
    result, decision = classify_with_resolver("Innovation Catalyst", PERSONAS)
    assert result.needs_resolver
    assert decision is not None
    assert decision.persona == Persona.UNKNOWN
    assert decision.rationale  # a resolver must always explain its decision


def test_clear_titles_do_not_need_resolver() -> None:
    for title in ["Head of Production", "Chief Operating Officer", "Sustainability Manager"]:
        assert not classify_title(title, PERSONAS).needs_resolver
