"""The Alembic migration applies cleanly to a fresh SQLite DB (no network)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

REPO_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_TABLES = {
    "account",
    "contact",
    "domain",
    "mailbox",
    "sender",
    "batch",
    "message",
    "event",
    "suppression",
    "outcome",
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
