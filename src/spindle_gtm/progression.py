"""Commercial progression: positive reply -> signed LOI -> scheduled pilot.

Monotonic 11-stage machine on the account, a structured discovery template, a hard
qualification gate before any LOI, and document generators (briefs, demo plan, pilot
scope, success metrics, follow-up email, non-binding LOI draft).

THE LOI DRAFT IS NOT LEGAL ADVICE. Every generated LOI is explicitly non-binding, marks
fields for legal review, and requires counsel review before signature.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from pathlib import Path

from sqlmodel import Session

from spindle_gtm.config import REPO_ROOT
from spindle_gtm.models import Account, AuditLog

GENERATED_DIR = REPO_ROOT / "generated" / "commercial"

STAGES: tuple[str, ...] = (
    "positive_reply",
    "discovery_booked",
    "discovery_completed",
    "qualified_opportunity",
    "tailored_demo",
    "pilot_scope_drafted",
    "pilot_proposal_sent",
    "loi_drafted",
    "loi_sent",
    "loi_signed",
    "pilot_scheduled",
)

DISCOVERY_TEMPLATE: tuple[str, ...] = (
    "styles_and_colorways_per_season",
    "teams_involved",
    "systems_used",
    "work_in_email_spreadsheets_pdfs_folders_messaging",
    "approval_and_change_process",
    "duplicate_entry",
    "late_error_examples",
    "time_spent_on_status_preparation",
    "live_collection_suitable_for_pilot",
    "users",
    "data_availability",
    "executive_sponsor",
    "budget_owner",
    "legal_and_security_blockers",
    "target_start_date",
)


class ProgressionError(ValueError):
    pass


def advance_stage(
    session: Session, account: Account, new_stage: str, actor: str = "system"
) -> None:
    """Advance exactly one stage forward; skipping or regressing raises."""
    if new_stage not in STAGES:
        raise ProgressionError(f"unknown stage {new_stage!r}")
    current = account.commercial_stage
    expected_index = 0 if current is None else STAGES.index(current) + 1
    if STAGES.index(new_stage) != expected_index:
        raise ProgressionError(
            f"illegal stage transition {current!r} -> {new_stage!r} (next is "
            f"{STAGES[expected_index] if expected_index < len(STAGES) else 'terminal'!r})"
        )
    account.commercial_stage = new_stage
    assert account.id is not None
    session.add(
        AuditLog(
            actor=actor,
            action="stage_advanced",
            entity_type="account",
            entity_id=account.id,
            detail=new_stage,
        )
    )
    session.flush()


# --- qualification gate before LOI ----------------------------------------------
@dataclass
class QualificationInput:
    repeated_problem: bool = False
    named_collection: str = ""
    named_champion: str = ""
    named_sponsor_or_budget_path: str = ""
    sample_data_available: bool = False
    measurable_baseline: str = ""
    pilot_style_count: int = 0
    pilot_scope_justification: str = ""  # required if style count outside 30-100
    bounded_duration_weeks: int = 0
    success_criteria: str = ""
    target_start_date: str = ""
    commercial_discussion_intended: bool = False


def qualification_gate(inp: QualificationInput) -> tuple[bool, list[str]]:
    missing: list[str] = []
    if not inp.repeated_problem:
        missing.append("repeated_problem")
    if not inp.named_collection:
        missing.append("named_collection")
    if not inp.named_champion:
        missing.append("named_champion")
    if not inp.named_sponsor_or_budget_path:
        missing.append("named_sponsor_or_budget_path")
    if not inp.sample_data_available:
        missing.append("sample_data_available")
    if not inp.measurable_baseline:
        missing.append("measurable_baseline")
    if not (30 <= inp.pilot_style_count <= 100) and not inp.pilot_scope_justification:
        missing.append("pilot_scope_30_100_or_justified")
    if inp.bounded_duration_weeks <= 0:
        missing.append("bounded_duration")
    if not inp.success_criteria:
        missing.append("success_criteria")
    if not inp.target_start_date:
        missing.append("target_start_date")
    if not inp.commercial_discussion_intended:
        missing.append("commercial_discussion_intended")
    return (not missing, missing)


# --- generators ------------------------------------------------------------------
def _write(name: str, content: str, out_dir: Path | None = None) -> Path:
    out = out_dir or GENERATED_DIR
    out.mkdir(parents=True, exist_ok=True)
    path = out / name
    path.write_text(content, encoding="utf-8")
    return path


def discovery_brief(
    account_name: str, answers: dict[str, str], out_dir: Path | None = None
) -> Path:
    lines = [f"# Discovery brief — {account_name}", ""]
    for field_name in DISCOVERY_TEMPLATE:
        lines.append(f"## {field_name.replace('_', ' ')}")
        lines.append(answers.get(field_name, "_not yet captured_"))
        lines.append("")
    return _write(
        f"{account_name.lower().replace(' ', '-')}-discovery-brief.md", "\n".join(lines), out_dir
    )


def demo_plan(account_name: str, answers: dict[str, str], out_dir: Path | None = None) -> Path:
    systems = answers.get("systems_used", "their current stack")
    collection = answers.get("live_collection_suitable_for_pilot", "a current collection")
    content = "\n".join(
        [
            f"# Tailored demo plan — {account_name}",
            "",
            f"1. Recreate their flow: {collection} alongside {systems}.",
            "2. Show the pain named in discovery: "
            f"{answers.get('late_error_examples', 'late changes')}.",
            "3. Walk the approval path they described: "
            f"{answers.get('approval_and_change_process', 'approvals')}.",
            "4. End on the pilot scope and success metrics (no feature tour).",
        ]
    )
    return _write(f"{account_name.lower().replace(' ', '-')}-demo-plan.md", content, out_dir)


def pilot_scope(account_name: str, inp: QualificationInput, out_dir: Path | None = None) -> Path:
    content = "\n".join(
        [
            f"# Pilot scope — {account_name}",
            "",
            f"- Collection: {inp.named_collection}",
            f"- Styles: {inp.pilot_style_count}"
            + (
                f" (justification: {inp.pilot_scope_justification})"
                if inp.pilot_scope_justification
                else ""
            ),
            f"- Duration: {inp.bounded_duration_weeks} weeks (bounded)",
            f"- Champion: {inp.named_champion}",
            f"- Sponsor / budget path: {inp.named_sponsor_or_budget_path}",
            f"- Baseline: {inp.measurable_baseline}",
            f"- Target start: {inp.target_start_date}",
        ]
    )
    return _write(f"{account_name.lower().replace(' ', '-')}-pilot-scope.md", content, out_dir)


def success_metric_table(
    inp: QualificationInput, out_dir: Path | None = None, account_name: str = "pilot"
) -> Path:
    content = "\n".join(
        [
            "# Success metrics",
            "",
            "| Metric | Baseline | Target | Measured how |",
            "|--------|----------|--------|--------------|",
            f"| Primary | {inp.measurable_baseline} | {inp.success_criteria} | agreed at kickoff |",
            "| Time/cost improvements | measured during pilot "
            "| pilot targets, not claims | tracked weekly |",
        ]
    )
    return _write(f"{account_name.lower().replace(' ', '-')}-success-metrics.md", content, out_dir)


def followup_email(
    account_name: str, first_name: str, inp: QualificationInput, out_dir: Path | None = None
) -> Path:
    content = "\n".join(
        [
            f"Subject: {account_name} pilot — scope as discussed",
            "",
            f"Hi {first_name},",
            "",
            "Thanks for the discovery conversation. As discussed: a "
            f"{inp.bounded_duration_weeks}-week "
            f"pilot on {inp.named_collection} ({inp.pilot_style_count} styles), success measured "
            f"against: {inp.success_criteria}.",
            "Attached are the pilot scope and success metrics. Does the "
            f"{inp.target_start_date} start still work?",
            "",
            "— (sender identity + opt-out per message rules)",
        ]
    )
    return _write(f"{account_name.lower().replace(' ', '-')}-followup-email.md", content, out_dir)


LOI_DISCLAIMER = (
    "THIS DRAFT IS NOT LEGAL ADVICE. It is a NON-BINDING letter of intent template. "
    "Counsel review is REQUIRED before signature."
)


def loi_draft(account_name: str, inp: QualificationInput, out_dir: Path | None = None) -> Path:
    """Generate the non-binding LOI draft. Refuses unless the qualification gate passes."""
    ok, missing = qualification_gate(inp)
    if not ok:
        raise ProgressionError(f"qualification gate failed; missing: {missing}")
    content = "\n".join(
        [
            f"# NON-BINDING LETTER OF INTENT (DRAFT) — {account_name}",
            "",
            f"> {LOI_DISCLAIMER}",
            "",
            "## Parties",
            f"- Spindle ([LEGAL REVIEW: entity name]) and {account_name} "
            "([LEGAL REVIEW: entity name])",
            "",
            "## Intent",
            f"The parties intend to run a {inp.bounded_duration_weeks}-week pilot on "
            f"{inp.named_collection} (~{inp.pilot_style_count} styles), "
            f"starting {inp.target_start_date}.",
            "",
            "## Success criteria",
            f"{inp.success_criteria} (baseline: {inp.measurable_baseline})",
            "",
            "## Commercial",
            "If success criteria are met, the parties intend to discuss commercial terms "
            "[LEGAL REVIEW: pricing placeholder]. This letter is non-binding and creates no "
            "obligation to proceed.",
            "",
            "## Signatures",
            "[LEGAL REVIEW REQUIRED BEFORE SIGNATURE]",
            f"- {inp.named_sponsor_or_budget_path} — {account_name}",
            "- [Founder] — Spindle",
        ]
    )
    return _write(f"{account_name.lower().replace(' ', '-')}-loi-draft.md", content, out_dir)


def generate_all(
    account_name: str,
    first_name: str,
    answers: dict[str, str],
    inp: QualificationInput,
    out_dir: Path | None = None,
) -> dict[str, Path]:
    """All six artifacts (LOI included only if the gate passes)."""
    outputs = {
        "discovery_brief": discovery_brief(account_name, answers, out_dir),
        "demo_plan": demo_plan(account_name, answers, out_dir),
        "pilot_scope": pilot_scope(account_name, inp, out_dir),
        "success_metrics": success_metric_table(inp, out_dir, account_name),
        "followup_email": followup_email(account_name, first_name, inp, out_dir),
    }
    ok, _ = qualification_gate(inp)
    if ok:
        outputs["loi_draft"] = loi_draft(account_name, inp, out_dir)
    return outputs


def qualification_fields() -> list[str]:
    return [f.name for f in fields(QualificationInput)]
