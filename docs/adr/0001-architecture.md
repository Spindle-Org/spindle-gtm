# ADR-0001 — Architecture

- Status: Accepted
- Date: 2026-07-17
- Deciders: founder

## Context
Spindle needs to research the first 25–50 accounts and make them outreach-ready,
converting to 3–5 signed LOIs for a free pilot — run by a single founder, fast, and
without an unsafe high-volume automation system. Targets are global, so compliance
gating is first-class.

## Decision
A small, local, single-user pipeline:

- **Language/runtime:** Python 3.12, managed with **uv** (`uv.lock` committed).
- **Package:** src-layout `spindle_gtm`.
- **CLI:** **Typer** — the primary interface; safe-by-default (see ADR-0002).
- **Storage:** local **SQLite** as the operational store; **SQLModel** (SQLAlchemy 2 +
  Pydantic v2) for models; **Alembic** for migrations.
- **System of record:** **Apollo** is authoritative for account/contact data; we snapshot
  it locally (`apollo_id` + `fetched_at`) and never write back.
- **Compliance:** region policy is **data** (`config/region_policy.toml`); a single
  `compliance_gate()` is **code**. Adding a country is a config row.
- **Dashboard:** **Streamlit**, local, read-only, **PII-free** (aggregate/status only).
- **Quality:** ruff, mypy, pytest, pre-commit; CI runs all of them with no external access.

## Consequences
- Minimal infra; portable; easy to back up; low blast radius.
- Not multi-user and not a CRM — intentional (see IMPLEMENTATION_PLAN §16 non-goals).
- Sending infrastructure (cold domains/mailboxes) is deliberately **not** built in this
  foundation; it arrives behind the ADR-0002 gates in a later phase.
