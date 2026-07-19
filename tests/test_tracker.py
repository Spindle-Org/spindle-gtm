"""Tracker schema + validation tests."""

from __future__ import annotations

from pathlib import Path

from spindle_gtm.tracker import (
    COLUMNS,
    template_row,
    validate_csv,
    validate_rows,
    write_template,
)


def test_template_row_validates_clean() -> None:
    assert validate_rows(list(COLUMNS), [template_row()]) == []


def test_bad_enum_is_caught() -> None:
    bad = {**template_row(), "send_status": "yeeted"}
    issues = validate_rows(list(COLUMNS), [bad])
    assert any(i.column == "send_status" for i in issues)


def test_send_ready_requires_copy_and_sender() -> None:
    row = {**template_row(), "send_status": "ready", "email_1": "", "subject_a": ""}
    issues = validate_rows(list(COLUMNS), [row])
    cols = {i.column for i in issues}
    assert {"email_1", "subject_a"} <= cols


def test_missing_and_reordered_columns() -> None:
    dropped = [c for c in COLUMNS if c != "email"]
    assert any("missing columns" in i.message for i in validate_rows(dropped, []))
    reordered = list(COLUMNS)
    reordered[0], reordered[1] = reordered[1], reordered[0]
    assert any("canonical order" in i.message for i in validate_rows(reordered, []))


def test_row_without_contact_id_is_flagged() -> None:
    row = {**template_row(), "contact_id": ""}
    assert any(i.column == "contact_id" for i in validate_rows(list(COLUMNS), [row]))


def test_write_and_validate_roundtrip(tmp_path: Path) -> None:
    path = write_template(tmp_path / "t.csv")
    assert validate_csv(path) == []


def test_example_email_is_example_dot_com() -> None:
    # Guard: the committed sample must never carry a real address.
    assert template_row()["email"].endswith("@example.com")
