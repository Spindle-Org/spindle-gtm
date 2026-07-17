"""Apollo account synchronization (read-only), Mode A (list/stage/CSV/saved-view) and
Mode B (official saved-accounts search API, paginated with checkpoints).

Rules (docs/adr/0002): reads are safe + retryable; upsert by Apollo account ID; never
delete (mark inactive); never overwrite human notes/qualification overrides; a diff is
produced and bound to an immutable manifest before apply; emails/PII are redacted from logs.
No live Apollo calls happen in tests/CI — sources are injectable and driven by fixtures.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path
from typing import Any, Protocol

from sqlmodel import Session, select

from spindle_gtm.domain import build_manifest, manifest_hash
from spindle_gtm.models import (
    Account,
    ActionState,
    ExternalActionManifest,
    ExternalActionResult,
    SyncRun,
    SyncStatus,
    utcnow,
)

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_PII_KEYS = {
    "email",
    "personal_email",
    "phone",
    "mobile",
    "direct_phone",
    "first_name",
    "last_name",
}


# --- normalized record + scope -------------------------------------------------
@dataclass
class AccountRecord:
    apollo_account_id: str
    name: str
    domain: str | None = None
    industry: str | None = None
    headcount: int | None = None
    region_code: str | None = None
    stage: str | None = None
    source_updated_at: str | None = None


@dataclass
class SyncScope:
    mode: str  # "A" | "B"
    scope_type: str  # list | stage | csv | saved_view | api
    scope_value: str
    workspace: str | None = None


class AccountSource(Protocol):
    scope: SyncScope

    def fetch(self) -> Iterator[AccountRecord]: ...


# --- redaction (logs must never contain emails/PII) ----------------------------
def redact_text(text: str) -> str:
    return _EMAIL_RE.sub("<redacted-email>", text)


def redact_mapping(data: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in data.items():
        if key.lower() in _PII_KEYS:
            out[key] = "<redacted>"
        elif isinstance(value, str):
            out[key] = redact_text(value)
        else:
            out[key] = value
    return out


# --- retry (reads are safe + retryable) ----------------------------------------
def with_retries(
    fn: Callable[[], Any], attempts: int = 3, on_error: Callable[[Exception], None] | None = None
) -> Any:
    last: Exception | None = None
    for _ in range(attempts):
        try:
            return fn()
        except (OSError, ValueError, RuntimeError) as exc:  # transient read errors
            last = exc
            if on_error:
                on_error(exc)
    raise last if last else RuntimeError("with_retries: no attempts made")


# --- sources -------------------------------------------------------------------
@dataclass
class FixtureAccountSource:
    """In-memory source for tests / recorded fixtures."""

    records: list[AccountRecord]
    scope: SyncScope

    def fetch(self) -> Iterator[AccountRecord]:
        yield from self.records


_CSV_ID_KEYS = ("apollo account id", "account id", "id")
_CSV_NAME_KEYS = ("account", "company", "name", "company name")
_CSV_DOMAIN_KEYS = ("domain", "website", "primary domain")
_CSV_SIZE_KEYS = ("# employees", "employees", "headcount", "num employees")
_CSV_INDUSTRY_KEYS = ("industry",)
_CSV_STAGE_KEYS = ("stage", "account stage")
_CSV_COUNTRY_KEYS = ("country", "region")


def _pick(row: dict[str, str], keys: tuple[str, ...]) -> str | None:
    lower = {k.lower().strip(): v for k, v in row.items()}
    for k in keys:
        if lower.get(k):
            return lower[k]
    return None


def _record_from_csv_row(row: dict[str, str]) -> AccountRecord | None:
    apollo_id = _pick(row, _CSV_ID_KEYS)
    name = _pick(row, _CSV_NAME_KEYS)
    if not apollo_id or not name:
        return None
    size = _pick(row, _CSV_SIZE_KEYS)
    headcount = int(re.sub(r"[^0-9]", "", size)) if size and re.search(r"\d", size) else None
    return AccountRecord(
        apollo_account_id=apollo_id,
        name=name,
        domain=_pick(row, _CSV_DOMAIN_KEYS),
        industry=_pick(row, _CSV_INDUSTRY_KEYS),
        headcount=headcount,
        region_code=_pick(row, _CSV_COUNTRY_KEYS),
        stage=_pick(row, _CSV_STAGE_KEYS),
    )


@dataclass
class CsvAccountSource:
    """Mode A: an Apollo CSV export / saved-company view."""

    path: Path
    scope: SyncScope

    def fetch(self) -> Iterator[AccountRecord]:
        import csv

        with self.path.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                record = _record_from_csv_row(row)
                if record is not None:
                    yield record


def _record_from_api(obj: dict[str, Any]) -> AccountRecord:
    return AccountRecord(
        apollo_account_id=str(obj.get("id") or obj.get("account_id") or ""),
        name=str(obj.get("name") or obj.get("organization_name") or ""),
        domain=obj.get("domain") or obj.get("primary_domain"),
        industry=obj.get("industry"),
        headcount=obj.get("estimated_num_employees") or obj.get("headcount"),
        region_code=obj.get("country") or obj.get("region"),
        stage=obj.get("stage"),
        source_updated_at=obj.get("updated_at"),
    )


PageFetcher = Callable[[int], dict[str, Any]]


@dataclass
class ApolloApiAccountSource:
    """Mode B: official saved-accounts search endpoint, paginated with checkpoints.

    ``fetch_page(page)`` returns the raw JSON page; injected so tests use recorded
    fixtures and CI never calls Apollo. ``checkpoint`` persists the last completed page.
    """

    fetch_page: PageFetcher
    scope: SyncScope
    checkpoint: dict[str, int] = field(default_factory=dict)
    max_pages: int = 100

    def fetch(self) -> Iterator[AccountRecord]:
        page = self.checkpoint.get(self.scope.scope_value, 0) + 1
        for _ in range(self.max_pages):
            resp = with_retries(partial(self.fetch_page, page))
            for obj in resp.get("accounts", []):
                record = _record_from_api(obj)
                if record.apollo_account_id:
                    yield record
            self.checkpoint[self.scope.scope_value] = page  # checkpoint after each page
            pagination = resp.get("pagination", {})
            total_pages = int(pagination.get("total_pages", page))
            if page >= total_pages:
                break
            page += 1


# --- diff ----------------------------------------------------------------------
_SOURCED_FIELDS = ("name", "domain", "industry", "region_code", "stage")


@dataclass
class AccountDiff:
    added: list[AccountRecord]
    updated: list[tuple[Account, AccountRecord, dict[str, Any]]]
    unchanged: list[Account]
    inactivated: list[Account]

    def summary(self, scope: SyncScope) -> dict[str, Any]:
        return {
            "scope": {"type": scope.scope_type, "value": scope.scope_value, "mode": scope.mode},
            "added": sorted(r.apollo_account_id for r in self.added),
            "updated": sorted(ex.apollo_id or "" for ex, _, _ in self.updated),
            "inactivated": sorted(a.apollo_id or "" for a in self.inactivated),
            "unchanged_count": len(self.unchanged),
        }


def _size_str(record: AccountRecord) -> str | None:
    return str(record.headcount) if record.headcount is not None else None


def _changed_fields(existing: Account, record: AccountRecord) -> dict[str, Any]:
    changed: dict[str, Any] = {}
    for f in _SOURCED_FIELDS:
        new = getattr(record, f)
        if new is not None and getattr(existing, f) != new:
            changed[f] = new
    size = _size_str(record)
    if size is not None and existing.size != size:
        changed["size"] = size
    return changed


def compute_diff(
    session: Session, records: Iterable[AccountRecord], scope: SyncScope
) -> AccountDiff:
    incoming = list(records)
    by_id = {r.apollo_account_id: r for r in incoming}
    existing_all = list(session.exec(select(Account)))
    existing_by_apollo = {a.apollo_id: a for a in existing_all if a.apollo_id}

    added: list[AccountRecord] = []
    updated: list[tuple[Account, AccountRecord, dict[str, Any]]] = []
    unchanged: list[Account] = []
    for record in incoming:
        existing = existing_by_apollo.get(record.apollo_account_id)
        if existing is None:
            added.append(record)
            continue
        changed = _changed_fields(existing, record)
        if changed:
            updated.append((existing, record, changed))
        else:
            unchanged.append(existing)

    # Never delete: accounts previously synced from THIS scope but no longer returned
    # are marked inactive.
    inactivated = [
        a
        for a in existing_all
        if a.active and a.sync_scope == scope.scope_value and (a.apollo_id or "") not in by_id
    ]
    return AccountDiff(added=added, updated=updated, unchanged=unchanged, inactivated=inactivated)


# --- plan (dry-run -> manifest) + apply ----------------------------------------
def plan_sync(
    session: Session, source: AccountSource
) -> tuple[AccountDiff, ExternalActionManifest]:
    diff = compute_diff(session, source.fetch(), source.scope)
    payload = diff.summary(source.scope)
    target = f"{source.scope.scope_type}:{source.scope.scope_value}"
    manifest = build_manifest("account_sync", target, payload)
    session.add(manifest)
    session.flush()
    return diff, manifest


def apply_sync(session: Session, source: AccountSource, manifest_id: int) -> SyncRun:
    """Re-verify the plan against the immutable manifest, then apply."""
    manifest = session.get(ExternalActionManifest, manifest_id)
    if manifest is None:
        raise ValueError(f"no manifest {manifest_id}")

    diff = compute_diff(session, source.fetch(), source.scope)
    payload = diff.summary(source.scope)
    target = f"{source.scope.scope_type}:{source.scope.scope_value}"
    if manifest_hash("account_sync", target, payload) != manifest.manifest_hash:
        raise ValueError("sync diff changed since planning — manifest invalidated; re-plan")

    now = utcnow()
    run = SyncRun(
        kind="accounts",
        source="apollo",
        status=SyncStatus.RUNNING,
        mode=source.scope.mode,
        workspace=source.scope.workspace,
        scope_type=source.scope.scope_type,
        scope_value=source.scope.scope_value,
    )
    session.add(run)

    for record in diff.added:
        session.add(
            Account(
                apollo_id=record.apollo_account_id,
                name=record.name,
                domain=record.domain,
                industry=record.industry,
                size=_size_str(record),
                region_code=record.region_code,
                stage=record.stage,
                active=True,
                sync_scope=source.scope.scope_value,
                last_synced_at=now,
                source="apollo",
                source_updated_at=now,
            )
        )
    for existing, _record, changed in diff.updated:
        for attr, value in changed.items():  # sourced fields only — never notes/overrides
            setattr(existing, attr, value)
        existing.active = True
        existing.sync_scope = source.scope.scope_value
        existing.last_synced_at = now
    for existing in diff.inactivated:
        existing.active = False
        existing.last_synced_at = now

    run.status = SyncStatus.SUCCESS
    run.finished_at = now
    run.stats_json = json.dumps(
        {
            "added": len(diff.added),
            "updated": len(diff.updated),
            "inactivated": len(diff.inactivated),
            "unchanged": len(diff.unchanged),
        }
    )
    manifest.state = ActionState.APPLIED
    session.add(
        ExternalActionResult(
            manifest_id=manifest_id,
            idempotency_key=manifest.idempotency_key,
            state=ActionState.APPLIED,
            response_json=run.stats_json,
        )
    )
    return run
