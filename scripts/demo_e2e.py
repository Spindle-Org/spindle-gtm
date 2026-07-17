#!/usr/bin/env python3
"""Thin wrapper for the synthetic end-to-end demo. Logic lives in
``spindle_gtm.demo`` so it is importable by tests. Run: `python -m spindle_gtm.demo`."""

from __future__ import annotations

from spindle_gtm.demo import _main

if __name__ == "__main__":
    _main()
