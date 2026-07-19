"""CRM outreach tracker: the canonical artifact of an Apollo-list outreach batch.

One row per contact, ~50 columns spanning identity, scoring, verified evidence,
drafted copy, compliance status, and send tracking. This module is the *single
source of truth* for the schema so ``tracker template`` and ``tracker validate``
never drift. Filled trackers contain real emails (PII) and MUST stay in the
gitignored ``exports/`` dir — never commit one.

Schema mirrors the proven Spindle_Outreach_System master CSV; see
docs/outreach/TRACKER_SCHEMA.md for column definitions and filter views.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

# The canonical column order. Changing this is a schema change — update
# docs/outreach/TRACKER_SCHEMA.md and the template in the same commit.
COLUMNS: tuple[str, ...] = (
    "contact_id",
    "first_name",
    "last_name",
    "full_name",
    "job_title",
    "company",
    "country",
    "region",
    "email",
    "linkedin",
    "relationship_status",
    "persona",
    "deal_role",
    "primary_use_case",
    "secondary_use_case",
    "icp_score",
    "role_fit_score",
    "trigger_score",
    "evidence_score",
    "reply_potential_score",
    "pilot_potential_score",
    "source_tier",
    "verified_trigger",
    "trigger_source",
    "trigger_publication_date",
    "trigger_access_date",
    "trigger_confidence",
    "safe_interpretation",
    "recommended_sender",
    "recommended_channel",
    "subject_a",
    "subject_b",
    "subject_c",
    "email_1",
    "followup_1",
    "followup_2",
    "followup_3",
    "linkedin_connection_note",
    "linkedin_message",
    "positive_reply_message",
    "referral_message",
    "legal_review_status",
    "personalization_review_status",
    "send_status",
    "hold_reason",
    "next_action",
    "owner",
    "last_contacted",
    "reply_status",
    "notes",
)

# Enums for the columns you filter and gate on. Kept deliberately small: only the
# fields the compliance/send workflow depends on are constrained. Everything else
# is free text so a future batch can extend vocabulary without a code change.
ENUMS: dict[str, frozenset[str]] = {
    "region": frozenset({"US", "UK", "EU", "CA", "IN", "KR", "JP"}),
    "source_tier": frozenset({"A", "B", "C", "D", "E"}),
    "trigger_confidence": frozenset({"high", "medium", "low", ""}),
    "legal_review_status": frozenset({"not-required", "pending", "cleared", "hold", ""}),
    "personalization_review_status": frozenset({"pending", "pass", "fail", ""}),
    "send_status": frozenset(
        {"hold", "draft", "ready", "approved", "sent", "replied", "bounced", ""}
    ),
    "reply_status": frozenset(
        {"none", "positive", "negative", "neutral", "ooo", "referral", "unsubscribe", "bounce", ""}
    ),
}

# A send-ready row (send_status in this set) must carry copy + compliance fields.
_SEND_READY = frozenset({"ready", "approved", "sent"})
_REQUIRED_WHEN_READY = ("subject_a", "email_1", "recommended_sender")


@dataclass
class Issue:
    """One validation problem. ``row`` is 1-based over data rows (0 = header)."""

    row: int
    column: str
    message: str

    def __str__(self) -> str:
        where = "header" if self.row == 0 else f"row {self.row}"
        col = f" [{self.column}]" if self.column else ""
        return f"{where}{col}: {self.message}"


def template_row() -> dict[str, str]:
    """An illustrative row using example.com — safe to show/commit as a sample."""
    row = dict.fromkeys(COLUMNS, "")
    row.update(
        contact_id="SP001",
        first_name="Alex",
        last_name="Rivera",
        full_name="Alex Rivera",
        job_title="Head of Product Development",
        company="Example Apparel Co",
        country="United States",
        region="US",
        email="alex.rivera@example.com",
        relationship_status="cold",
        persona="Merchandising/Planning",
        deal_role="Operational champion",
        primary_use_case="multichannel_assortment_coordination",
        icp_score="8",
        role_fit_score="7",
        trigger_score="8",
        evidence_score="8",
        reply_potential_score="7",
        pilot_potential_score="7",
        source_tier="A",
        verified_trigger="Opened a domestic knitting facility (2023) — cite brand source",
        trigger_source="https://example.com/newsroom/knitting-mill",
        trigger_access_date="2026-07-18",
        trigger_confidence="high",
        safe_interpretation="Runs more of the supply chain in-house than peers",
        recommended_sender="Ayush",
        recommended_channel="Email (LinkedIn parallel)",
        subject_a="Assortment Visibility",
        legal_review_status="not-required",
        personalization_review_status="pending",
        send_status="draft",
        next_action="verify trigger, draft email_1",
        owner="Ayush",
        reply_status="none",
    )
    return row


def write_template(path: Path, with_example: bool = True) -> Path:
    """Write an empty tracker (header + optional one example row) to ``path``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS)
        writer.writeheader()
        if with_example:
            writer.writerow(template_row())
    return path


def validate_rows(header: list[str], rows: list[dict[str, str]]) -> list[Issue]:
    """Validate an already-parsed tracker. Pure function — easy to unit test."""
    issues: list[Issue] = []

    missing = [c for c in COLUMNS if c not in header]
    extra = [c for c in header if c not in COLUMNS]
    if missing:
        issues.append(Issue(0, "", f"missing columns: {', '.join(missing)}"))
    if extra:
        issues.append(Issue(0, "", f"unexpected columns: {', '.join(extra)}"))
    if list(header) != list(COLUMNS) and not missing and not extra:
        issues.append(Issue(0, "", "columns present but out of canonical order"))

    for i, row in enumerate(rows, start=1):
        for col, allowed in ENUMS.items():
            val = (row.get(col) or "").strip()
            if val and val not in allowed:
                issues.append(
                    Issue(i, col, f"{val!r} not one of {sorted(v for v in allowed if v)}")
                )
        if (row.get("send_status") or "").strip() in _SEND_READY:
            for col in _REQUIRED_WHEN_READY:
                if not (row.get(col) or "").strip():
                    issues.append(Issue(i, col, "required once send_status is ready/approved/sent"))
        if not (row.get("contact_id") or "").strip():
            issues.append(Issue(i, "contact_id", "row has no contact_id"))
    return issues


def validate_csv(path: Path) -> list[Issue]:
    """Parse and validate a tracker CSV on disk."""
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        header = reader.fieldnames or []
        rows = list(reader)
    return validate_rows(list(header), rows)


def demo() -> None:
    """Self-check: template validates clean; broken rows are caught."""
    good = template_row()
    assert validate_rows(list(COLUMNS), [good]) == [], "template must validate clean"

    bad_enum = {**good, "send_status": "yeeted"}
    assert any(i.column == "send_status" for i in validate_rows(list(COLUMNS), [bad_enum]))

    ready_missing = {**good, "send_status": "ready", "email_1": ""}
    assert any(i.column == "email_1" for i in validate_rows(list(COLUMNS), [ready_missing]))

    dropped = [c for c in COLUMNS if c != "email"]
    assert any("missing columns" in i.message for i in validate_rows(dropped, []))
    print("tracker demo: all checks passed")


if __name__ == "__main__":
    demo()
