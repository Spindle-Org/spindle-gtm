"""Doctor checks — Apollo calls are mocked; nothing hits the network or spends credits."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from spindle_gtm import doctor


def _fake_whoami(returncode: int) -> subprocess.CompletedProcess[str]:
    # Uses example.com so no real identity ever appears in tests.
    return subprocess.CompletedProcess(
        args=["apollo", "auth", "whoami"],
        returncode=returncode,
        stdout="Logged in as Test User (test@example.com)" if returncode == 0 else "",
        stderr="",
    )


def test_apollo_auth_ok_is_sanitized(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(doctor.shutil, "which", lambda _: "/usr/bin/apollo")
    monkeypatch.setattr(doctor, "_apollo_whoami", lambda: _fake_whoami(0))
    result = doctor.check_apollo_auth()
    assert result.ok
    assert "example.com" not in result.detail  # identity must not leak into output


def test_apollo_auth_not_logged_in(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(doctor.shutil, "which", lambda _: "/usr/bin/apollo")
    monkeypatch.setattr(doctor, "_apollo_whoami", lambda: _fake_whoami(1))
    assert not doctor.check_apollo_auth().ok


def test_apollo_auth_missing_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(doctor.shutil, "which", lambda _: None)
    r = doctor.check_apollo_auth()
    assert not r.ok and "not installed" in r.detail


def test_apollo_mcp_detects_server(tmp_path: Path) -> None:
    (tmp_path / ".mcp.json").write_text('{"mcpServers": {"apollo": {"type": "http"}}}')
    assert doctor.check_apollo_mcp(tmp_path).ok


def test_apollo_mcp_missing(tmp_path: Path) -> None:
    assert not doctor.check_apollo_mcp(tmp_path).ok


def test_kill_switch_engaged_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OUTBOUND_ENABLED", raising=False)
    assert doctor.check_kill_switch().ok  # default False => engaged


def test_kill_switch_disengaged_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OUTBOUND_ENABLED", "true")
    r = doctor.check_kill_switch()
    assert not r.ok and "LIVE" in r.detail


def test_no_tracked_secrets_flags_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(doctor, "_git_tracked", lambda _: [".env", "src/app.py"])
    assert not doctor.check_no_tracked_secrets(Path(".")).ok


def test_no_tracked_secrets_clean(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        doctor, "_git_tracked", lambda _: [".env.example", "src/app.py", "db/.gitkeep"]
    )
    assert doctor.check_no_tracked_secrets(Path(".")).ok


def test_run_all_returns_all_checks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(doctor.shutil, "which", lambda _: "/usr/bin/apollo")
    monkeypatch.setattr(doctor, "_apollo_whoami", lambda: _fake_whoami(0))
    monkeypatch.setattr(doctor, "_git_tracked", lambda _: ["src/app.py"])
    names = {r.name for r in doctor.run_all()}
    assert names == {
        "apollo_cli_installed",
        "apollo_auth_valid",
        "apollo_mcp_visible",
        "database_reachable",
        "config_valid",
        "no_tracked_pii",
        "no_tracked_secrets",
        "outbound_kill_switch",
    }
