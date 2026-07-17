# ADR-0002 — External-action safety

- Status: Accepted
- Date: 2026-07-17
- Deciders: founder

## Context
The dangerous failure modes of an outreach tool are: emailing the wrong people, emailing
at unsafe volume, breaching regional law, leaking PII, and mutating the system of record.
A GTM tool that is convenient but unsafe is a liability.

## Decision
Every action that reaches an external system (Apollo, email, LinkedIn) is governed by
these non-negotiable rules:

1. **Dry-run by default.** The CLI performs no external action unless `--apply` is passed.
   `--apply` alone is never sufficient for a real send — a **batch-level human approval
   gate** must also be satisfied.
2. **Apollo is read-only.** We never create/update Apollo accounts, contacts, sequences,
   or campaigns. Apollo is the system of record; this tool only reads and snapshots.
3. **No LinkedIn automation.** LinkedIn is a **manual, human-in-the-loop** channel only —
   no API, no scraping, no automated actions. The tool may only draft text a human sends.
4. **Compliance gate before sendable.** Every contact passes `compliance_gate()` for its
   region; suppression wins over everything; unknown regions hold.
5. **Deliverability gates + caps.** Sends are capped per mailbox and rotated across
   domains; anomalies auto-pause. No blast path exists in code.
6. **Evidence for personalization.** Any personalized claim must cite evidence stored
   alongside it (source + fetched_at). No fabricated personalization.
7. **PII never enters git.** `data/`, `db/`, `exports/`, `.env*`, and `.csv` are ignored;
   only `.gitkeep` is tracked in data dirs. A guard (`spindle_gtm.security`) fails commits/
   CI that contain real-looking emails or exports. Test emails use `example.com`.
8. **CI is credential-free.** CI never accesses Apollo, never sends email, and never
   requires production secrets.

## Consequences
- Slower, deliberate outreach — acceptable at pilot scale and the point of the design.
- New external integrations must plug into the same guard + approval gate, enforced by
  code review (CODEOWNERS) and the PR safety checklist.
