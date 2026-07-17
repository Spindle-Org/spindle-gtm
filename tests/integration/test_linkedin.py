"""LinkedIn manual task workflow + connection-note generator."""

from __future__ import annotations

import pytest
from sqlmodel import Session

from spindle_gtm.linkedin import (
    create_connection_request_task,
    create_verify_role_task,
    generate_connection_note,
    human_note_for_outreach,
    record_connection_outcome,
    record_role_verification,
)
from spindle_gtm.models import Contact


def test_full_manual_flow(session: Session, contact: Contact) -> None:
    contact.linkedin_url = "https://www.linkedin.com/in/ada"  # stored only, never fetched
    session.commit()

    t1 = create_verify_role_task(session, contact)
    session.commit()
    assert t1.action == "verify_role" and t1.status == "pending"
    assert t1.linkedin_url == "https://www.linkedin.com/in/ada"

    record_role_verification(session, t1, "Head of Production", "Spoke on a supply-chain panel")
    session.commit()
    assert t1.status == "done"
    assert human_note_for_outreach(t1) == "Spoke on a supply-chain panel"

    t2 = create_connection_request_task(session, contact, suggested_text="Hi Ada, ...")
    session.commit()
    record_connection_outcome(session, t2, "ACCEPTED")
    session.commit()
    assert t2.outcome == "ACCEPTED" and t2.status == "done"


def test_invalid_outcome_rejected(session: Session, contact: Contact) -> None:
    task = create_connection_request_task(session, contact)
    with pytest.raises(ValueError, match="outcome must be one of"):
        record_connection_outcome(session, task, "MAYBE")


def test_connection_note_respects_cap() -> None:
    note = generate_connection_note("Ada", "Ayush", max_chars=80)
    assert len(note) <= 80


def test_connection_note_is_not_salesy() -> None:
    note = generate_connection_note("Ada", "Ayush").lower()
    for banned in ("demo", "pilot", "meeting", "buy", "purchase", "sale", "pitch", "discount"):
        assert banned not in note
