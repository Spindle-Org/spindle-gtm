"""Commercial progression: stage machine, qualification gate, generators, LOI safety."""

from __future__ import annotations

from pathlib import Path

import pytest
from sqlmodel import Session, select

from spindle_gtm.models import Account, AuditLog
from spindle_gtm.progression import (
    DISCOVERY_TEMPLATE,
    LOI_DISCLAIMER,
    STAGES,
    ProgressionError,
    QualificationInput,
    advance_stage,
    generate_all,
    loi_draft,
    qualification_gate,
)


def _qualified() -> QualificationInput:
    return QualificationInput(
        repeated_problem=True,
        named_collection="SS27 Womenswear",
        named_champion="Head of Production",
        named_sponsor_or_budget_path="COO",
        sample_data_available=True,
        measurable_baseline="6h/week status prep",
        pilot_style_count=50,
        bounded_duration_weeks=4,
        success_criteria="status prep under 2h/week for the pilot collection",
        target_start_date="2026-09-01",
        commercial_discussion_intended=True,
    )


# --- stage machine ---------------------------------------------------------------
def test_stages_are_the_specified_eleven() -> None:
    assert len(STAGES) == 11
    assert STAGES[0] == "positive_reply" and STAGES[-1] == "pilot_scheduled"


def test_advance_walks_forward_and_audits(session: Session, account: Account) -> None:
    advance_stage(session, account, "positive_reply", actor="ayush")
    advance_stage(session, account, "discovery_booked", actor="ayush")
    session.commit()
    assert account.commercial_stage == "discovery_booked"
    audits = [a for a in session.exec(select(AuditLog)) if a.action == "stage_advanced"]
    assert len(audits) == 2


def test_skipping_a_stage_raises(session: Session, account: Account) -> None:
    advance_stage(session, account, "positive_reply")
    with pytest.raises(ProgressionError, match="illegal stage transition"):
        advance_stage(session, account, "qualified_opportunity")  # skips discovery


def test_regression_raises(session: Session, account: Account) -> None:
    advance_stage(session, account, "positive_reply")
    advance_stage(session, account, "discovery_booked")
    with pytest.raises(ProgressionError):
        advance_stage(session, account, "positive_reply")


# --- discovery template + gate ----------------------------------------------------
def test_discovery_template_has_all_fifteen_fields() -> None:
    assert len(DISCOVERY_TEMPLATE) == 15
    assert "styles_and_colorways_per_season" in DISCOVERY_TEMPLATE
    assert "legal_and_security_blockers" in DISCOVERY_TEMPLATE


def test_qualification_gate_passes_when_complete() -> None:
    ok, missing = qualification_gate(_qualified())
    assert ok and missing == []


def test_qualification_gate_lists_missing() -> None:
    ok, missing = qualification_gate(QualificationInput())
    assert not ok
    assert "named_champion" in missing and "success_criteria" in missing


def test_pilot_scope_outside_range_needs_justification() -> None:
    inp = _qualified()
    inp.pilot_style_count = 200
    ok, missing = qualification_gate(inp)
    assert not ok and "pilot_scope_30_100_or_justified" in missing
    inp.pilot_scope_justification = "two drops combined; explicitly agreed"
    ok, _ = qualification_gate(inp)
    assert ok


# --- generators + LOI safety -------------------------------------------------------
def test_loi_refuses_unqualified(tmp_path: Path) -> None:
    with pytest.raises(ProgressionError, match="qualification gate failed"):
        loi_draft("Acme", QualificationInput(), tmp_path)


def test_loi_is_nonbinding_with_legal_markers(tmp_path: Path) -> None:
    path = loi_draft("Acme Apparel", _qualified(), tmp_path)
    text = path.read_text()
    assert "NON-BINDING" in text
    assert LOI_DISCLAIMER in text  # not legal advice + counsel required
    assert "[LEGAL REVIEW" in text
    assert "REQUIRED BEFORE SIGNATURE" in text


def test_generate_all_produces_six_artifacts(tmp_path: Path) -> None:
    answers = {f: f"answer for {f}" for f in DISCOVERY_TEMPLATE}
    outputs = generate_all("Acme Apparel", "Ada", answers, _qualified(), tmp_path)
    assert set(outputs) == {
        "discovery_brief",
        "demo_plan",
        "pilot_scope",
        "success_metrics",
        "followup_email",
        "loi_draft",
    }
    assert all(p.exists() for p in outputs.values())
    brief = outputs["discovery_brief"].read_text()
    for field_name in DISCOVERY_TEMPLATE:
        assert field_name.replace("_", " ") in brief


def test_generate_all_omits_loi_when_unqualified(tmp_path: Path) -> None:
    answers: dict[str, str] = {}
    outputs = generate_all("Acme", "Ada", answers, QualificationInput(), tmp_path)
    assert "loi_draft" not in outputs
