"""Outcome analytics with explicit denominators and minimum-sample warnings.

We deliberately do NOT compute or optimize for open rate (tracking is off by default).
Experiment variants are assigned at the ACCOUNT level (outreach.assign_variant) and stay
stable; breakdowns here group by that stored variant.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any

from sqlmodel import Session, select

from spindle_gtm.models import (
    Account,
    AccountContactRole,
    Activity,
    Contact,
    EmailDraft,
    LoiRecord,
    PilotProposal,
    ResearchFinding,
    utcnow,
)

MIN_SAMPLE = 20  # below this, rates carry a low-sample warning

Row = dict[str, Any]


def _naive(dt: datetime) -> datetime:
    """SQLite round-trips datetimes as naive; normalize for safe comparison."""
    return dt.replace(tzinfo=None) if dt.tzinfo else dt


def _rate(numerator: int, denominator: int) -> Row:
    value = round(numerator / denominator, 4) if denominator else None
    row: Row = {"numerator": numerator, "denominator": denominator, "rate": value}
    if denominator < MIN_SAMPLE:
        row["warning"] = f"low sample (n={denominator} < {MIN_SAMPLE})"
    return row


def _activity_counts(session: Session) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for act in session.exec(select(Activity)):
        counts[act.type] += 1
    return counts


def core_metrics(session: Session) -> Row:
    contacts = list(session.exec(select(Contact)))
    with_email = [c for c in contacts if c.email]
    valid_email = [c for c in with_email if c.email_status == "verified"]
    counts = _activity_counts(session)
    sent = counts.get("sent", 0)
    delivered = counts.get("delivered", 0)
    positive = counts.get("positive_reply", 0)
    proposals = len(list(session.exec(select(PilotProposal))))
    lois = list(session.exec(select(LoiRecord)))

    return {
        "valid_email_rate": _rate(len(valid_email), len(with_email)),
        "bounce_rate": _rate(counts.get("bounce", 0), sent),
        "positive_reply_rate": _rate(positive, delivered or sent),
        "referral_rate": _rate(counts.get("referral", 0), delivered or sent),
        "meeting_booked_rate": _rate(counts.get("meeting", 0), positive),
        "demo_rate": _rate(counts.get("demo", 0), counts.get("meeting", 0)),
        "pilot_proposal_rate": _rate(proposals, counts.get("meeting", 0)),
        "loi_rate": _rate(len([r for r in lois if r.status == "signed"]), proposals),
        "time_to_first_reply_hours": _time_to_first_reply(session),
    }


def _time_to_first_reply(session: Session) -> float | None:
    """Mean hours from first send to first reply, per account with both."""
    first_sent: dict[int, Any] = {}
    first_reply: dict[int, Any] = {}
    for act in session.exec(select(Activity)):
        stamp = _naive(act.occurred_at)
        if act.type == "sent" and (
            act.account_id not in first_sent or stamp < first_sent[act.account_id]
        ):
            first_sent[act.account_id] = stamp
        elif act.type in {"positive_reply", "negative_reply", "referral"} and (
            act.account_id not in first_reply or stamp < first_reply[act.account_id]
        ):
            first_reply[act.account_id] = stamp
    deltas = [
        (first_reply[a] - first_sent[a]).total_seconds() / 3600
        for a in first_reply
        if a in first_sent and first_reply[a] >= first_sent[a]
    ]
    return round(sum(deltas) / len(deltas), 2) if deltas else None


def _breakdown(session: Session, key_for_contact: dict[int, str]) -> list[Row]:
    """Positive-reply rate grouped by an arbitrary contact -> key mapping."""
    sent: dict[str, int] = defaultdict(int)
    positive: dict[str, int] = defaultdict(int)
    for act in session.exec(select(Activity)):
        if act.contact_id is None:
            continue
        key = key_for_contact.get(act.contact_id)
        if key is None:
            continue
        if act.type == "sent":
            sent[key] += 1
        elif act.type == "positive_reply":
            positive[key] += 1
    return [
        {"group": key, **_rate(positive.get(key, 0), sent.get(key, 0))}
        for key in sorted(set(sent) | set(positive))
    ]


def by_persona(session: Session) -> list[Row]:
    mapping = {
        r.contact_id: r.role
        for r in session.exec(select(AccountContactRole))
        if r.role != "rejected"
    }
    return _breakdown(session, mapping)


def by_segment(session: Session) -> list[Row]:
    accounts = {a.id: a.industry or "unknown" for a in session.exec(select(Account))}
    mapping = {
        c.id: accounts.get(c.account_id, "unknown")
        for c in session.exec(select(Contact))
        if c.id is not None
    }
    return _breakdown(session, mapping)


def by_trigger_type(session: Session) -> list[Row]:
    mapping = {d.contact_id: d.trigger_type or "unknown" for d in session.exec(select(EmailDraft))}
    return _breakdown(session, mapping)


def by_variant(session: Session) -> list[Row]:
    mapping = {d.contact_id: d.variant or "unknown" for d in session.exec(select(EmailDraft))}
    return _breakdown(session, mapping)


def research_time_per_account(session: Session) -> list[Row]:
    """Estimated research span per account (first->last finding timestamp)."""
    spans: dict[int, list[Any]] = defaultdict(list)
    for f in session.exec(select(ResearchFinding)):
        spans[f.account_id].append(f.created_at)
    return [
        {
            "account_id": account_id,
            "research_span_minutes": round((max(stamps) - min(stamps)).total_seconds() / 60, 1),
            "findings": len(stamps),
            "note": "span estimate from finding timestamps",
        }
        for account_id, stamps in sorted(spans.items())
    ]


def summary(session: Session, period: str = "daily") -> Row:
    """Daily/weekly summary with explicit denominators and low-sample warnings."""
    days = 1 if period == "daily" else 7
    cutoff = _naive(utcnow()) - timedelta(days=days)
    recent = [a for a in session.exec(select(Activity)) if _naive(a.occurred_at) >= cutoff]
    recent_counts: dict[str, int] = defaultdict(int)
    for act in recent:
        recent_counts[act.type] += 1
    metrics = core_metrics(session)
    warnings = [
        f"{name}: {value['warning']}"
        for name, value in metrics.items()
        if isinstance(value, dict) and value.get("warning")
    ]
    return {
        "period": period,
        "window_days": days,
        "activity_in_window": dict(recent_counts),
        "cumulative_metrics": metrics,
        "by_persona": by_persona(session),
        "by_segment": by_segment(session),
        "by_trigger_type": by_trigger_type(session),
        "by_variant": by_variant(session),
        "research_time": research_time_per_account(session),
        "low_sample_warnings": warnings,
        "note": "Open rate is intentionally not reported; optimize for replies/meetings/LOIs.",
    }
