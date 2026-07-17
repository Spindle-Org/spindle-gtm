# AGENTS.md

This file orients any AI coding agent (Claude Code, Codex, etc.) working in this repo.
**`CLAUDE.md` is the single source of truth for the rules** — read it first and follow it.

## TL;DR safety contract
- **Apollo = system of record, READ-ONLY.** No writes back to Apollo, ever.
- **No LinkedIn automation.** Manual, human-in-the-loop only.
- **Evidence required for personalization.** No invented facts.
- **Human approval for every external write.** Dry-run by default; `--apply` + approval gate.
- **No PII in git.** Test emails use `example.com`; `.csv`/`data/`/`db/`/`exports/`/`.env*` ignored.

## Environment
- Python 3.12, managed by `uv`. Install: `uv sync`. Run CLI: `uv run spindle --help`.
- Quality gates: `uv run ruff format . && uv run ruff check . && uv run mypy && uv run pytest`.
- DB migrations: `uv run alembic upgrade head`.
- Dashboard: `uv run streamlit run src/spindle_gtm/dashboard.py`.

## Conventions
- src-layout package `spindle_gtm`; tests in `tests/{unit,integration}`; fixtures synthetic.
- Small, reviewable commits. Never push to `main`; open a PR (see the PR template checklist).
- Region policy is data in `config/region_policy.toml`; the gate is `compliance.py`.
