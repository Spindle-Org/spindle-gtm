"""LinkedIn as a MANUAL task workflow ONLY.

This module stores an Apollo-provided LinkedIn URL and creates manual review tasks for a
human (Ayush) to action in the browser. It NEVER logs in, scrapes, automates views /
invitations / messages, downloads contact data, or uses any browser-automation library or
undocumented API. It performs NO network I/O of any kind — it only touches the local DB and
generates note text. Downstream outreach uses ONLY the human-entered note. Enforced by
tests/unit/test_linkedin_policy.py and the PreToolUse governance hook.
"""

from __future__ import annotations

from sqlmodel import Session

from spindle_gtm.models import Contact, LinkedinManualTask, utcnow
from spindle_gtm.qualification.loader import get_app_config

# Referenced here only as data for the manual workflow — never fetched.
LINKEDIN_DOMAINS = ("linkedin.com", "lnkd.in")

ACTION_VERIFY_ROLE = "verify_role"
ACTION_CONNECTION_REQUEST = "connection_request"
VALID_OUTCOMES = ("SENT", "ACCEPTED", "DECLINED", "NO_RESPONSE")


def create_verify_role_task(session: Session, contact: Contact) -> LinkedinManualTask:
    """Step 1: create a manual 'Verify current role' task from the stored profile URL."""
    task = LinkedinManualTask(
        account_id=contact.account_id,
        contact_id=contact.id,
        action=ACTION_VERIFY_ROLE,
        linkedin_url=contact.linkedin_url,
        status="pending",
    )
    session.add(task)
    session.flush()
    return task


def record_role_verification(
    session: Session,
    task: LinkedinManualTask,
    confirmed_title: str,
    observation: str,
) -> LinkedinManualTask:
    """Step 3: the human records the confirmed title + one professionally relevant note."""
    task.confirmed_title = confirmed_title
    task.observation = observation
    task.human_note = observation
    task.status = "done"
    task.completed_at = utcnow()
    session.flush()
    return task


def create_connection_request_task(
    session: Session,
    contact: Contact,
    suggested_text: str | None = None,
) -> LinkedinManualTask:
    """Step 4: create a manual 'Send connection request' task (the human sends it)."""
    task = LinkedinManualTask(
        account_id=contact.account_id,
        contact_id=contact.id,
        action=ACTION_CONNECTION_REQUEST,
        linkedin_url=contact.linkedin_url,
        suggested_text=suggested_text,
        status="pending",
    )
    session.add(task)
    session.flush()
    return task


def record_connection_outcome(
    session: Session,
    task: LinkedinManualTask,
    outcome: str,
) -> LinkedinManualTask:
    """Step 6: the human records the connection outcome."""
    if outcome not in VALID_OUTCOMES:
        raise ValueError(f"outcome must be one of {VALID_OUTCOMES}, got {outcome!r}")
    task.outcome = outcome
    task.status = "done"
    task.completed_at = utcnow()
    session.flush()
    return task


def human_note_for_outreach(task: LinkedinManualTask) -> str | None:
    """Downstream outreach may use ONLY the human-entered observation."""
    return task.human_note


def generate_connection_note(
    first_name: str,
    sender_name: str,
    *,
    role_context: str = "product and production teams",
    max_chars: int | None = None,
) -> str:
    """Short, non-salesy connection note, capped at the configured character limit.

    No pitch, no pilot/demo/meeting ask — just a plain reason to connect. The human sends it.
    """
    if max_chars is None:
        max_chars = get_app_config().message_rules.linkedin_note_max_chars
    note = (
        f"Hi {first_name}, I work alongside {role_context} on product operations and "
        f"would value connecting here. — {sender_name}"
    )
    if len(note) <= max_chars:
        return note
    # Trim gracefully to the cap without cutting mid-word.
    trimmed = note[: max_chars - 1].rsplit(" ", 1)[0]
    return f"{trimmed}…"
