---
name: qualify-accounts
description: Qualify accounts from the Apollo seed list into a research-ready shortlist using read-only research. Use at the start of a batch.
---

Qualify accounts for outreach.

1. Delegate to the **account-researcher** subagent (read-only web + Apollo).
2. Pull the seed company list (read-only) and score each account against the ICP: fit, buying
   signals, and reachability. Capture `evidence[]` (claim, source, fetched_at) per signal.
3. Output a ranked shortlist with a qualify/disqualify decision and reason per account.

Guardrails: Apollo stays read-only; no LinkedIn fetching; no sends; no approval state changes.
This produces a shortlist only — nothing is contacted.
