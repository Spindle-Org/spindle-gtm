"""Region compliance policy, loaded from ``config/region_policy.toml``.

Policy is data, the gate is code (docs/adr/0001, ADR-7). Adding a country is a
config row, not a code change.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

from pydantic import BaseModel

from spindle_gtm.config import get_settings
from spindle_gtm.models import ColdEmailPolicy


class RegionPolicy(BaseModel):
    region_code: str
    legal_basis: str
    requires_consent: bool
    unsubscribe_required: bool
    physical_address_required: bool
    cold_email_allowed: ColdEmailPolicy
    notes: str = ""


def load_region_policies(path: Path | None = None) -> dict[str, RegionPolicy]:
    path = path or get_settings().region_policy_path
    with path.open("rb") as fh:
        raw = tomllib.load(fh)
    policies: dict[str, RegionPolicy] = {}
    for code, values in raw.items():
        policies[code] = RegionPolicy(region_code=code, **values)
    return policies
