---
name: research-batch
description: Run deep read-only research across a batch of accounts to gather evidence for personalization. Use after accounts are qualified and the buying group is selected.
---

Research a batch of accounts.

1. For each account in the batch, delegate to the **account-researcher** subagent.
2. Gather buying signals and context, each backed by an `evidence[]` item (claim, source,
   fetched_at). Prefer primary sources; note anything unverifiable.
3. Consolidate per-account research packets ready for independent verification.

Guardrails: read-only web + Apollo; no LinkedIn fetching; no sends; no writes to Apollo.
Do NOT draft outreach here — evidence must be verified first (`/verify-evidence`).
