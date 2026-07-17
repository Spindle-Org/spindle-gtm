---
name: audit-gtm-system
description: Audit the GTM governance layer — permissions, hooks, subagent tool boundaries, and policy tests — and report gaps. Read-only.
---

Audit the governance layer end to end.

1. Read `.claude/settings.json` (permission denies + PreToolUse hook), `.claude/agents/*.md`
   (tool allowlists), and `src/spindle_gtm/policy.py`.
2. Verify the invariants hold: credentials/`.env` blocked; LinkedIn domains + browser automation
   blocked; Apollo writes force approval and sends/enrollment are denied; git add/commit of
   data/db/exports/CSV/SQLite/secrets denied; outbound apply requires an approved manifest;
   external-write attempts are logged.
3. Run the policy tests: `uv run pytest tests/unit/test_policy.py -q`.
4. Cross-check each subagent's `tools:` allowlist against its stated read-only/no-send boundary.
5. Report findings: what is enforced, by which layer (deny rule / hook / allowlist), and any gap.
   Remind the operator to verify live with `/permissions` and `/hooks`.

Guardrails: read-only audit; make no changes. Recommend fixes for a human to apply.
