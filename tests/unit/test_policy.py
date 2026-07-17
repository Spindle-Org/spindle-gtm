"""Governance policy — deterministic classification of tool calls.

Covers each denial/ask category the Claude Code hook enforces (docs/adr/0002).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from spindle_gtm.policy import Action, classify, manifest_present


def _action(tool: str, tool_input: dict[str, object]) -> Action:
    return classify(tool, tool_input).action


# --- credentials ---------------------------------------------------------------
def test_read_env_denied() -> None:
    assert _action("Read", {"file_path": "./.env"}) == Action.DENY


def test_read_env_example_allowed() -> None:
    assert _action("Read", {"file_path": "./.env.example"}) == Action.PASSTHROUGH


def test_cat_env_in_bash_denied() -> None:
    assert _action("Bash", {"command": "cat .env"}) == Action.DENY


def test_ssh_key_denied() -> None:
    assert _action("Read", {"file_path": "/Users/x/.ssh/id_rsa"}) == Action.DENY


@pytest.mark.parametrize(
    "path", ["credentials.json", "~/.aws/credentials", "apollo_oauth.json", "token.json"]
)
def test_credential_files_denied(path: str) -> None:
    assert _action("Read", {"file_path": path}) == Action.DENY


# --- LinkedIn ------------------------------------------------------------------
def test_webfetch_linkedin_denied() -> None:
    assert _action("WebFetch", {"url": "https://www.linkedin.com/in/foo"}) == Action.DENY


def test_bash_curl_linkedin_denied() -> None:
    assert _action("Bash", {"command": "curl -s https://linkedin.com/in/foo"}) == Action.DENY


def test_webfetch_other_domain_ok() -> None:
    assert _action("WebFetch", {"url": "https://example.com/about"}) == Action.PASSTHROUGH


# --- browser automation --------------------------------------------------------
@pytest.mark.parametrize(
    "cmd",
    [
        "npx playwright test",
        "python -m selenium.webdriver",
        "node puppeteer_script.js",
        "chromedriver --port=9515",
        "chrome --headless --remote-debugging-port=9222 --disable-web-security",
    ],
)
def test_browser_automation_denied(cmd: str) -> None:
    assert _action("Bash", {"command": cmd}) == Action.DENY


# --- git add/commit of forbidden content ---------------------------------------
@pytest.mark.parametrize(
    "cmd",
    [
        "git add data/spindle.db",
        "git add -f exports/leads.csv",
        "git commit -m x db/spindle.db",
        "git add contacts.csv",
    ],
)
def test_git_forbidden_denied(cmd: str) -> None:
    assert _action("Bash", {"command": cmd}) == Action.DENY


def test_git_add_source_allowed() -> None:
    assert _action("Bash", {"command": "git add README.md"}) == Action.PASSTHROUGH


# --- Apollo verb classification ------------------------------------------------
def test_apollo_send_denied() -> None:
    d = classify("mcp__apollo__apollo_emailer_messages_send_now", {})
    assert d.action == Action.DENY and d.is_external_write


def test_apollo_sequence_enroll_denied() -> None:
    assert _action("mcp__apollo__apollo_emailer_campaigns_add_contact_ids", {}) == Action.DENY


def test_apollo_create_asks() -> None:
    d = classify("mcp__apollo__apollo_contacts_create", {})
    assert d.action == Action.ASK and d.is_external_write


def test_apollo_read_passthrough() -> None:
    assert _action("mcp__apollo__apollo_contacts_search", {}) == Action.PASSTHROUGH


def test_apollo_unknown_verb_asks() -> None:
    # Forward-safe: an unclassified Apollo tool is treated as a write needing approval.
    assert _action("mcp__apollo__apollo_frobnicate_widget", {}) == Action.ASK


def test_apollo_cli_write_asks() -> None:
    assert _action("Bash", {"command": "apollo contacts create --name x"}) == Action.ASK


# --- Apollo credit-consuming actions (enrich / reveal / match) => ASK -----------
@pytest.mark.parametrize(
    "tool",
    [
        "mcp__apollo__apollo_organizations_enrich",
        "mcp__apollo__apollo_organizations_bulk_enrich",
        "mcp__apollo__apollo_people_match",
        "mcp__apollo__apollo_people_bulk_match",
    ],
)
def test_apollo_credit_mcp_asks(tool: str) -> None:
    d = classify(tool, {})
    assert d.action == Action.ASK and d.category == "apollo-credit" and d.is_external_write


@pytest.mark.parametrize(
    "cmd",
    [
        "apollo people enrich --email ada@example.com",
        "apollo people bulk-enrich --emails ada@example.com",
        "apollo companies enrich --domain example.com",
        "apollo people email --id X123",
    ],
)
def test_apollo_credit_cli_asks(cmd: str) -> None:
    assert classify("Bash", {"command": cmd}).category == "apollo-credit"


# --- Apollo sends/enrollment (CLI) => DENY; safe reads => passthrough -----------
@pytest.mark.parametrize(
    "cmd",
    ["apollo sequences add-contacts --id S --contact-id C", "apollo sequences approve --id S"],
)
def test_apollo_cli_send_denied(cmd: str) -> None:
    assert _action("Bash", {"command": cmd}) == Action.DENY


@pytest.mark.parametrize(
    "cmd",
    [
        "apollo auth whoami",
        "apollo usage credits",
        "apollo sequences search --query welcome",
        "apollo people search --title CTO",
        "apollo email-accounts list",
    ],
)
def test_apollo_cli_read_passthrough(cmd: str) -> None:
    assert _action("Bash", {"command": cmd}) == Action.PASSTHROUGH


@pytest.mark.parametrize(
    "cmd",
    [
        # Prose ABOUT Apollo (commit messages, echoes) is not an Apollo CLI invocation.
        'git commit -m "feat(gateway): Apollo write gateway with sequence enroll deny"',
        'echo "the Apollo enrollment flow is blocked"',
        "git add src/spindle_gtm/apollo_gateway.py",
    ],
)
def test_prose_mentioning_apollo_is_not_apollo_cli(cmd: str) -> None:
    assert _action("Bash", {"command": cmd}) == Action.PASSTHROUGH


@pytest.mark.parametrize(
    "cmd",
    [
        "ls; apollo sequences add-contacts --id S",  # after separator: still caught
        "true && apollo sequences approve --id S",
    ],
)
def test_apollo_after_shell_separator_still_caught(cmd: str) -> None:
    assert _action("Bash", {"command": cmd}) == Action.DENY


# --- outbound apply requires an approved manifest ------------------------------
def test_outbound_apply_without_manifest_denied() -> None:
    d = classify("Bash", {"command": "uv run spindle send --apply"}, manifest_ok=False)
    assert d.action == Action.DENY and d.category == "outbound-no-manifest"


def test_outbound_apply_with_manifest_asks() -> None:
    d = classify("Bash", {"command": "uv run spindle send --apply"}, manifest_ok=True)
    assert d.action == Action.ASK


def test_manifest_present_requires_both_files(tmp_path: Path) -> None:
    assert not manifest_present(tmp_path)
    (tmp_path / "outbox" / "approved").mkdir(parents=True)
    (tmp_path / "outbox" / "approved" / "manifest.json").write_text("{}")
    assert not manifest_present(tmp_path)  # approval record still missing
    (tmp_path / "outbox" / "approved" / "manifest.approved").write_text("ok")
    assert manifest_present(tmp_path)


# --- default -------------------------------------------------------------------
def test_unmatched_passthrough() -> None:
    assert _action("Bash", {"command": "ls -la"}) == Action.PASSTHROUGH
