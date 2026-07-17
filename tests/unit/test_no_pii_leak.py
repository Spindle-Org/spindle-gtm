"""Security guard: no real-looking emails or Apollo exports may be committed.

The whole tree that git would commit is scanned; only example.com/.org/.net
addresses are allowed, and raw .csv files are rejected as exports.
"""

from __future__ import annotations

from pathlib import Path

from spindle_gtm.security import committable_files, find_email_violations, scan_paths

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_repo_has_no_pii_leak() -> None:
    """Nothing currently about to be committed may contain PII or a .csv export."""
    violations = scan_paths(committable_files(REPO_ROOT), REPO_ROOT)
    assert violations == [], "\n".join(violations)


def test_guard_catches_real_email(tmp_path: Path) -> None:
    # Built at runtime so this source file itself contains no matchable address.
    bad_email = "founder@acme" + "-labs.io"
    f = tmp_path / "leak.txt"
    f.write_text(f"contact {bad_email} today")
    violations = scan_paths([f], tmp_path)
    assert violations and "real-looking email" in violations[0]


def test_guard_allows_example_com(tmp_path: Path) -> None:
    f = tmp_path / "ok.txt"
    f.write_text("reach ada@example.com and max@example.org")
    assert scan_paths([f], tmp_path) == []
    assert find_email_violations("ada@example.com") == []


def test_guard_rejects_csv_export(tmp_path: Path) -> None:
    f = tmp_path / "apollo_export.csv"
    f.write_text("name,title\nAcme,VP\n")
    violations = scan_paths([f], tmp_path)
    assert violations and "export" in violations[0]
