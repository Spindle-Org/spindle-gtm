#!/usr/bin/env python3
"""PreToolUse governance hook for Claude Code (v2.1.x).

Reads the hook JSON on stdin, classifies the tool call with the deterministic
policy in ``spindle_gtm.policy``, logs external-write attempts (including denials),
and emits a permission decision. Fail-safe: any internal error defers to Claude
Code's normal permission flow rather than bricking the session.

Wiring: .claude/settings.json -> hooks.PreToolUse. Verify with /hooks.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from spindle_gtm.policy import Action, classify, manifest_present  # noqa: E402

LOG_PATH = REPO_ROOT / "logs" / "external-attempts.log"


def _log(tool_name: str, decision: object, extra: dict[str, object]) -> None:
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "ts": datetime.now(UTC).isoformat(),
            "tool_name": tool_name,
            **extra,
        }
        with LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
    except OSError:
        pass  # logging must never block a decision


def _emit(permission_decision: str, reason: str) -> None:
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": permission_decision,
                    "permissionDecisionReason": reason,
                }
            }
        )
    )


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0  # can't parse — defer to normal permissions

    tool_name = str(payload.get("tool_name", ""))
    tool_input = payload.get("tool_input") or {}
    cwd = payload.get("cwd") or str(REPO_ROOT)

    try:
        decision = classify(tool_name, tool_input, manifest_ok=manifest_present(cwd))
    except Exception:  # noqa: BLE001 — never brick the session on a guard bug
        return 0

    # Log every attempted external write and every denial.
    if decision.is_external_write or decision.action == Action.DENY:
        _log(
            tool_name,
            decision,
            {
                "action": decision.action.value,
                "category": decision.category,
                "reason": decision.reason,
                "external_write": decision.is_external_write,
            },
        )

    if decision.action == Action.DENY:
        _emit("deny", decision.reason)
    elif decision.action == Action.ASK:
        _emit("ask", decision.reason)
    # passthrough: emit nothing, exit 0 -> normal permission flow applies.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
