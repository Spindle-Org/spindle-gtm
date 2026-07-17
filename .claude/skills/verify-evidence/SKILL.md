---
name: verify-evidence
description: Independently verify research claims against their sources before any drafting. Use as the gate between research and copywriting.
---

Verify research evidence independently.

1. Delegate to the **evidence-verifier** subagent (independent, read-only).
2. For each claim, re-check the cited source and mark `verified`, `unverified`, or
   `contradicted`. Reject stale, mismatched, or unsourced claims.
3. Emit an **approved evidence set** containing only `verified` items. This set is the ONLY
   input the copywriter is allowed to use.

Guardrails: read-only; no Apollo writes; no LinkedIn fetching. Unverified claims must not pass.
