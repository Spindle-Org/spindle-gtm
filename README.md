# spindle-gtm
Built for another level of out reach.

A local, single-founder GTM engine: research the first 25–50 accounts, gate compliance,
and send human-approved outreach — converting to 3–5 signed LOIs for a free pilot, **without**
an unsafe high-volume automation system.

Full design: **[docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md)** ·
ADRs: [0001 architecture](docs/adr/0001-architecture.md),
[0002 external-action safety](docs/adr/0002-external-action-safety.md).

## Stack
Python 3.12 + [uv](https://docs.astral.sh/uv/) · Typer CLI · SQLModel / SQLAlchemy 2 · Alembic ·
Pydantic v2 · Streamlit (local dashboard) · ruff · mypy · pytest · pre-commit.

## Safety invariants (non-negotiable — see ADR-0002)
- **Apollo is the system of record and READ-ONLY** from this tool. Never written back.
- **No send without `--apply` AND a human batch-approval gate.** CLI is dry-run by default.
- **No LinkedIn automation** — manual, human-in-the-loop only.
- **Compliance gate per region**; **suppression wins over everything**.
- **PII stays local.** `data/`, `db/`, `exports/`, `.env*`, `.csv` are gitignored; a guard +
  CI fail on real-looking emails or exports. Test emails use `example.com`.

## Quickstart
```sh
uv sync
cp .env.example .env                       # fill in secrets; never commit .env
uv run alembic upgrade head                # create local db/spindle.db (gitignored)
uv run spindle --help
uv run spindle regions                     # list region compliance policies
uv run spindle gate CA --unsubscribe --physical-address
uv run streamlit run src/spindle_gtm/dashboard.py
```

## Develop
```sh
uv run ruff format . && uv run ruff check . && uv run mypy && uv run pytest
uv run pre-commit install                  # enable local hooks
```
Also enable GitHub **secret scanning + push protection** (Settings → Security).
Work in small commits on a feature branch; never push directly to `main`.
