# spindle-gtm developer experience. Everything runs locally; nothing writes to Apollo.
.PHONY: setup check test run verify dashboard doctor release-gate migrate help

help:
	@echo "setup        install deps + git hooks (uv sync, pre-commit install)"
	@echo "check        ruff format check + ruff lint + mypy"
	@echo "test         run the pytest suite"
	@echo "run          run the synthetic end-to-end demo (no external writes)"
	@echo "verify       run the full release gate (tests, no-PII/secrets, writes-blocked, e2e)"
	@echo "dashboard    launch the local Streamlit review dashboard"
	@echo "doctor       run the read-only preflight (Apollo CLI/auth/MCP, DB, config, kill switch)"
	@echo "migrate      apply database migrations (alembic upgrade head)"

setup:
	uv sync
	uv run pre-commit install

check:
	uv run ruff format --check .
	uv run ruff check .
	uv run mypy

test:
	uv run pytest

run:
	uv run python -m spindle_gtm.demo

verify:
	bash scripts/release_gate.sh

release-gate: verify

dashboard:
	uv run streamlit run src/spindle_gtm/dashboard.py

doctor:
	uv run spindle-gtm doctor

migrate:
	uv run alembic upgrade head
