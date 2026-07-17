# CLAUDE.md — spindle-gtm

Guidance for Claude Code (and any agent) working in this repo. These rules are
**binding**; they encode the safety posture in `docs/adr/0002`.

## What this is
A local, single-founder GTM engine: research accounts, gate compliance, and send
human-approved outreach. Stack: Python 3.12 + uv, Typer CLI, SQLModel/SQLAlchemy 2,
Alembic, Pydantic v2, Streamlit dashboard. See `docs/IMPLEMENTATION_PLAN.md`.

## Non-negotiable rules
1. **Apollo is the system of record and is READ-ONLY from this tool.** Never create or
   update Apollo accounts, contacts, sequences, or campaigns. Read + snapshot only
   (`apollo_id` + `fetched_at`); never write back and never treat local data as authoritative
   over Apollo for account/contact facts.
2. **No LinkedIn automation, ever.** LinkedIn is manual, human-in-the-loop only — no API,
   no scraping, no automated connects/messages. You may only draft text a human sends.
3. **Evidence is required for personalization.** Every personalized claim must reference
   concrete evidence (source + fetched_at) stored with it. Do not invent facts about a
   person or company to personalize a message.
4. **Explicit human approval for every external write.** Any action that leaves the
   machine (Apollo call, email send) is dry-run unless `--apply` AND a batch-level human
   approval gate are both satisfied. Never add a code path that sends without approval.

## Working rules
- Keep PII out of git: never commit `data/`, `db/`, `exports/`, `.env*`, or `.csv`. Test
  emails MUST use `example.com`. The `no-pii-leak` guard and CI enforce this.
- The CLI is safe-by-default (dry-run). Preserve that: new external actions gate on `--apply`.
- Region compliance is data (`config/region_policy.toml`) + one gate (`compliance.py`).
  Add regions as config rows; don't scatter region logic.
- Before committing: `uv run ruff format . && uv run ruff check . && uv run mypy && uv run pytest`.
- Migrations: `uv run alembic revision --autogenerate -m "..."` then review the generated file.
- Commit style: small, reviewable commits. Never push directly to `main`; open a PR.
- Do not connect Apollo or wire up sending without an explicit instruction to do so.
