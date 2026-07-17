#!/usr/bin/env bash
# Release gate — must pass before any real send. Runs no external writes.
# Manual verifier prompts (docs/Spindle_GTM_Claude_Code_Prompt_Pack.md, Part III) are
# tracked separately in the first-real-send checklist; this script covers the automated gates.
set -euo pipefail
cd "$(dirname "$0")/.."

echo "== format / lint / types =="
uv run ruff format --check .
uv run ruff check .
uv run mypy

echo "== tests =="
uv run pytest -q

echo "== no tracked PII =="
uv run python scripts/check_no_pii.py

echo "== no tracked secrets =="
uv run python - <<'PY'
from pathlib import Path
from spindle_gtm.doctor import check_no_tracked_secrets
result = check_no_tracked_secrets(Path.cwd())
assert result.ok, f"tracked secrets: {result.detail}"
print("secrets:", result.detail)
PY

echo "== real-write tools still blocked + kill switch engaged =="
uv run python - <<'PY'
from spindle_gtm.apollo_gateway import RealApolloClient
from spindle_gtm.config import get_settings
try:
    RealApolloClient().apply("create_task", {})
    raise SystemExit("FAIL: real Apollo client did not refuse")
except NotImplementedError:
    pass
assert get_settings().outbound_enabled is False, "FAIL: outbound kill switch is DISENGAGED"
print("real writes blocked; kill switch engaged")
PY

echo "== synthetic end-to-end demo =="
uv run python -m spindle_gtm.demo

echo ""
echo "RELEASE GATE: PASS (automated). Complete the manual verifier prompts and the"
echo "first-real-send checklist (docs/runbooks/first-real-send-checklist.md) before any real send."
