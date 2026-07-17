---
name: run
description: How to launch and drive the spindle-gtm app so a change can be seen working. Project launch descriptor for /run.
---

# Running spindle-gtm

This is a local Python (uv) CLI + Streamlit app. Nothing here writes to Apollo or sends email.

## Fastest "it works" run — the synthetic end-to-end demo
```sh
make run          # == uv run python -m spindle_gtm.demo
```
Runs the whole pipeline on an in-memory DB with synthetic example.com data: account →
qualify → buying group → research → verify → draft → compliance → batch → hash-bound approval
→ gateway verify (dry-run) → reply lock. Prints a JSON summary and `E2E DEMO: PASS`.

## Launch the CLI
```sh
uv run spindle-gtm --help
uv run spindle-gtm doctor                 # read-only preflight
uv run spindle-gtm regions
uv run spindle-gtm gate US --unsubscribe --physical-address
```

## Launch the review dashboard (needs a DB)
```sh
make migrate      # first time: create db/spindle.db
make dashboard    # == uv run streamlit run src/spindle_gtm/dashboard.py  → http://localhost:8501
```

## Notes for driving it
- Outbound is dry-run/blocked by default (`OUTBOUND_ENABLED=false`); do not enable it to "run".
- To see a change in a specific module, prefer `make run` (exercises most modules) or a focused
  `uv run pytest tests/... -q`.
