"""SQLModel domain model (see docs/IMPLEMENTATION_PLAN.md §7, docs/adr/0001).

The local database is a research cache, decision log, experiment store, and audit
layer — **not** the commercial system of record (Apollo is). Principles:
- Apollo IDs are external identifiers (``apollo_id``), never our primary key.
- Human ``notes`` are preserved and never overwritten by sync (see domain.upsert_*).
- Every record has created_at/updated_at; synced records add source/source_updated_at.
- Every external action carries a deterministic idempotency key + payload hash, and
  approvals bind to an immutable manifest hash (domain.py).
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, Index, UniqueConstraint
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(UTC)


# --- enums ---------------------------------------------------------------------
class ColdEmailPolicy(StrEnum):
    YES = "yes"
    CAUTION = "caution"
    NO = "no"


class ActionState(StrEnum):
    PLANNED = "PLANNED"
    REVIEWED = "REVIEWED"
    APPROVED = "APPROVED"
    APPLYING = "APPLYING"
    APPLIED = "APPLIED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class AccountLockState(StrEnum):
    OPEN = "OPEN"
    REPLIED = "REPLIED"
    MEETING_SET = "MEETING_SET"
    DO_NOT_CONTACT = "DO_NOT_CONTACT"
    LEGAL_HOLD = "LEGAL_HOLD"


class BatchStatus(StrEnum):
    DRAFT = "DRAFT"
    REVIEW = "REVIEW"
    APPROVED = "APPROVED"
    APPLIED = "APPLIED"
    CANCELLED = "CANCELLED"


class DraftStatus(StrEnum):
    DRAFT = "DRAFT"
    SEND_READY = "SEND_READY"
    HELD = "HELD"
    SENT = "SENT"


class ClaimStatus(StrEnum):
    UNVERIFIED = "UNVERIFIED"
    VERIFIED = "VERIFIED"
    CONTRADICTED = "CONTRADICTED"


class SyncStatus(StrEnum):
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


def _states(enum: type[StrEnum]) -> str:
    return ", ".join(f"'{m.value}'" for m in enum)


# --- bases ---------------------------------------------------------------------
class Base(SQLModel):
    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=utcnow, nullable=False)
    updated_at: datetime = Field(
        default_factory=utcnow, sa_column_kwargs={"onupdate": utcnow}, nullable=False
    )


class SourcedBase(Base):
    """Records synced from an external system carry provenance."""

    source: str = Field(default="apollo", nullable=False)
    source_updated_at: datetime | None = None


# --- sync + core entities ------------------------------------------------------
class SyncRun(Base, table=True):
    __tablename__ = "sync_runs"
    source: str = Field(default="apollo", index=True)
    kind: str  # accounts | contacts | activities | ...
    status: str = Field(default=SyncStatus.RUNNING)
    mode: str | None = None  # A | B
    workspace: str | None = None
    scope_type: str | None = None  # list | stage | csv | saved_view | api
    scope_value: str | None = None
    started_at: datetime = Field(default_factory=utcnow)
    finished_at: datetime | None = None
    stats_json: str | None = None
    __table_args__ = (CheckConstraint(f"status IN ({_states(SyncStatus)})", name="ck_sync_status"),)


class Account(SourcedBase, table=True):
    __tablename__ = "accounts"
    apollo_id: str | None = Field(default=None, unique=True, index=True)
    name: str
    domain: str | None = Field(default=None, index=True)
    industry: str | None = None
    size: str | None = None
    hq_country: str | None = None
    region_code: str | None = Field(default=None, index=True)
    stage: str | None = None
    notes: str | None = None  # human-authored — never overwritten by sync
    qualification_override: str | None = None  # human decision — never overwritten by sync
    active: bool = Field(default=True, index=True)  # sync marks inactive, never deletes
    sync_scope: str | None = None  # list/stage this account was synced from
    last_synced_at: datetime | None = None
    status: str = Field(default="pulled")


class Contact(SourcedBase, table=True):
    __tablename__ = "contacts"
    account_id: int = Field(foreign_key="accounts.id", index=True)
    apollo_id: str | None = Field(default=None, unique=True, index=True)
    first_name: str | None = None
    last_name: str | None = None
    title: str | None = None
    email: str | None = Field(default=None, index=True)
    email_status: str | None = None  # verified | guessed
    linkedin_url: str | None = None
    region_code: str | None = Field(default=None, index=True)
    consent_basis: str | None = None
    notes: str | None = None  # human-authored — never overwritten by sync
    status: str = Field(default="new")


class AccountContactRole(Base, table=True):
    __tablename__ = "account_contact_roles"
    account_id: int = Field(foreign_key="accounts.id", index=True)
    contact_id: int = Field(foreign_key="contacts.id", index=True)
    role: str  # decision_maker | champion | influencer | blocker
    seniority: str | None = None
    __table_args__ = (
        UniqueConstraint("account_id", "contact_id", "role", name="uq_account_contact_role"),
    )


class AccountScore(Base, table=True):
    __tablename__ = "account_scores"
    account_id: int = Field(foreign_key="accounts.id", index=True)
    model: str
    score: float
    rationale: str | None = None
    scored_at: datetime = Field(default_factory=utcnow)


class ContactScore(Base, table=True):
    __tablename__ = "contact_scores"
    contact_id: int = Field(foreign_key="contacts.id", index=True)
    model: str
    score: float
    rationale: str | None = None
    scored_at: datetime = Field(default_factory=utcnow)


# --- research + evidence -------------------------------------------------------
class ResearchSource(SourcedBase, table=True):
    __tablename__ = "research_sources"
    account_id: int | None = Field(default=None, foreign_key="accounts.id", index=True)
    url: str | None = None
    source_type: str  # web | apollo | manual
    title: str | None = None
    fetched_at: datetime | None = None


class ResearchFinding(Base, table=True):
    __tablename__ = "research_findings"
    account_id: int = Field(foreign_key="accounts.id", index=True)
    source_id: int | None = Field(default=None, foreign_key="research_sources.id")
    summary: str
    detail: str | None = None


class EvidenceClaim(Base, table=True):
    __tablename__ = "evidence_claims"
    account_id: int = Field(foreign_key="accounts.id", index=True)
    finding_id: int | None = Field(default=None, foreign_key="research_findings.id")
    claim: str
    status: str = Field(default=ClaimStatus.UNVERIFIED, index=True)
    __table_args__ = (
        CheckConstraint(f"status IN ({_states(ClaimStatus)})", name="ck_claim_status"),
    )


class EvidenceVerification(Base, table=True):
    __tablename__ = "evidence_verifications"
    claim_id: int = Field(foreign_key="evidence_claims.id", index=True)
    verifier: str
    verdict: str  # verified | unverified | contradicted
    note: str | None = None
    source_id: int | None = Field(default=None, foreign_key="research_sources.id")
    verified_at: datetime = Field(default_factory=utcnow)


# --- outreach ------------------------------------------------------------------
class LinkedinManualTask(Base, table=True):
    __tablename__ = "linkedin_manual_tasks"
    account_id: int = Field(foreign_key="accounts.id", index=True)
    contact_id: int = Field(foreign_key="contacts.id", index=True)
    action: str  # connect | message (MANUAL only — never automated)
    suggested_text: str | None = None
    status: str = Field(default="pending")  # pending | done | skipped
    completed_at: datetime | None = None


class EmailDraft(Base, table=True):
    __tablename__ = "email_drafts"
    account_id: int = Field(foreign_key="accounts.id", index=True)
    contact_id: int = Field(foreign_key="contacts.id", index=True)
    batch_id: int | None = Field(default=None, foreign_key="outreach_batches.id", index=True)
    subject: str | None = None
    body: str | None = None
    evidence_claim_ids_json: str | None = None
    gate_result: str | None = None
    status: str = Field(default=DraftStatus.DRAFT, index=True)
    send_ready_at: datetime | None = None
    __table_args__ = (
        CheckConstraint(f"status IN ({_states(DraftStatus)})", name="ck_draft_status"),
    )


class OutreachBatch(Base, table=True):
    __tablename__ = "outreach_batches"
    name: str
    status: str = Field(default=BatchStatus.DRAFT, index=True)  # defaults to DRAFT
    region_scope: str | None = None
    __table_args__ = (
        CheckConstraint(f"status IN ({_states(BatchStatus)})", name="ck_batch_status"),
    )


class OutreachBatchItem(Base, table=True):
    __tablename__ = "outreach_batch_items"
    batch_id: int = Field(foreign_key="outreach_batches.id", index=True)
    draft_id: int = Field(foreign_key="email_drafts.id", index=True)
    contact_id: int = Field(foreign_key="contacts.id", index=True)
    account_id: int = Field(foreign_key="accounts.id", index=True)
    gate_result: str | None = None
    position: int | None = None
    __table_args__ = (UniqueConstraint("batch_id", "draft_id", name="uq_batch_draft"),)


# --- external actions (audit + idempotency) ------------------------------------
class ExternalActionManifest(Base, table=True):
    __tablename__ = "external_action_manifests"
    batch_id: int | None = Field(default=None, foreign_key="outreach_batches.id", index=True)
    action_type: str  # e.g. apollo_label_add, email_send
    idempotency_key: str = Field(unique=True, index=True)
    payload_json: str
    payload_hash: str = Field(index=True)
    manifest_hash: str = Field(index=True)  # immutable content hash; approvals bind to this
    state: str = Field(default=ActionState.PLANNED, index=True)
    __table_args__ = (
        CheckConstraint(f"state IN ({_states(ActionState)})", name="ck_action_state"),
    )


class Approval(Base, table=True):
    __tablename__ = "approvals"
    manifest_id: int = Field(foreign_key="external_action_manifests.id", index=True)
    approved_manifest_hash: str  # snapshot; any manifest change invalidates this approval
    approved_by: str
    approved_at: datetime = Field(default_factory=utcnow)
    revoked_at: datetime | None = None


class ExternalActionResult(Base, table=True):
    __tablename__ = "external_action_results"
    manifest_id: int = Field(foreign_key="external_action_manifests.id", index=True)
    idempotency_key: str = Field(unique=True, index=True)  # one result per action key
    state: str = Field(default=ActionState.APPLIED)
    response_json: str | None = None
    error: str | None = None
    applied_at: datetime = Field(default_factory=utcnow)
    __table_args__ = (
        CheckConstraint(f"state IN ({_states(ActionState)})", name="ck_result_state"),
    )


# --- activities + experiments --------------------------------------------------
class Activity(SourcedBase, table=True):
    __tablename__ = "activities"
    account_id: int = Field(foreign_key="accounts.id", index=True)
    contact_id: int | None = Field(default=None, foreign_key="contacts.id", index=True)
    type: str  # reply | meeting | open | bounce | unsub | ...
    payload_json: str | None = None
    occurred_at: datetime = Field(default_factory=utcnow, index=True)


class Experiment(Base, table=True):
    __tablename__ = "experiments"
    key: str = Field(unique=True, index=True)
    name: str
    hypothesis: str | None = None
    status: str = Field(default="active")


class ExperimentAssignment(Base, table=True):
    __tablename__ = "experiment_assignments"
    experiment_id: int = Field(foreign_key="experiments.id", index=True)
    unit_type: str  # account | contact
    unit_id: int
    variant: str
    assigned_at: datetime = Field(default_factory=utcnow)
    __table_args__ = (
        UniqueConstraint("experiment_id", "unit_type", "unit_id", name="uq_experiment_unit"),
    )


# --- suppression + locks -------------------------------------------------------
class SuppressionEntry(Base, table=True):
    __tablename__ = "suppression_entries"
    email: str | None = None
    domain: str | None = None
    scope: str = Field(default="email")  # email | domain
    reason: str
    source: str = Field(default="manual")
    __table_args__ = (
        Index("uq_suppression_email", "email", unique=True),
        Index("uq_suppression_domain", "domain", unique=True),
    )


class AccountLock(Base, table=True):
    __tablename__ = "account_locks"
    account_id: int = Field(foreign_key="accounts.id", unique=True, index=True)
    state: str = Field(default=AccountLockState.OPEN, index=True)
    reason: str | None = None
    locked_at: datetime = Field(default_factory=utcnow)
    __table_args__ = (
        CheckConstraint(f"state IN ({_states(AccountLockState)})", name="ck_lock_state"),
    )


# --- discovery -> pilot -> LOI -------------------------------------------------
class DiscoveryCall(Base, table=True):
    __tablename__ = "discovery_calls"
    account_id: int = Field(foreign_key="accounts.id", index=True)
    scheduled_at: datetime | None = None
    occurred_at: datetime | None = None
    notes: str | None = None
    outcome: str | None = None


class PilotProposal(Base, table=True):
    __tablename__ = "pilot_proposals"
    account_id: int = Field(foreign_key="accounts.id", index=True)
    discovery_call_id: int | None = Field(default=None, foreign_key="discovery_calls.id")
    status: str = Field(default="draft")  # draft | sent | accepted | declined
    terms_json: str | None = None


class LoiRecord(Base, table=True):
    __tablename__ = "loi_records"
    account_id: int = Field(foreign_key="accounts.id", index=True)
    pilot_proposal_id: int | None = Field(default=None, foreign_key="pilot_proposals.id")
    status: str = Field(default="draft")  # draft | sent | signed | declined
    signed_at: datetime | None = None
    document_ref: str | None = None
