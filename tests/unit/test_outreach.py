"""Outreach drafting engine + deterministic validation."""

from __future__ import annotations

from spindle_gtm.models import ClaimStatus, ClaimType, EvidenceClaim
from spindle_gtm.outreach import (
    Draft,
    DraftContext,
    SenderIdentity,
    assign_variant,
    build_sequence,
    champion_first_email,
    validate_draft,
)
from spindle_gtm.qualification.loader import load_app_config

CFG = load_app_config()
WEDGE = CFG.pilot_wedges.wedges[0]
SENDER = SenderIdentity("Ayush", "Spindle", "1 Example St, City", "https://example.com/unsubscribe")


def _claim() -> EvidenceClaim:
    c = EvidenceClaim(
        account_id=1,
        claim="opened a US flagship store in 2026",
        claim_type=ClaimType.VERIFIED_FACT,
        status=ClaimStatus.VERIFIED,
    )
    c.id = 1
    return c


def _ctx(*, with_trigger: bool = True, variant: str = "A") -> DraftContext:
    claim = _claim() if with_trigger else None
    return DraftContext(
        account_id=1,
        account_name="Meridian Apparel",
        first_name="Ada",
        segment="apparel",
        region="US",
        wedge=WEDGE,
        sender=SENDER,
        variant=variant,
        usable_claim_ids=[1] if with_trigger else [],
        trigger_claim=claim,
    )


def test_variant_is_stable_per_account() -> None:
    variants = ["A", "B", "C"]
    assert assign_variant(42, variants) == assign_variant(42, variants)  # stable
    # account-level: same account always same variant (used across every step)


def test_sequence_has_six_coherent_outputs() -> None:
    seq = build_sequence(_ctx(variant="B"), CFG)
    assert set(seq) == {
        "champion_first_email",
        "champion_followup",
        "exec_sponsor_escalation",
        "final_close_the_loop",
        "linkedin_connection_note",
        "warm_intro_request",
    }
    assert {d.variant for d in seq.values()} == {"B"}  # coherent across all steps


def test_first_email_with_trigger_references_claim_and_validates() -> None:
    draft = champion_first_email(_ctx(with_trigger=True), CFG)
    assert draft.evidence_claim_ids == [1]
    assert validate_draft(draft, [1], CFG, is_first_email=True) == []


def test_first_email_without_trigger_uses_role_relevant_no_claim() -> None:
    draft = champion_first_email(_ctx(with_trigger=False), CFG)
    assert draft.evidence_claim_ids == []
    assert validate_draft(draft, [], CFG, is_first_email=True) == []


def _bad(body: str, **kw: object) -> Draft:
    return Draft("champion_first_email", "s", body, kw.get("ids", []), "A")  # type: ignore[arg-type]


def test_validator_flags_missing_optout_and_cta() -> None:
    v = validate_draft(_bad("Hi there, just a plain line."), [], CFG)
    assert any("opt-out" in x for x in v) and any("CTA" in x for x in v)


def test_validator_flags_banned_phrase() -> None:
    v = validate_draft(_bad("Quick question? opt out here"), [], CFG)
    assert any("banned phrase" in x for x in v)


def test_validator_flags_excessive_links() -> None:
    body = "See https://a.example.com and https://b.example.com ? opt out"
    assert any("too many links" in x for x in validate_draft(_bad(body), [], CFG))


def test_validator_flags_unsupported_claim() -> None:
    d = Draft("champion_first_email", "s", "Congrats? opt out", [99], "A")
    assert any("unsupported claim" in x for x in validate_draft(d, [1], CFG))


def test_validator_flags_loi_in_first_email() -> None:
    body = "Would you sign an LOI? opt out"
    v = validate_draft(_bad(body), [], CFG, is_first_email=True)
    assert any("LOI" in x for x in v)


def test_validator_flags_unlabeled_time_money_claim() -> None:
    body = "We save you time and money. Interested? opt out"
    assert any("pilot target" in x for x in validate_draft(_bad(body), [], CFG))


def test_validator_flags_tool_usage_assertion() -> None:
    body = "You use spreadsheets for everything, right? opt out"
    assert any("tool usage" in x for x in validate_draft(_bad(body), [], CFG))


def test_validator_flags_html_and_lead_credentials() -> None:
    body = "From Palo Alto: <b>hi</b>. Interested? opt out"
    v = validate_draft(_bad(body), [], CFG)
    assert any("plain text" in x for x in v) and any("banned credential" in x for x in v)
