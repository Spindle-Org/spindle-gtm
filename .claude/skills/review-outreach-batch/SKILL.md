---
name: review-outreach-batch
description: Run compliance + deliverability review, then a final manifest check, on a drafted batch before human approval.
---

Review a drafted batch. Two stages, both read-only.

1. Delegate to the **compliance-reviewer** subagent: run the region gate + deliverability checks
   over every message. Produce a pass/hold table with exact reasons.
2. For the passing subset, delegate to the **outbound-reviewer** subagent: verify the exact batch
   manifest matches the gated drafts (no drift), suppression honored, counts within caps.
3. Summarize a go / no-go. Do NOT approve or send — approval is the founder's explicit action,
   and outbound apply is blocked until an approved manifest + approval record exist.

Guardrails: no sends, no approvals, no Apollo writes.
