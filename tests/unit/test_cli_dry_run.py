"""The CLI must default to dry-run; external actions only run with --apply."""

from __future__ import annotations

from typer.testing import CliRunner

from spindle_gtm.cli import app

runner = CliRunner()


def test_ingest_is_dry_run_by_default() -> None:
    result = runner.invoke(app, ["ingest"])
    assert result.exit_code == 0
    assert "[dry-run]" in result.stdout


def test_send_is_dry_run_by_default() -> None:
    result = runner.invoke(app, ["send"])
    assert result.exit_code == 0
    assert "[dry-run]" in result.stdout


def test_apply_does_not_silently_send() -> None:
    # --apply on an unwired integration must refuse (non-zero), never pretend success.
    result = runner.invoke(app, ["--apply", "send"])
    assert result.exit_code == 1
    assert "[dry-run]" not in result.stdout


def test_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.stdout.strip()


def test_gate_command_reports_hold() -> None:
    result = runner.invoke(app, ["gate", "KR"])
    assert result.exit_code == 0
    assert "HOLD" in result.stdout
