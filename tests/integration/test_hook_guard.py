"""The PreToolUse hook wrapper adapts stdin JSON -> permission decision JSON."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GUARD = REPO_ROOT / ".claude" / "hooks" / "pretooluse_guard.py"


def _run(payload: dict) -> str:
    proc = subprocess.run(
        [sys.executable, str(GUARD)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=True,
    )
    return proc.stdout


def test_deny_emits_deny_decision() -> None:
    out = _run(
        {
            "hook_event_name": "PreToolUse",
            "tool_name": "mcp__apollo__apollo_emailer_messages_send_now",
            "tool_input": {},
            "cwd": str(REPO_ROOT),
        }
    )
    decision = json.loads(out)["hookSpecificOutput"]
    assert decision["permissionDecision"] == "deny"
    assert decision["hookEventName"] == "PreToolUse"


def test_apollo_write_emits_ask() -> None:
    out = _run(
        {
            "tool_name": "mcp__apollo__apollo_contacts_create",
            "tool_input": {},
            "cwd": str(REPO_ROOT),
        }
    )
    assert json.loads(out)["hookSpecificOutput"]["permissionDecision"] == "ask"


def test_passthrough_emits_nothing() -> None:
    out = _run({"tool_name": "Bash", "tool_input": {"command": "ls"}, "cwd": str(REPO_ROOT)})
    assert out.strip() == ""


def test_malformed_stdin_defers() -> None:
    proc = subprocess.run(
        [sys.executable, str(GUARD)],
        input="not json",
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=True,
    )
    assert proc.returncode == 0
    assert proc.stdout.strip() == ""
