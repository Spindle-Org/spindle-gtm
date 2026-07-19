# Apollo-list → CRM tracker: the standing outreach pipeline

This folder is the **pre-built playbook** so that whenever you say *"take this list
from Apollo"*, the work is already scoped: Claude just runs the orchestrator skill
`/take-apollo-list`, follows the numbered steps, and hands you a filled, filterable
CRM tracker plus a send plan and compliance checklist.

Nothing here contacts anyone or writes to Apollo. Apollo stays read-only; every send
is dry-run until you approve (see `CLAUDE.md`, `docs/adr/0002`).

## What you get at the end (the artifacts)

All land in the gitignored `exports/` dir (they contain real emails = PII):

| Artifact | What it is |
|---|---|
| `exports/outreach_tracker.csv` | The CRM tracker — one row per contact, 50 columns, ready to sort/filter. Schema: [`TRACKER_SCHEMA.md`](TRACKER_SCHEMA.md). |
| `exports/send_plan.md` | Ranked first-wave send order, sender + channel + CTA variant per contact, blockers. |
| `exports/compliance_checklist.md` | Per-region legal + deliverability gate results for this batch (from [`COMPLIANCE.md`](COMPLIANCE.md)). |

## The one command

```
/take-apollo-list <apollo-list-name-or-id>
```

The orchestrator skill drives the existing skill chain in order and stops for your
approval at every external boundary. You never assemble the 50 columns by hand.

## The pipeline (what the orchestrator runs)

Each step is an existing skill delegating to a scoped subagent. Read-only until the
final human-approved send.

1. **`/qualify-accounts`** — pull the Apollo list (read-only), score each account vs ICP,
   drop misfits. → shortlist.
2. **`/select-buying-group`** — pick the operational champion (+ optional exec sponsor)
   per account by persona/seniority. Contact **ids** only; enrich emails later, deliberately.
3. **`/research-batch`** — one verified trigger per contact, each with source + access date.
4. **`/verify-evidence`** — independent re-check. Only `verified` claims survive; this is
   the gate into copywriting.
5. **`/draft-outreach`** — from approved evidence only, per the rules in
   [`PRINCIPLES.md`](PRINCIPLES.md): 50–90 words, 1–4 word subject, interest/referral CTA,
   no "AI/platform" jargon. Produces subject A/B/C, `email_1`, 3 follow-ups, LinkedIn +
   reply + referral scripts. Each line cites its evidence id.
6. **`/review-outreach-batch`** — compliance + deliverability gate ([`COMPLIANCE.md`](COMPLIANCE.md)),
   then a manifest check. Go / no-go. No sends, no approvals.
7. **Assemble the tracker** — `spindle-gtm tracker template --out exports/outreach_tracker.csv`,
   fill one row per contact from steps 1–6, then `spindle-gtm tracker validate` it.
8. **Write the send plan + compliance checklist** into `exports/`.
9. **`/prepare-apollo-actions`** (optional, dry-run) — proposed labels/notes for your review.
   Never executes.

## Filtering the tracker (how you actually work it)

The tracker's constrained columns are the filter axes. Common views:

- **This week's US sends:** `region = US` AND `send_status = ready` AND `legal_review_status ∈ {not-required, cleared}`.
- **EU legal-hold queue:** `region = EU` AND `legal_review_status ∈ {pending, hold}` → LinkedIn-first.
- **Best triggers first:** sort by `source_tier` (A→E) then `trigger_score` desc.
- **Needs a champion:** `deal_role = Operational champion` AND `send_status = draft`.
- **Reply triage:** `reply_status = positive` → discovery; `= referral` → referral script.
- **One-per-account:** never two `send_status = ready` rows for the same `company`.

See [`TRACKER_SCHEMA.md`](TRACKER_SCHEMA.md) for every column and its allowed values.

## Test / send methodology (batch-agnostic)

- **CTA variants** per contact: **A** = relevance, **B** = useful asset (the Change Map),
  **C** = referral. Assign one per row; compare positive-reply quality, not open rate.
- **Wave sizing:** start ~8–14 accounts, US-by-email / EU-by-LinkedIn-first, 2–3 sends/day
  to warm the domain. One contact per account until it replies or the sequence closes.
- **Success = positive/qualified reply rate, referral rate, useful corrections** — never open rate.
- **Graduation to pilot:** positive reply → discovery call → named collection + owners → *then*
  design-partner framing, and only after that price/pilot scope. Never in a first touch.

## Guardrails (binding)

Apollo read-only · no LinkedIn automation (drafts only) · evidence required for every
personalized claim · human approval for every external write · no PII in git — the filled
tracker lives in `exports/` and is never committed.
