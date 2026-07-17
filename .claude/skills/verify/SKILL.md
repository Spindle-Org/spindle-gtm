---
name: verify
description: How to verify a spindle-gtm change end-to-end (release gate + focused checks). Project verify descriptor for /verify.
---

# Verifying spindle-gtm

## Full gate (use before shipping)
```sh
make verify       # == bash scripts/release_gate.sh
```
Passes only when: ruff format/lint + mypy clean, full pytest suite passes, no tracked PII,
no tracked secrets, real-write tools still blocked (RealApolloClient refuses + kill switch
engaged), and the synthetic end-to-end demo (`spindle_gtm.demo`) runs clean.

## Focused verification while iterating
```sh
make check                          # ruff format check + lint + mypy
uv run pytest tests/unit/test_<area>.py tests/integration/test_<area>.py -q
uv run python -m spindle_gtm.demo   # observe the pipeline actually run end-to-end
```

## What "verified" means here
Drive the affected flow and observe behavior, not just green tests:
- outreach change → `make run` and read the drafted body + `validate_draft` violations.
- gates/gateway change → run the demo + the relevant test; confirm reason codes.
- schema change → `make migrate` on a fresh DB, then `make run`.

## Independent audits (deeper, separate sessions)
The verifier prompts in `docs/Spindle_GTM_Claude_Code_Prompt_Pack.md` (Part III) are the
independent audits; run them in a fresh session before a real send. The first-real-send
checklist (docs/runbooks/first-real-send-checklist.md) tracks them.
