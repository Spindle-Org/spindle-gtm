"""Local Streamlit review dashboard (7 pages).

Thin renderer over dashboard_data providers; approval actions route through approvals.py
(role-checked, hash-bound, audited). Deliberately NO bulk approve-all control. Runs locally:
``streamlit run src/spindle_gtm/dashboard.py``. Screenshots/tests use synthetic fixtures.
"""

from __future__ import annotations

import os

import streamlit as st
from sqlmodel import Session, select

from spindle_gtm import dashboard_data as data
from spindle_gtm.approvals import (
    ApprovalError,
    approve_batch,
    batch_payload,
    confirm_apply,
    current_batch_hash,
    edit_draft_field,
    expected_confirmation,
    mark_reviewed,
)
from spindle_gtm.db import make_engine
from spindle_gtm.domain import build_manifest
from spindle_gtm.gates import preapply_recheck
from spindle_gtm.models import BatchStatus, EmailDraft, OutreachBatch

PAGES = (
    "Accounts",
    "Buying groups",
    "Research & evidence",
    "Draft review",
    "Batch manifest",
    "Tasks",
    "Funnel & experiments",
)

# The acting user (approver checks happen in approvals.py against APPROVERS).
ACTOR = os.environ.get("SPINDLE_ACTOR", "ayush")
APPROVERS = [
    a.strip() for a in os.environ.get("SPINDLE_APPROVERS", "ayush").split(",") if a.strip()
]


def _session() -> Session:
    return Session(make_engine())


def page_accounts(session: Session) -> None:
    st.subheader("Accounts")
    st.dataframe(data.accounts_view(session), use_container_width=True)


def page_buying_groups(session: Session) -> None:
    st.subheader("Buying groups")
    rows = data.buying_groups_view(session)
    selected = [r for r in rows if r["role"] != "rejected"]
    rejected = [r for r in rows if r["role"] == "rejected"]
    st.markdown("**Selected**")
    st.dataframe(selected, use_container_width=True)
    st.markdown("**Rejected (with reasons)**")
    st.dataframe(rejected, use_container_width=True)


def page_research(session: Session) -> None:
    st.subheader("Research & evidence")
    st.dataframe(data.research_view(session), use_container_width=True)


def page_drafts(session: Session) -> None:
    st.subheader("Draft review")
    for row in data.drafts_view(session):
        with st.expander(f"#{row['draft_id']} → {row['recipient']} [{row['status']}]"):
            st.write({k: v for k, v in row.items() if k != "body"})
            new_body = st.text_area("Body", row["body"] or "", key=f"body{row['draft_id']}")
            col_a, col_b, col_c = st.columns(3)
            draft = session.get(EmailDraft, row["draft_id"])
            if draft is None:
                continue
            if col_a.button("Save edit", key=f"save{row['draft_id']}") and new_body != row["body"]:
                edit_draft_field(session, draft, "body", new_body, editor=ACTOR)
                session.commit()
                st.rerun()
            if col_b.button("Approve", key=f"ok{row['draft_id']}"):
                draft.status = "APPROVED"
                session.commit()
                st.rerun()
            if col_c.button("Reject", key=f"no{row['draft_id']}"):
                draft.status = "REJECTED"
                session.commit()
                st.rerun()


def page_batch(session: Session) -> None:
    st.subheader("Batch manifest")
    batches = list(session.exec(select(OutreachBatch)))
    if not batches:
        st.info("No batches yet.")
        return
    batch = st.selectbox("Batch", batches, format_func=lambda b: f"#{b.id} {b.name} [{b.status}]")
    assert batch.id is not None
    view = data.batch_manifest_view(session, batch.id)
    st.write({k: v for k, v in view.items() if k != "recipients"})
    st.dataframe(view.get("recipients", []), use_container_width=True)

    if batch.status == BatchStatus.DRAFTED and st.button("Mark reviewed"):
        mark_reviewed(session, batch, ACTOR)
        session.commit()
        st.rerun()

    if batch.status == BatchStatus.REVIEWED and st.button("Approve (hash-bound)"):
        manifest = build_manifest(
            "outreach_batch", f"batch:{batch.id}", batch_payload(session, batch), batch_id=batch.id
        )
        manifest.manifest_hash = current_batch_hash(session, batch)
        session.add(manifest)
        session.flush()
        try:
            approve_batch(session, batch, manifest, ACTOR, APPROVERS)
            session.commit()
            st.rerun()
        except ApprovalError as exc:
            st.error(str(exc))

    if batch.status == BatchStatus.APPROVED:
        count = len(view.get("recipients", []))
        st.warning(
            f"Second confirmation required. Type exactly: {expected_confirmation(batch.id, count)}"
        )
        typed = st.text_input("Confirmation", key=f"confirm{batch.id}")
        if st.button("Apply batch"):
            blockers = preapply_recheck(session, batch.id)
            if blockers:
                st.error(f"Blocked by pre-apply recheck: {blockers}")
            elif confirm_apply(session, batch, typed, ACTOR):
                st.success("Confirmed. (Dispatch is handled by the gated send path.)")
                session.commit()
            else:
                st.error("Confirmation text did not match.")
    # ponytail: no bulk approve-all control by design (first production version).


def page_tasks(session: Session) -> None:
    st.subheader("Tasks")
    st.dataframe(data.tasks_view(session), use_container_width=True)


def page_funnel(session: Session) -> None:
    st.subheader("Funnel & experiments")
    funnel = data.funnel_view(session)
    experiments = funnel.pop("experiments", [])
    cols = st.columns(4)
    for i, (key, value) in enumerate(funnel.items()):
        cols[i % 4].metric(key.replace("_", " "), value)
    st.markdown("**Experiments**")
    st.dataframe(experiments, use_container_width=True)


def render() -> None:
    st.set_page_config(page_title="spindle-gtm review", page_icon="📮", layout="wide")
    st.title("spindle-gtm — review dashboard")
    st.caption("Local review surface. Synthetic fixtures in screenshots/tests; PII stays local.")
    page = st.sidebar.radio("Page", PAGES)
    with _session() as session:
        {
            "Accounts": page_accounts,
            "Buying groups": page_buying_groups,
            "Research & evidence": page_research,
            "Draft review": page_drafts,
            "Batch manifest": page_batch,
            "Tasks": page_tasks,
            "Funnel & experiments": page_funnel,
        }[page](session)


if __name__ == "__main__" or os.environ.get("STREAMLIT_RUNTIME"):
    render()
