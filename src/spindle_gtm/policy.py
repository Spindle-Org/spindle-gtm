"""Deterministic governance policy for Claude Code hooks.

Pure, stdlib-only classification of a tool call into allow / ask / deny, so it can
be unit-tested without Claude Code and imported by a thin hook wrapper. The wrapper
adapts Claude Code's hook stdin/stdout to :func:`classify`.

Design notes:
- Apollo tools are matched by a semantic pattern (any MCP tool whose name contains
  "apollo", plus an ``apollo`` CLI in a shell command) and classified by VERB, so we
  never depend on an exact, possibly-unknown Apollo MCP tool name. Unknown Apollo
  verbs are treated as writes (ask), never silently allowed.
- See docs/adr/0002 and CLAUDE.md for the rules this enforces.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

# Outbound apply requires BOTH a manifest and an approval record to exist
# (docs/adr/0002). Paths are under outbox/ (gitignored). The hook checks the
# filesystem and passes the result into classify() so classify() stays pure.
MANIFEST_REL = "outbox/approved/manifest.json"
APPROVAL_REL = "outbox/approved/manifest.approved"


class Action(StrEnum):
    DENY = "deny"
    ASK = "ask"
    PASSTHROUGH = "passthrough"  # defer to Claude Code's normal permission flow


@dataclass(frozen=True)
class Decision:
    action: Action
    category: str
    reason: str
    is_external_write: bool = False


# --- credential / secret access -------------------------------------------------
_CRED_RE = re.compile(
    r"""(?ix)
    ( \.env\b(?!\.example)          # .env, .env.local — but not .env.example
    | \.mcp\.json\b(?!\.example)
    | credentials?(?:\.json|\.ya?ml|\.txt|\.ini|/)   # a credential FILE/dir, not the bare word
    | (?:^|/)\.aws/
    | (?:^|/)\.ssh/
    | (?:^|/)\.gnupg/
    | \.netrc\b
    | id_rsa\b
    | \.pem\b
    | \.p12\b
    | oauth[\w-]*\.json
    | [\w-]*token[\w-]*\.json
    | secrets?\.(?:json|ya?ml|toml|txt)
    )
    """
)

# --- LinkedIn (manual only; never automated/fetched) ----------------------------
_LINKEDIN_RE = re.compile(r"(?i)\blinkedin\.com\b|\blnkd\.in\b")

# --- browser automation / scraping frameworks -----------------------------------
_BROWSER_AUTOMATION_RE = re.compile(
    r"""(?ix)
    ( playwright
    | selenium
    | puppeteer
    | chromedriver
    | geckodriver
    | \bwebdriver\b
    | msedgedriver
    | \bphantomjs\b
    | --load-extension
    | --headless.*--(?:remote-debugging|disable-web-security)
    )
    """
)

# --- shell fetchers (used to detect LinkedIn scraping via curl/wget/etc.) --------
_FETCHER_RE = re.compile(r"(?ix)\b(curl|wget|http|https|httpie|xh|lynx|links)\b")

# --- Apollo verb classification (see docs/APOLLO_CAPABILITIES.md) ----------------
# Matched against a NORMALIZED haystack ('_' and '-' -> space) so word boundaries work
# for both MCP tool names (apollo_people_match) and CLI commands (people bulk-enrich).
# Order of evaluation: send/enroll (DENY) -> credit (ASK) -> write (ASK) -> read.
_APOLLO_SEND_ENROLL_RE = re.compile(
    r"(?i)"
    r"send now|send email|email send|messages send|messages create|\bsend\b|"
    r"enroll|add contacts?|campaigns? add|\bapprove\b"
)
# CREDIT-CONSUMING: enrichment / email-or-phone reveal / person match. Approval-required.
_APOLLO_CREDIT_RE = re.compile(r"(?i)enrich|\bmatch\b|reveal|people email")
# WRITE (CRM mutation / purchase). Approval-required.
_APOLLO_WRITE_RE = re.compile(
    r"(?i)"
    r"create|update|delete|purchase|\blog\b|import|upload|"
    r"add entity|remove entity|complete|skip|remove contacts?|campaigns? remove|remove or stop"
)
# READ (no credits, no mutation). Defer to normal permission flow.
_APOLLO_READ_RE = re.compile(
    r"(?i)"
    r"search|\bindex\b|\bshow\b|\bget\b|\blist\b|employees|\bjobs\b|\bnews\b|"
    r"schedules|job postings|sync report|result show|show product|show profile|"
    r"\bwhoami\b|\bauth\b|\blogin\b|\blogout\b|\bhelp\b|\bversion\b|"
    r"usage|credits|\bprofile\b|stats|analytics|email accounts|\busers\b"
)


def _normalize(text: str) -> str:
    return re.sub(r"[_\-]+", " ", text.lower())


# --- git add/commit of forbidden content ----------------------------------------
_GIT_ADDCOMMIT_RE = re.compile(r"(?ix)\bgit\s+(add|commit)\b")
_GIT_FORBIDDEN_RE = re.compile(
    r"""(?ix)
    ( -f\b | --force
    | (?:^|[\s'"=/])data/
    | (?:^|[\s'"=/])db/
    | (?:^|[\s'"=/])exports/
    | \.csv\b
    | \.sqlite3?\b
    | \.db\b
    | \.env\b(?!\.example)
    )
    """
)

# --- outbound apply (the real send/enroll dispatch via the local CLI) -----------
_OUTBOUND_APPLY_RE = re.compile(
    r"(?ix)\bspindle\b.*--apply\b.*\b(send|outbound|enroll|dispatch)\b"
    r"|\bspindle\b.*\b(send|outbound|enroll|dispatch)\b.*--apply\b"
)

_PATH_TOOLS = {"Read", "Edit", "Write", "NotebookEdit", "MultiEdit"}


def manifest_present(cwd: Path | str) -> bool:
    """True iff both the batch manifest and its approval record exist."""
    root = Path(cwd)
    return (root / MANIFEST_REL).is_file() and (root / APPROVAL_REL).is_file()


def _is_apollo(tool_name: str, command: str) -> bool:
    if "apollo" in tool_name.lower() and tool_name.startswith("mcp__"):
        return True
    # Apollo CLI invoked as a COMMAND: only at command position (start of command, or
    # after ; | & && || $( or backtick) — NOT the word "apollo" appearing in prose such
    # as a git commit message.
    return bool(re.search(r"(?i)(?:^|[;&|]\s*|\$\(\s*|`\s*)apollo(?:-cli)?\b", command))


def _classify_apollo(tool_name: str, command: str) -> Decision:
    haystack = _normalize(f"{tool_name} {command}")
    if _APOLLO_SEND_ENROLL_RE.search(haystack):
        return Decision(
            Action.DENY,
            "apollo-send-or-enroll",
            "Apollo email-send / sequence-enrollment is BLOCKED during development "
            "(outbound kill switch — docs/adr/0002, docs/APOLLO_CAPABILITIES.md).",
            is_external_write=True,
        )
    if _APOLLO_CREDIT_RE.search(haystack):
        return Decision(
            Action.ASK,
            "apollo-credit",
            "Apollo enrichment/reveal consumes credits — explicit human approval required.",
            is_external_write=True,
        )
    if _APOLLO_WRITE_RE.search(haystack):
        return Decision(
            Action.ASK,
            "apollo-write",
            "Apollo write requires explicit human approval (Apollo is read-only system of record).",
            is_external_write=True,
        )
    if _APOLLO_READ_RE.search(haystack):
        return Decision(Action.PASSTHROUGH, "apollo-read", "Apollo read allowed.")
    # Unknown Apollo verb: be conservative — treat as a write needing approval.
    return Decision(
        Action.ASK,
        "apollo-unknown",
        "Unclassified Apollo action — requires human approval (fail safe).",
        is_external_write=True,
    )


def classify(tool_name: str, tool_input: dict[str, Any], *, manifest_ok: bool = False) -> Decision:
    """Classify a single tool call. Never raises on malformed input.

    ``manifest_ok`` is computed by the hook wrapper via :func:`manifest_present`
    and tells us whether an approved batch manifest exists for outbound apply.
    """
    command = str(tool_input.get("command", "")) if isinstance(tool_input, dict) else ""
    url = str(tool_input.get("url", "")) if isinstance(tool_input, dict) else ""
    file_path = str(tool_input.get("file_path", "")) if isinstance(tool_input, dict) else ""

    # 1) Credential / secret access — highest priority deny.
    if tool_name in _PATH_TOOLS and _CRED_RE.search(file_path):
        return Decision(Action.DENY, "credential-access", f"Blocked credential path: {file_path}")
    if tool_name in {"Bash", "BashOutput"} and _CRED_RE.search(command):
        return Decision(
            Action.DENY, "credential-access", "Blocked credential access in shell command."
        )

    # 2) LinkedIn automation / fetching.
    if tool_name == "WebFetch" and _LINKEDIN_RE.search(url):
        return Decision(
            Action.DENY, "linkedin-fetch", "LinkedIn is manual-only; automated fetch denied."
        )
    if tool_name == "Bash" and _LINKEDIN_RE.search(command) and _FETCHER_RE.search(command):
        return Decision(Action.DENY, "linkedin-fetch", "LinkedIn shell fetch/scrape denied.")

    # 3) Browser automation frameworks / extensions.
    if tool_name == "Bash" and _BROWSER_AUTOMATION_RE.search(command):
        return Decision(
            Action.DENY,
            "browser-automation",
            "Browser automation (Playwright/Selenium/Puppeteer/etc.) denied.",
        )

    # 4) git add/commit of forbidden content.
    if (
        tool_name == "Bash"
        and _GIT_ADDCOMMIT_RE.search(command)
        and _GIT_FORBIDDEN_RE.search(command)
    ):
        return Decision(
            Action.DENY,
            "git-forbidden",
            "git add/commit of data/db/exports/CSV/SQLite/secrets denied.",
        )

    # 5) Outbound apply (local send/enroll dispatch) requires an approved manifest.
    if tool_name == "Bash" and _OUTBOUND_APPLY_RE.search(command):
        if not manifest_ok:
            return Decision(
                Action.DENY,
                "outbound-no-manifest",
                f"Outbound apply blocked: missing approved batch manifest "
                f"({MANIFEST_REL}) and/or approval record ({APPROVAL_REL}).",
                is_external_write=True,
            )
        return Decision(
            Action.ASK,
            "outbound-apply",
            "Outbound apply with an approved manifest — confirm before dispatch.",
            is_external_write=True,
        )

    # 6) Apollo MCP or CLI.
    if _is_apollo(tool_name, command):
        return _classify_apollo(tool_name, command)

    # Anything else: defer to Claude Code's normal permission flow.
    return Decision(Action.PASSTHROUGH, "unmatched", "")
