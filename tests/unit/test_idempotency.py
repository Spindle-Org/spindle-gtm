"""Deterministic idempotency keys / payload hashes and approval invalidation."""

from __future__ import annotations

from spindle_gtm.domain import (
    approval_valid,
    build_manifest,
    idempotency_key,
    manifest_hash,
    payload_hash,
)
from spindle_gtm.models import Approval

PAYLOAD = {"label": "Q3 Targets", "account_ids": [2, 1, 3]}


def test_payload_hash_is_deterministic_and_order_independent() -> None:
    # Canonical JSON sorts keys, so equal dicts hash equally regardless of key order.
    assert payload_hash({"a": 1, "b": 2}) == payload_hash({"b": 2, "a": 1})
    assert payload_hash(PAYLOAD) != payload_hash({**PAYLOAD, "label": "changed"})


def test_idempotency_key_deterministic() -> None:
    k1 = idempotency_key("apollo_label_add", "account:1", PAYLOAD)
    k2 = idempotency_key("apollo_label_add", "account:1", PAYLOAD)
    assert k1 == k2
    assert k1 != idempotency_key("apollo_label_add", "account:2", PAYLOAD)


def test_build_manifest_is_reproducible() -> None:
    m1 = build_manifest("apollo_label_add", "account:1", PAYLOAD)
    m2 = build_manifest("apollo_label_add", "account:1", PAYLOAD)
    assert m1.idempotency_key == m2.idempotency_key
    assert m1.manifest_hash == m2.manifest_hash
    assert m1.payload_hash == m2.payload_hash


def test_approval_bound_to_manifest_hash() -> None:
    manifest = build_manifest("apollo_label_add", "account:1", PAYLOAD)
    approval = Approval(
        manifest_id=1, approved_manifest_hash=manifest.manifest_hash, approved_by="founder"
    )
    assert approval_valid(approval, manifest)

    # Any change to the manifest content invalidates the prior approval.
    manifest.manifest_hash = manifest_hash("apollo_label_add", "account:1", {**PAYLOAD, "x": 9})
    assert not approval_valid(approval, manifest)


def test_revoked_approval_is_invalid() -> None:
    from spindle_gtm.models import utcnow

    manifest = build_manifest("apollo_label_add", "account:1", PAYLOAD)
    approval = Approval(
        manifest_id=1,
        approved_manifest_hash=manifest.manifest_hash,
        approved_by="founder",
        revoked_at=utcnow(),
    )
    assert not approval_valid(approval, manifest)
