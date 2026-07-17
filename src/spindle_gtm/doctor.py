"""`spindle-gtm doctor` — read-only environment + safety preflight.

Never consumes Apollo credits and never modifies Apollo: the only Apollo call is
``apollo auth whoami`` (read-only identity). Everything else is local/offline.
The subprocess/git calls are behind small functions so tests can mock them.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import text

from spindle_gtm.config import REPO_ROOT, get_settings
from spindle_gtm.region_policy import load_region_policies
from spindle_gtm.security import committable_files, scan_paths

_SECRET_FILE_RE = re.compile(
    r"""(?ix)
    ( (^|/)\.env(\.(?!example)[\w.-]+)?$
    | \.(db|sqlite|sqlite3)$
    | (^|/)credentials[\w.-]*\.(json|ya?ml)$
    | \.(pem|key|p12)$
    | [\w-]*token[\w-]*\.json$
    | [\w-]*oauth[\w-]*\.json$
    )
    """
)


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str


# --- mockable side-effect seams ------------------------------------------------
def _apollo_whoami() -> subprocess.CompletedProcess[str]:
    return subprocess.run(["apollo", "auth", "whoami"], capture_output=True, text=True, timeout=20)


def _git_tracked(project_dir: Path) -> list[str]:
    out = subprocess.run(
        ["git", "ls-files"], cwd=project_dir, capture_output=True, text=True, check=True
    )
    return [line for line in out.stdout.splitlines() if line]


# --- checks --------------------------------------------------------------------
def check_apollo_cli() -> CheckResult:
    path = shutil.which("apollo")
    return CheckResult("apollo_cli_installed", path is not None, path or "apollo not on PATH")


def check_apollo_auth() -> CheckResult:
    if shutil.which("apollo") is None:
        return CheckResult("apollo_auth_valid", False, "apollo CLI not installed")
    try:
        proc = _apollo_whoami()
    except (OSError, subprocess.SubprocessError) as exc:
        return CheckResult("apollo_auth_valid", False, f"whoami failed: {exc}")
    # Sanitized: report only success/failure, never the identity/email.
    return CheckResult(
        "apollo_auth_valid",
        proc.returncode == 0,
        "authenticated" if proc.returncode == 0 else "not logged in",
    )


def check_apollo_mcp(project_dir: Path = REPO_ROOT) -> CheckResult:
    mcp = project_dir / ".mcp.json"
    if not mcp.is_file():
        return CheckResult("apollo_mcp_visible", False, "no project .mcp.json")
    try:
        servers = json.loads(mcp.read_text()).get("mcpServers", {})
    except (json.JSONDecodeError, OSError) as exc:
        return CheckResult("apollo_mcp_visible", False, f"unreadable .mcp.json: {exc}")
    return CheckResult(
        "apollo_mcp_visible",
        "apollo" in servers,
        "apollo server in .mcp.json" if "apollo" in servers else "apollo not configured",
    )


def check_database() -> CheckResult:
    try:
        from spindle_gtm.db import make_engine

        engine = make_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            has_tables = conn.execute(
                text("SELECT count(*) FROM sqlite_master WHERE type='table'")
            ).scalar_one()
    except Exception as exc:  # noqa: BLE001 — surface any connection error as a failed check
        return CheckResult("database_reachable", False, f"{type(exc).__name__}: {exc}")
    detail = (
        f"connected ({has_tables} tables)"
        if has_tables
        else "connected (no migrations applied yet)"
    )
    return CheckResult("database_reachable", True, detail)


def check_config() -> CheckResult:
    try:
        get_settings()
        n = len(load_region_policies())
    except Exception as exc:  # noqa: BLE001
        return CheckResult("config_valid", False, f"{type(exc).__name__}: {exc}")
    return CheckResult("config_valid", True, f"settings + {n} region policies loaded")


def check_no_tracked_pii(project_dir: Path = REPO_ROOT) -> CheckResult:
    violations = scan_paths(committable_files(project_dir), project_dir)
    return CheckResult(
        "no_tracked_pii",
        not violations,
        "clean" if not violations else f"{len(violations)} violation(s)",
    )


def check_no_tracked_secrets(project_dir: Path = REPO_ROOT) -> CheckResult:
    tracked = _git_tracked(project_dir)
    hits = [f for f in tracked if _SECRET_FILE_RE.search(f)]
    return CheckResult(
        "no_tracked_secrets", not hits, "clean" if not hits else f"tracked: {', '.join(hits)}"
    )


def check_kill_switch() -> CheckResult:
    engaged = not get_settings().outbound_enabled
    return CheckResult(
        "outbound_kill_switch",
        engaged,
        "engaged (outbound disabled)" if engaged else "DISENGAGED — outbound is LIVE",
    )


def run_all(project_dir: Path = REPO_ROOT) -> list[CheckResult]:
    return [
        check_apollo_cli(),
        check_apollo_auth(),
        check_apollo_mcp(project_dir),
        check_database(),
        check_config(),
        check_no_tracked_pii(project_dir),
        check_no_tracked_secrets(project_dir),
        check_kill_switch(),
    ]
