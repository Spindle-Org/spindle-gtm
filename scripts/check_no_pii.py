#!/usr/bin/env python3
"""Pre-commit entrypoint for the PII / Apollo-export guard. Logic lives in
``spindle_gtm.security`` so it is importable and unit-tested."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from spindle_gtm.security import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
