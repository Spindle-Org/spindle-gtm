"""SQLModel data model. Local SQLite is the operational store; Apollo is the
system of record for account/contact data (snapshotted here, never written back).

See docs/IMPLEMENTATION_PLAN.md §7 and docs/adr/0001.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from sqlmodel import Field, SQLModel


class ColdEmailPolicy(StrEnum):
    YES = "yes"
    CAUTION = "caution"
    NO = "no"


class AccountStatus(StrEnum):
    PULLED = "pulled"
    RESEARCHING = "researching"
    RESEARCH_READY = "research_ready"
    IN_BATCH = "in_batch"
    CONTACTED = "contacted"
    ENGAGED = "engaged"
    WON = "won"
    DISQUALIFIED = "disqualified"


class ContactStatus(StrEnum):
    NEW = "new"
    ENRICHED = "enriched"
    GATE_PENDING = "gate_pending"
    GATE_PASSED = "gate_passed"
    DRAFTED = "drafted"
    APPROVED = "approved"
    SENT = "sent"
    REPLIED = "replied"
    BOUNCED = "bounced"
    UNSUBSCRIBED = "unsubscribed"
    SUPPRESSED = "suppressed"


class BatchStatus(StrEnum):
    OPEN = "open"
    ASSEMBLED = "assembled"
    GATED = "gated"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    SENDING = "sending"
    SENT = "sent"
    CLOSED = "closed"


class Domain(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    domain: str = Field(unique=True, index=True)
    status: str = Field(default="warming")
    warmup_started_at: datetime | None = None
    reputation_notes: str | None = None


class Mailbox(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    domain_id: int = Field(foreign_key="domain.id")
    address: str = Field(unique=True, index=True)
    daily_cap: int = 20
    sent_today: int = 0
    warmup_stage: int = 0
    status: str = Field(default="warming")
    provider_ref: str | None = None


class Sender(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    founder: bool = True
    mailbox_id: int | None = Field(default=None, foreign_key="mailbox.id")


class Account(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    apollo_id: str | None = Field(default=None, unique=True, index=True)
    name: str
    domain: str | None = None
    industry: str | None = None
    size: str | None = None
    hq_country: str | None = None
    region_code: str | None = Field(default=None, index=True)
    stage: str | None = None
    research_notes: str | None = None
    fetched_at: datetime | None = None
    status: str = Field(default=AccountStatus.PULLED)


class Contact(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    account_id: int = Field(foreign_key="account.id", index=True)
    apollo_id: str | None = Field(default=None, unique=True, index=True)
    first_name: str | None = None
    last_name: str | None = None
    title: str | None = None
    email: str | None = Field(default=None, index=True)
    email_status: str | None = None  # verified | guessed
    linkedin_url: str | None = None
    region_code: str | None = Field(default=None, index=True)
    consent_basis: str | None = None
    fetched_at: datetime | None = None
    status: str = Field(default=ContactStatus.NEW)
    suppressed_reason: str | None = None


class Batch(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    created_at: datetime
    size: int = 0
    approved_by: int | None = Field(default=None, foreign_key="sender.id")
    approved_at: datetime | None = None
    status: str = Field(default=BatchStatus.OPEN)


class Message(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    contact_id: int = Field(foreign_key="contact.id", index=True)
    batch_id: int = Field(foreign_key="batch.id", index=True)
    sender_id: int = Field(foreign_key="sender.id")
    channel: str = Field(default="email")  # email | linkedin_manual
    subject: str | None = None
    body: str | None = None
    status: str = Field(default="draft")
    gate_result: str | None = None
    scheduled_at: datetime | None = None
    sent_at: datetime | None = None
    provider_msg_id: str | None = None


class Event(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    message_id: int | None = Field(default=None, foreign_key="message.id")
    contact_id: int | None = Field(default=None, foreign_key="contact.id", index=True)
    type: str
    payload: str | None = None
    occurred_at: datetime


class Suppression(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    email: str | None = Field(default=None, index=True)
    domain: str | None = Field(default=None, index=True)
    scope: str = Field(default="email")  # email | domain
    reason: str
    created_at: datetime


class Outcome(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    account_id: int = Field(foreign_key="account.id", index=True)
    meeting_at: datetime | None = None
    loi_status: str | None = None  # none | sent | signed | declined
    loi_signed_at: datetime | None = None
