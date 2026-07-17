"""The synthetic end-to-end demo runs clean in CI (no external writes)."""

from __future__ import annotations

from sqlmodel import Session

from spindle_gtm.demo import run_demo


def test_e2e_demo(session: Session) -> None:
    summary = run_demo(session)
    assert summary["qualified"] is True
    assert summary["buying_group_selected"] == 2
    assert summary["draft_violations"] == 0
    assert summary["compliance_decision"] == "ALLOW"
    assert summary["batch_status"] == "APPROVED"
    assert summary["gateway_verify_ok"] is True
    assert summary["real_writes_blocked"] is True
    assert summary["reply_lock_engaged"] is True
    assert summary["removal_manifests_prepared"] == 1
