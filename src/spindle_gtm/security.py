"""Guardrail: refuse to track real-looking PII or Apollo exports.

Used by both the pre-commit hook (scripts/check_no_pii.py) and a unit test.
Only example.com / example.org / example.net addresses (RFC 2606 reserved) are
permitted anywhere in the tree; raw ``.csv`` files are treated as Apollo exports
and rejected (they are gitignored and must never be force-added).
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
ALLOWED_EMAIL_DOMAINS = ("example.com", "example.org", "example.net")

# Text files worth scanning for emails; everything else is skipped as binary/noise.
_SCANNABLE_SUFFIXES = {
    ".py",
    ".toml",
    ".md",
    ".txt",
    ".json",
    ".yaml",
    ".yml",
    ".ini",
    ".cfg",
    ".mako",
    ".env",
    ".example",
    ".sh",
    ".sql",
    ".html",
    "",
}


def _domain_allowed(email: str) -> bool:
    domain = email.rsplit("@", 1)[-1].lower()
    return any(domain == d or domain.endswith("." + d) for d in ALLOWED_EMAIL_DOMAINS)


def find_email_violations(text: str) -> list[str]:
    return [m for m in EMAIL_RE.findall(text) if not _domain_allowed(m)]


def scan_paths(paths: list[Path], repo_root: Path | None = None) -> list[str]:
    """Return human-readable violation strings for the given files."""
    repo_root = repo_root or Path.cwd()
    violations: list[str] = []
    for path in paths:
        full = path if path.is_absolute() else repo_root / path
        if not full.is_file():
            continue
        if full.suffix.lower() == ".csv":
            violations.append(f"{path}: raw .csv (treated as an Apollo/contact export)")
            continue
        if full.suffix.lower() not in _SCANNABLE_SUFFIXES:
            continue
        try:
            text = full.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for email in find_email_violations(text):
            violations.append(f"{path}: real-looking email {email!r} (use example.com)")
    return violations


def committable_files(repo_root: Path | None = None) -> list[Path]:
    """Files git would include in a commit: tracked + untracked, minus gitignored."""
    repo_root = repo_root or Path.cwd()
    out = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )
    return [Path(line) for line in out.stdout.splitlines() if line]


def staged_files(repo_root: Path | None = None) -> list[Path]:
    repo_root = repo_root or Path.cwd()
    out = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )
    return [Path(line) for line in out.stdout.splitlines() if line]


def main() -> int:
    root = Path.cwd()
    files = staged_files(root) or committable_files(root)
    violations = scan_paths(files, root)
    if violations:
        print("PII/export guard failed:")
        for v in violations:
            print(f"  - {v}")
        print("Only example.com addresses are allowed; .csv exports must not be committed.")
        return 1
    return 0
