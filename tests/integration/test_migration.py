"""The Alembic migration applies cleanly to a fresh SQLite DB (no network)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

REPO_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_TABLES = {
    "sync_runs",
    "accounts",
    "contacts",
    "account_contact_roles",
    "account_scores",
    "contact_scores",
    "research_sources",
    "research_findings",
    "evidence_claims",
    "evidence_verifications",
    "linkedin_manual_tasks",
    "email_drafts",
    "outreach_batches",
    "outreach_batch_items",
    "approvals",
    "external_action_manifests",
    "external_action_results",
    "activities",
    "experiments",
    "experiment_assignments",
    "suppression_entries",
    "account_locks",
    "discovery_calls",
    "pilot_proposals",
    "loi_records",
}


def test_upgrade_head_creates_all_tables(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("SPINDLE_DB_PATH", str(db_path))

    cfg = Config(str(REPO_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(REPO_ROOT / "migrations"))
    command.upgrade(cfg, "head")

    con = sqlite3.connect(db_path)
    tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    con.close()
    assert tables >= EXPECTED_TABLES
