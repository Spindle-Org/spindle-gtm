"""Streamlit local review dashboard — PII-free by construction.

Shows only aggregate counts and batch status. It never renders names, emails, or
message bodies (docs/adr/0002). Run: ``streamlit run src/spindle_gtm/dashboard.py``.
"""

from __future__ import annotations

import streamlit as st
from sqlalchemy import func
from sqlmodel import select

from spindle_gtm.db import make_engine, session_scope
from spindle_gtm.models import Account, Batch, Contact


def _counts_by_status(model: type) -> dict[str, int]:
    with session_scope(make_engine()) as session:
        rows = session.exec(
            select(model.status, func.count()).group_by(model.status)  # type: ignore[attr-defined]
        ).all()
    return {str(status): int(count) for status, count in rows}


def render() -> None:
    st.set_page_config(page_title="spindle-gtm review", page_icon="📮")
    st.title("spindle-gtm — review dashboard")
    st.caption("Aggregate + status only. No names, emails, or message bodies are shown here.")

    try:
        accounts = _counts_by_status(Account)
        contacts = _counts_by_status(Contact)
        batches = _counts_by_status(Batch)
    except Exception as exc:  # noqa: BLE001 — surface an empty-DB hint, not a stack trace
        st.info(f"No data yet (run `spindle` first). Details: {exc}")
        return

    col1, col2, col3 = st.columns(3)
    col1.metric("Accounts", sum(accounts.values()))
    col2.metric("Contacts", sum(contacts.values()))
    col3.metric("Batches", sum(batches.values()))

    st.subheader("Accounts by status")
    st.bar_chart(accounts)
    st.subheader("Contacts by status")
    st.bar_chart(contacts)


render()
