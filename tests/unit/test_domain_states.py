"""Action-state machine and account-lock gating."""

from __future__ import annotations

import pytest

from spindle_gtm.domain import (
    BLOCKING_LOCKS,
    TransitionError,
    assert_action_transition,
    lock_blocks_outbound,
)
from spindle_gtm.models import AccountLockState, ActionState


@pytest.mark.parametrize(
    ("cur", "nxt"),
    [
        (ActionState.PLANNED, ActionState.REVIEWED),
        (ActionState.REVIEWED, ActionState.APPROVED),
        (ActionState.APPROVED, ActionState.APPLYING),
        (ActionState.APPLYING, ActionState.APPLIED),
        (ActionState.APPLYING, ActionState.PARTIAL),
        (ActionState.PARTIAL, ActionState.APPLYING),
        (ActionState.FAILED, ActionState.APPLYING),
    ],
)
def test_legal_transitions(cur: ActionState, nxt: ActionState) -> None:
    assert_action_transition(cur, nxt)  # must not raise


@pytest.mark.parametrize(
    ("cur", "nxt"),
    [
        (ActionState.PLANNED, ActionState.APPLIED),  # can't skip approval/apply
        (ActionState.PLANNED, ActionState.APPROVED),
        (ActionState.APPLIED, ActionState.APPLYING),  # terminal
        (ActionState.CANCELLED, ActionState.PLANNED),  # terminal
        (ActionState.APPROVED, ActionState.APPLIED),  # must go through APPLYING
    ],
)
def test_illegal_transitions_raise(cur: ActionState, nxt: ActionState) -> None:
    with pytest.raises(TransitionError):
        assert_action_transition(cur, nxt)


@pytest.mark.parametrize(
    "state",
    [AccountLockState.REPLIED, AccountLockState.MEETING_SET, AccountLockState.DO_NOT_CONTACT],
)
def test_named_blocking_locks(state: AccountLockState) -> None:
    assert lock_blocks_outbound(state)
    assert state in BLOCKING_LOCKS


def test_open_lock_does_not_block() -> None:
    assert not lock_blocks_outbound(AccountLockState.OPEN)


def test_legal_hold_also_blocks() -> None:
    assert lock_blocks_outbound(AccountLockState.LEGAL_HOLD)
