"""Evidence-grounded outreach drafting engine + deterministic validation.

The copywriter receives ONLY verified evidence (usable claim ids) plus config — never raw
web pages. Message variants are assigned at the ACCOUNT level (stable across every follow-up)
so the narrative stays coherent. Optimize for positive replies / referrals / meetings /
pilot proposals / LOIs — never opens. Every personalized sentence carries an evidence_claim_id.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

from spindle_gtm.config import get_settings
from spindle_gtm.models import EvidenceClaim
from spindle_gtm.qualification.loader import get_app_config
from spindle_gtm.qualification.schemas import AppConfig, PilotWedge

OPTIMIZATION_METRICS = ("positive_reply", "referral", "meeting", "pilot_proposal", "loi")
_URL_RE = re.compile(r"https?://\S+")
_HTML_RE = re.compile(r"</?[a-zA-Z][^>]*>")


@dataclass
class SenderIdentity:
    name: str
    company: str
    postal_address: str
    unsubscribe_url: str


def sender_from_settings() -> SenderIdentity:
    s = get_settings()
    return SenderIdentity(
        name=s.sender_name or "Sender Name",
        company=s.sender_company or "Spindle",
        postal_address=s.sender_postal_address or "123 Example St, City",
        unsubscribe_url=s.unsubscribe_url or "https://example.com/unsubscribe",
    )


@dataclass
class DraftContext:
    account_id: int
    account_name: str
    first_name: str
    segment: str
    region: str
    wedge: PilotWedge
    sender: SenderIdentity
    variant: str
    usable_claim_ids: list[int] = field(default_factory=list)
    trigger_claim: EvidenceClaim | None = None


@dataclass
class Draft:
    message_type: str
    subject: str
    body: str
    evidence_claim_ids: list[int] = field(default_factory=list)
    variant: str = "A"


def assign_variant(account_id: int, variants: list[str], salt: str = "") -> str:
    """Deterministic ACCOUNT-level variant assignment (identical across every step)."""
    digest = hashlib.sha256(f"{salt}:{account_id}".encode()).hexdigest()
    return variants[int(digest, 16) % len(variants)]


def _trigger_line(ctx: DraftContext) -> tuple[str, list[int]]:
    """A verified trigger sentence (with claim id) or role-relevant messaging (no id)."""
    claim = ctx.trigger_claim
    if claim is not None and claim.id in ctx.usable_claim_ids:
        return f"Congrats on {claim.claim.rstrip('.').lower()} — genuinely strong to see.", [
            claim.id
        ]
    return (
        f"I work with {ctx.segment} brands on the operational side of product development.",
        [],
    )


def champion_first_email(ctx: DraftContext, cfg: AppConfig | None = None) -> Draft:
    cfg = cfg or get_app_config()
    trigger, ids = _trigger_line(ctx)
    one_liner = cfg.message_rules.spindle_one_liner
    body = "\n".join(
        [
            f"Hi {ctx.first_name},",
            "",
            trigger,
            f"As the range grows, how does your team keep {ctx.wedge.pain.rstrip('.').lower()} "
            "from slowing product development down?",
            one_liner,
            f"If useful, we could run a small pilot: {ctx.wedge.wedge.rstrip('.').lower()}. "
            "Any time or cost improvement would be a pilot target we measure, not a claim.",
            "Would you be open to a short look in the next couple of weeks?",
            "",
            f"— {ctx.sender.name}, {ctx.sender.company}",
            ctx.sender.postal_address,
            f"Not relevant? Reply 'unsubscribe' or opt out here: {ctx.sender.unsubscribe_url}",
        ]
    )
    return Draft(
        "champion_first_email", f"Product ops at {ctx.account_name}", body, ids, ctx.variant
    )


def champion_followup(ctx: DraftContext, cfg: AppConfig | None = None) -> Draft:
    body = "\n".join(
        [
            f"Hi {ctx.first_name}, following up briefly.",
            f"The pilot idea stands: {ctx.wedge.wedge.rstrip('.').lower()}.",
            "Happy to share a one-page outline if that is easier than a call.",
            "",
            f"— {ctx.sender.name}, {ctx.sender.company}",
            f"Opt out: {ctx.sender.unsubscribe_url}",
        ]
    )
    return Draft(
        "champion_followup", f"Re: Product ops at {ctx.account_name}", body, [], ctx.variant
    )


def exec_sponsor_escalation(ctx: DraftContext, cfg: AppConfig | None = None) -> Draft:
    body = "\n".join(
        [
            f"Hi {ctx.first_name},",
            f"I have been trying to reach the product/operations team at {ctx.account_name} "
            f"about {ctx.wedge.pain.rstrip('.').lower()}.",
            "If this is worth a look, could you point me to the right owner?",
            "",
            f"— {ctx.sender.name}, {ctx.sender.company}",
            f"Opt out: {ctx.sender.unsubscribe_url}",
        ]
    )
    return Draft(
        "exec_sponsor_escalation", f"Quick pointer, {ctx.account_name}?", body, [], ctx.variant
    )


def final_close_the_loop(ctx: DraftContext, cfg: AppConfig | None = None) -> Draft:
    body = "\n".join(
        [
            f"Hi {ctx.first_name}, last note from me on this.",
            "I will close the loop here — if the timing is ever right, the door is open.",
            "",
            f"— {ctx.sender.name}, {ctx.sender.company}",
            f"Opt out: {ctx.sender.unsubscribe_url}",
        ]
    )
    return Draft(
        "final_close_the_loop", f"Closing the loop, {ctx.account_name}", body, [], ctx.variant
    )


def warm_intro_request(ctx: DraftContext, cfg: AppConfig | None = None) -> Draft:
    body = "\n".join(
        [
            f"Hi {ctx.first_name},",
            f"You know the team at {ctx.account_name} — would a quick intro to whoever owns "
            "product operations be reasonable? Happy to send a forwardable blurb.",
            "",
            f"— {ctx.sender.name}, {ctx.sender.company}",
            f"Opt out: {ctx.sender.unsubscribe_url}",
        ]
    )
    return Draft("warm_intro_request", f"Intro at {ctx.account_name}?", body, [], ctx.variant)


def build_sequence(ctx: DraftContext, cfg: AppConfig | None = None) -> dict[str, Draft]:
    """The six coherent, account-variant-consistent outputs."""
    cfg = cfg or get_app_config()
    from spindle_gtm.linkedin import generate_connection_note

    note = generate_connection_note(
        ctx.first_name, ctx.sender.name, max_chars=cfg.message_rules.linkedin_note_max_chars
    )
    return {
        "champion_first_email": champion_first_email(ctx, cfg),
        "champion_followup": champion_followup(ctx, cfg),
        "exec_sponsor_escalation": exec_sponsor_escalation(ctx, cfg),
        "final_close_the_loop": final_close_the_loop(ctx, cfg),
        "linkedin_connection_note": Draft("linkedin_connection_note", "", note, [], ctx.variant),
        "warm_intro_request": warm_intro_request(ctx, cfg),
    }


# --- deterministic validation --------------------------------------------------
def validate_draft(
    draft: Draft,
    usable_claim_ids: list[int],
    cfg: AppConfig | None = None,
    *,
    is_first_email: bool = False,
) -> list[str]:
    cfg = cfg or get_app_config()
    mr = cfg.message_rules
    body = draft.body
    low = body.lower()
    violations: list[str] = []

    if _HTML_RE.search(body):
        violations.append("not plain text (contains HTML)")

    for phrase in [*mr.forbidden_phrases]:
        if phrase.lower() in low:
            violations.append(f"banned phrase: {phrase!r}")

    # Don't LEAD with credentials/geography — check the opening of the message.
    head = body[:200].lower()
    for term in mr.lead_ban_terms:
        if term.lower() in head:
            violations.append(f"leads with banned credential/geography: {term!r}")

    if "?" not in body:
        violations.append("missing CTA (no question)")

    if "opt out" not in low and "unsubscribe" not in low:
        violations.append("missing opt-out language")

    links = _URL_RE.findall(body)
    if len(links) > mr.max_links:
        violations.append(f"too many links: {len(links)} > {mr.max_links}")

    for cid in draft.evidence_claim_ids:
        if cid not in usable_claim_ids:
            violations.append(f"unsupported claim id {cid} (not a verified/usable claim)")

    if "i noticed" in low and not draft.evidence_claim_ids:
        violations.append("'I noticed' used without a verified claim")

    if re.search(r"save (?:you )?(?:time|money)|reduce cost|cut cost|\broi\b", low) and (
        "pilot target" not in low
    ):
        violations.append("time/money claim not labeled as a pilot target")

    if re.search(
        r"you (?:use|are using|rely on|run on) (?:spreadsheets|excel|whatsapp|plm|erp)", low
    ):
        violations.append("asserts specific tool usage (must be a sourced fact or a question)")

    if is_first_email:
        words = len(body.split())
        if not (mr.first_email_min_words <= words <= mr.first_email_max_words):
            violations.append(
                f"first-email word count {words} outside "
                f"[{mr.first_email_min_words}, {mr.first_email_max_words}]"
            )
        if re.search(r"\bloi\b|letter of intent", low):
            violations.append("first email must not request an LOI")

    return violations
