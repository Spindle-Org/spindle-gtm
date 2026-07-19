---
name: take-apollo-list
description: End-to-end orchestrator — turn a named Apollo list into a filled, filterable CRM tracker + send plan + compliance checklist. Use whenever the user says "take/pull this list from Apollo" and wants outreach-ready artifacts. Read-only until the final human-approved send.
---

Turn an Apollo list into the outreach artifacts in `docs/outreach/README.md`. You are the
conductor: run each existing skill in order, carry its output forward, and stop for the
founder's approval at every external boundary. Do NOT re-derive the playbook — it is
pre-built in `docs/outreach/` (PRINCIPLES, COMPLIANCE, TRACKER_SCHEMA).

**Input:** an Apollo list name or id (ask if not given). **Output:** three files in
`exports/` — `outreach_tracker.csv`, `send_plan.md`, `compliance_checklist.md`.

## Guardrails (binding — from CLAUDE.md / docs/adr/0002)
Apollo is READ-ONLY. No LinkedIn automation — draft text only. Every personalized claim
needs verified evidence. Every external write is dry-run until the founder approves. The
filled tracker holds real emails → it lives in `exports/` and is NEVER committed.

## Steps

1. **Qualify** — run `/qualify-accounts` on the list. Produce the ranked shortlist; note
   drop reasons. Confirm the shortlist with the user before spending research effort.
2. **Select buying group** — run `/select-buying-group`. Operational champion first; hold
   exec sponsors as wave-2 second threads. Contact ids only — do not enrich emails yet.
3. **Research** — run `/research-batch`. One company-specific trigger per contact, each with
   source + access date. Prefer brand-level sources over parent-company/group stats.
4. **Verify** — run `/verify-evidence`. Only `verified` claims pass. This is the hard gate:
   unverified triggers get `trigger_confidence=low` and the row stays `send_status=hold`.
5. **Draft** — run `/draft-outreach` using the approved evidence only. Follow
   `docs/outreach/PRINCIPLES.md`: 50–90 words, 1–4 word Title-Case subject, interest/referral
   CTA, no "AI/platform"/pitch jargon, ≤1 sentence describing Spindle. Assign a CTA variant
   (A relevance / B asset / C referral) per contact. Warm contacts → relationship-first,
   flagged for the owner's personal approval.
6. **Review** — run `/review-outreach-batch`. Compliance + deliverability gate per region
   (`docs/outreach/COMPLIANCE.md`), then the manifest check. Rows that fail the region gate
   get `send_status=hold` + a `hold_reason`; EU defaults to LinkedIn-first (`legal_review_status=pending`).
7. **Assemble the tracker.** Run `spindle-gtm tracker template --out exports/outreach_tracker.csv`,
   then fill one row per contact from steps 1–6 against `docs/outreach/TRACKER_SCHEMA.md`.
   Enrich emails now (deliberately, for send-ready rows only). Then
   `spindle-gtm tracker validate exports/outreach_tracker.csv` and fix every issue —
   the batch is not done until it validates clean.
8. **Write `exports/send_plan.md`** — ranked first-wave order (trigger strength × role fit ×
   compliance-cleanliness), sender + channel + CTA variant per contact, and the open blockers
   (postal address, sender identity, EU legal review, domain auth). Batch-agnostic methodology
   is in `docs/outreach/README.md`.
9. **Write `exports/compliance_checklist.md`** — the per-region gate results for this batch
   from `docs/outreach/COMPLIANCE.md`, plus the deliverability preflight state.
10. **(Optional) `/prepare-apollo-actions`** — a dry-run plan of Apollo labels/notes for the
    founder to review. Never execute it here.

## Done when
`tracker validate` passes, all three `exports/` artifacts exist, and you've handed the user a
one-screen summary: counts by `send_status`/`region`, the first-wave order, and the blockers
that gate the first send. Nothing has been sent and nothing was written to Apollo.
