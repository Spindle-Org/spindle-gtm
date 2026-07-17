---
name: sync-activity
description: Pull activity/outcomes (replies, meetings) from read-only Apollo and record them locally. Read-only against Apollo.
---

Sync outreach activity into the local store.

1. Read activity from Apollo (read-only): campaign/task/reply status for the current batch.
2. Record outcomes locally (meetings, replies, LOI progress) in the local DB/outcomes. Writes go
   to the **local** store only — never back to Apollo.
3. Report a funnel summary (contacted → replied → meeting → LOI) against the batch goal.

Guardrails: Apollo is read-only; no Apollo writes/sends. Local writes must not touch credential
paths and must not commit PII (data/db/exports stay gitignored).
