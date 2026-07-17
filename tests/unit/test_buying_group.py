"""Buying-group discovery: selection, ordering, edge cases, enrichment gating."""

from __future__ import annotations

from spindle_gtm.buying_group import Candidate, discover_buying_group
from spindle_gtm.qualification.loader import load_app_config
from spindle_gtm.qualification.schemas import Persona

_CFG = load_app_config()
PERSONAS = _CFG.personas
CONTACT = _CFG.contact_scoring


def _run(cands: list[Candidate], **kw: object):  # type: ignore[no-untyped-def]
    return discover_buying_group(cands, PERSONAS, CONTACT, **kw)  # type: ignore[arg-type]


def _c(title: str, **kw: object) -> Candidate:
    return Candidate(name=kw.pop("name", "X"), title=title, **kw)  # type: ignore[arg-type]


def test_selects_champion_and_sponsor_max_two() -> None:
    res = _run(
        [
            _c(
                "Head of Product Development",
                name="champ",
                email="a@example.com",
                email_confidence=0.9,
            ),
            _c("Chief Operating Officer", name="coo", email="b@example.com", email_confidence=0.9),
            _c("Head of Quality", name="tech", email="c@example.com", email_confidence=0.9),
            _c("Marketing Manager", name="mkt"),
        ],
        headcount=200,
    )
    assert len(res.selected) == 2
    assert {s.persona for s in res.selected} == {
        Persona.OPERATIONAL_CHAMPION,
        Persona.EXECUTIVE_SPONSOR,
    }
    # larger company => champion-first.
    assert res.selected[0].persona == Persona.OPERATIONAL_CHAMPION
    assert res.selected[0].order == 1 and res.selected[1].order == 2
    assert any("stagger" in n.lower() for n in res.notes)
    assert len(res.saved_for_later) == 1  # technical approver saved for later
    assert any("Marketing" in c.title for c, _ in res.rejected)


def test_small_company_founder_first() -> None:
    res = _run(
        [
            _c("Head of Production", name="champ", email="a@example.com", email_confidence=0.9),
            _c("Founder & CEO", name="founder", email="b@example.com", email_confidence=0.9),
        ],
        headcount=30,
    )
    assert res.selected[0].persona == Persona.EXECUTIVE_SPONSOR  # founder/COO-first


def test_plm_heavy_is_champion_first_even_if_small() -> None:
    res = _run(
        [
            _c("Head of Production", name="champ", email="a@example.com", email_confidence=0.9),
            _c("Founder & CEO", name="founder", email="b@example.com", email_confidence=0.9),
        ],
        headcount=30,
        plm_heavy=True,
    )
    assert res.selected[0].persona == Persona.OPERATIONAL_CHAMPION


def test_no_product_dev_function_reports_missing_role() -> None:
    res = _run(
        [
            _c("Chief Operating Officer", name="coo", email="b@example.com", email_confidence=0.9),
            _c("Head of Quality", name="tech", email="c@example.com", email_confidence=0.9),
        ],
        headcount=120,
    )
    assert "operational_champion" in res.missing_roles
    assert all(s.persona != Persona.OPERATIONAL_CHAMPION for s in res.selected)


def test_consultants_and_former_employees_excluded() -> None:
    res = _run(
        [
            _c("Sourcing Consultant", name="consult"),
            _c("Head of Production", name="former", is_current=False),
            _c("Chief Operating Officer", name="coo", email="b@example.com", email_confidence=0.9),
        ],
        headcount=120,
    )
    reasons = {c.name: r for c, r in res.rejected}
    assert "excluded" in reasons.get("consult", "")
    assert "excluded" in reasons.get("former", "")


def test_ambiguous_title_not_auto_selected() -> None:
    res = _run([_c("Innovation Catalyst", name="amb")], headcount=120)
    assert not res.selected
    assert any("ambiguous" in r for _, r in res.rejected)


def test_low_email_confidence_creates_research_task() -> None:
    res = _run(
        [_c("Head of Production", name="champ", email="a@example.com", email_confidence=0.3)],
        headcount=120,
        account_passed_icp=True,
    )
    assert res.selected[0].email_status == "research_task"
    assert res.enrichment_credit_estimate == 0  # never guess/enrich on low confidence


def test_missing_email_on_qualified_account_estimates_enrichment() -> None:
    res = _run(
        [_c("Head of Production", name="champ", email=None)],
        headcount=120,
        account_passed_icp=True,
    )
    assert res.selected[0].email_status == "enrich"
    assert res.enrichment_credit_estimate == 1


def test_enrichment_deferred_until_icp_passed() -> None:
    res = _run(
        [_c("Head of Production", name="champ", email=None)],
        headcount=120,
        account_passed_icp=False,
    )
    assert res.selected[0].email_status == "deferred"
    assert res.enrichment_credit_estimate == 0
