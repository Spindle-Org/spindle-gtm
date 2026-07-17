"""Load + validate the qualification config from ``config/*.yaml``."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from spindle_gtm.config import REPO_ROOT
from spindle_gtm.qualification.schemas import AppConfig

CONFIG_DIR = REPO_ROOT / "config"

_FILE_KEYS: dict[str, str] = {
    "icp": "icp.yaml",
    "account_scoring": "account_scoring.yaml",
    "personas": "personas.yaml",
    "contact_scoring": "contact_scoring.yaml",
    "research_sources": "research_sources.yaml",
    "evidence": "evidence.yaml",
    "message_rules": "message_rules.yaml",
    "pilot_wedges": "pilot_wedges.yaml",
    "outreach_policy": "outreach_policy.yaml",
    "mailbox_limits": "mailbox_limits.yaml",
    "suppression_rules": "suppression_rules.yaml",
}


def load_app_config(config_dir: Path = CONFIG_DIR) -> AppConfig:
    """Read every config file and validate the whole set at once."""
    raw: dict[str, Any] = {}
    for key, filename in _FILE_KEYS.items():
        with (config_dir / filename).open(encoding="utf-8") as fh:
            raw[key] = yaml.safe_load(fh)
    return AppConfig.model_validate(raw)


@lru_cache(maxsize=1)
def get_app_config() -> AppConfig:
    return load_app_config()
