---
name: prepare-apollo-actions
description: Assemble a DRY-RUN plan of Apollo actions (e.g. labels, task notes) for human review. Never executes Apollo writes.
---

Prepare a plan of proposed Apollo actions — **without executing any of them**.

1. Determine which Apollo write actions the batch would need (e.g. label an account, log a task).
   Use read-only Apollo to gather current state.
2. Emit a human-readable **action plan** (what, on which entity, why) plus the exact parameters —
   as a proposal file, not a call.
3. Stop. Every Apollo write requires explicit human approval; the governance hook forces an
   approval prompt on Apollo writes and denies sends/sequence-enrollment outright.

Guardrails: this skill NEVER calls an Apollo write tool. It only produces a reviewable plan.
Apollo remains the read-only system of record.
