# spindle-gtm — Implementation Plan

> Status: **approved foundation plan (Phase 0)**. Scope: get the first **25–50 accounts researched and
> outreach-ready** and convert to **3–5 signed LOIs** for a free time-boxed pilot — without building an
> unsafe high-volume automation system. Local **Python + SQLite** engine, run by one founder, one batch
> at a time, with a hard human-approval gate before any send.

## 0. Fixed decisions (from interview)
- Env: macOS 26.5.2, Claude Code 2.1.212.
- Stack: Python 3.12 + SQLite; single-user, local-only engine.
- Dashboard: Next.js on Vercel — **aggregate/status only, zero raw PII** (see §5, §6).
- Repo security: enable GitHub **secret scanning + push protection** (manual setup step).
- Apollo: Professional plan, admin (REST API key available), **read-only source**, seed = a saved
  company list.
- Sending: multiple cold domains + many mailboxes with rotation + per-mailbox caps; **1 founder** sends.
- Regions: US, Canada, UK/EU, Australia, APAC (India, Korea, Japan) → global compliance gates.
- First batch: 25–50 accounts. Governance: founder approves every batch. Retention: 12 months then
  purge; keep indefinitely if the contact replied.
- Offer: free time-boxed pilot. Success: 3–5 signed LOIs.

## 1. System boundaries
- **In-system (owned):** local Python CLI, local SQLite DB (`data/spindle.db`) = source of truth for all
  accounts/contacts/messages/events; local exports (`exports/`); message drafts; suppression list;
  region policy config.
- **Trust-boundary edges (external, not owned):**
  - Apollo (via MCP now; REST key optional) — **read-only**: company/contact search, enrichment,
    job-postings. Never the source of truth; never the sender.
  - Cold email mailboxes / SMTP-or-provider (e.g. Google Workspace / dedicated ESP) — the **only**
    sending surface. Manual or gated send.
  - LinkedIn — **manual only**, no automation, no scraping (see §10).
  - Vercel/Next.js dashboard — **read-only, PII-free** view fed by a sanitized export.
  - GitHub (private repo) — code only; never data or secrets.
- **Explicitly outside the boundary:** any auto-send without approval, any Apollo write-back, any
  multi-user server, any LinkedIn automation.

## 2. Architecture Decision Records (ADRs)
- **ADR-1 Local SQLite single source of truth.** Simplest durable store; one founder; portable; easy
  backups. Rejected: hosted DB (infra + PII exposure not justified at pilot scale).
- **ADR-2 Apollo read-only.** Keep deliverability/volume in our control; avoid coupling to Apollo
  sending limits and avoid Apollo-side campaign state drift. Rejected: Apollo sequences send.
- **ADR-3 Manual approval gate before any send.** Safety over throughput; a batch is inert until the
  founder approves. Non-negotiable.
- **ADR-4 Python + SQLite over TS.** Best fit for data pulls, enrichment, CSV, MCP orchestration; fewer
  moving parts than a JS engine. Dashboard is the only JS surface.
- **ADR-5 Dashboard is PII-free.** Vercel is public infra; it receives only aggregate metrics +
  account/batch status keyed by opaque ids — never emails/names/enrichment. Removes hosted-PII threat.
- **ADR-6 Domain/mailbox rotation with hard caps, not scale.** Multiple cold domains exist for
  deliverability & warmup headroom, but per-mailbox/day caps keep true volume low. No blast path exists
  in code.
- **ADR-7 Region policy as data, gate as code.** A `region_policy` table + a single `compliance_gate()`
  function every contact must pass before becoming sendable. Adding a country = a row, not a refactor.

## 3. Phased roadmap
- **Phase 0 — Foundation (this doc).** Repo scaffold, `.gitignore`/`.env.example`, SQLite schema,
  region-policy seed, suppression list, secret protection ON. No network writes.
- **Phase 1 — Ingest + enrich (read-only).** Pull the saved Apollo company list → `accounts`; enrich →
  `contacts`; dedupe; apply suppression. Output: a research-ready batch of 25–50 accounts. No sending.
- **Phase 2 — Research + draft.** Per-account research notes (Apollo job-postings/signals + manual),
  generate personalized draft messages into `messages` (status `draft`). Founder reviews.
- **Phase 3 — Compliance + deliverability gates.** Run `compliance_gate()` and deliverability preflight
  over the batch; anything failing is held with a reason. Founder-approve the batch.
- **Phase 4 — Send (gated, low-volume).** Send approved messages from rotating mailboxes under caps;
  log events; handle replies/bounces/unsubscribes → suppression.
- **Phase 5 — Track outcomes + dashboard.** Sync sanitized metrics to the Vercel dashboard; track
  meetings → LOIs against the 3–5 goal. Retention job (12mo/purge; keep if replied).

## 4. Source-of-truth rules
- Local SQLite is authoritative for **everything** operational: account/contact state, message content
  & status, consent/region determination, suppression, events, outcomes.
- Apollo is authoritative only for **upstream firmographic/contact discovery data at pull time**; we
  snapshot it into the DB with `apollo_id` + `fetched_at`. We never treat live Apollo state as truth and
  never write back.
- The dashboard is authoritative for **nothing**; it is a derived, read-only projection.
- Suppression list is authoritative and **wins over everything** — a suppressed contact can never be
  drafted or sent, regardless of source.
- Conflict rule: on re-pull, DB values are updated only for enrichment fields; **human-set fields**
  (status, approval, notes, consent decision) are never overwritten by an Apollo pull.

## 5. Read and write paths
- **Read (Apollo → DB):** `pull_accounts(list_id)` → `apollo_mixed_companies` / enrich →
  upsert `accounts`/`contacts` (snapshot + `fetched_at`). Idempotent on `apollo_id`.
- **Write (DB internal):** all state transitions go through typed functions
  (`create_batch`, `draft_message`, `approve_batch`, `record_event`) — never ad-hoc SQL in callers, so
  every write hits validation + the state machine.
- **Send path (DB → mailbox):** only `send_approved(batch_id)` reads messages where
  `status=approved AND batch.approved=true AND contact passes gate AND mailbox under cap`, sends, then
  writes a `sent` event. No other code path can emit mail.
- **Dashboard path (DB → Vercel):** `export_dashboard()` writes a **sanitized** JSON/rows (counts,
  per-batch status, funnel: pulled→drafted→approved→sent→replied→meeting→LOI, region breakdown by
  code) with **no names/emails/message bodies**. Pushed to the dashboard's store behind auth.
- **No path exists** from dashboard back into the engine (read-only projection).

## 6. Threat model
- **Assets:** contact PII (emails/names/enrichment), sending-domain reputation, Apollo credentials,
  mailbox credentials, the LOI pipeline.
- **Threats & mitigations:**
  - *Secret leakage to git* → GitHub secret scanning + push protection ON; `.env` + `data/` gitignored;
    `.env.example` only. Secrets never in code.
  - *PII leak via public dashboard* → dashboard is PII-free by construction (§5); auth on the dashboard;
    no bodies/emails leave the laptop.
  - *Accidental mass-send / wrong recipient* → hard approval gate + per-mailbox caps + suppression
    precedence + dry-run default; send requires explicit `--confirm`.
  - *Domain reputation burn* → warmup, caps, rotation, bounce/complaint monitoring auto-pauses a mailbox.
  - *Compliance breach (CASL/GDPR/APAC)* → `compliance_gate()` blocks sendability per region; suppression
    honored; unsubscribe + physical address enforced in template.
  - *Apollo credit/data misuse* → read-only, rate-limited, snapshot; no bulk export beyond batch need.
  - *Local data loss* → periodic DB backup to an encrypted local location (documented, not automated
    externally).
- **Out of scope for pilot:** nation-state, multi-tenant isolation, full SOC2 — noted as future.

## 7. Data model (SQLite)
Tables (key columns):
- `domains` (id, domain, status[warming|active|paused], warmup_started_at, reputation_notes)
- `mailboxes` (id, domain_id→, address, daily_cap, sent_today, warmup_stage, status, provider_ref)
- `senders` (id, name, founder=true, mailbox_id→)  *(1 row for pilot; modelled for N)*
- `accounts` (id, apollo_id, name, domain, industry, size, hq_country, region_code, stage,
  research_notes, fetched_at, status)
- `contacts` (id, account_id→, apollo_id, first/last, title, email, email_status[verified|guessed],
  linkedin_url, region_code, consent_basis, fetched_at, status, suppressed_reason NULL)
- `batches` (id, name, created_at, size, approved_by NULL, approved_at NULL, status)
- `messages` (id, contact_id→, batch_id→, sender_id→, channel[email|linkedin_manual], subject, body,
  status, gate_result, scheduled_at, sent_at, provider_msg_id)
- `events` (id, message_id→/contact_id→, type[sent|delivered|open|reply|bounce|complaint|unsub|meeting|
  loi], payload, occurred_at)
- `suppression` (id, email/domain, scope, reason, created_at)  *(authoritative, precedence)*
- `region_policy` (region_code, legal_basis, requires_consent bool, unsubscribe_required bool,
  physical_address_required bool, cold_email_allowed enum[yes|caution|no], notes)
- `outcomes` (account_id→, meeting_at, loi_status, loi_signed_at)  *(tracks the 3–5 LOI goal)*
- Retention handled by a job over `contacts.fetched_at` + reply events (12mo purge; keep if replied).

## 8. State machines
- **Account:** `pulled → researching → research_ready → in_batch → contacted → engaged → won(LOI) |
  disqualified`.
- **Contact:** `new → enriched → gate_pending → gate_passed → drafted → approved → sent → replied |
  bounced | unsubscribed | suppressed`. Suppressed/unsubscribed are terminal for outreach.
- **Batch:** `open → assembled → gated → awaiting_approval → approved → sending → sent → closed`.
  Only `approved` (by founder) unlocks `sending`. No transition skips approval.
- **Message:** `draft → gated(pass|hold) → approved → queued → sent → (delivered|bounced) →
  (replied|no_reply)`. `hold` requires a human to resolve the reason before it can advance.

## 9. Apollo integration plan (read-only)
- **Auth:** MCP OAuth (already connected) as primary; document optional REST API key (admin-available)
  as a fallback/automation path stored in `.env` (never committed).
- **Ingest:** resolve the saved company list → companies; `organizations_enrich` for firmographics;
  `contacts_search` / `people_match` for 1–3 contacts per account (title-filtered to buyer personas);
  `organizations_job_postings` for research signals.
- **Snapshot & idempotency:** upsert by `apollo_id`; store `fetched_at`; re-pull updates enrichment
  fields only (never human fields — §4).
- **Rate/credit safety:** batch-bounded pulls (25–50 accounts), backoff on rate limits, log
  `usage_stats` before/after; no bulk exports.
- **No writes:** we do **not** create Apollo accounts/contacts/sequences/campaigns. (Those MCP tools
  exist but are out of scope; enforced by convention + code review, not called.)

## 10. LinkedIn manual workflow
- **Manual, human-in-loop only. No automation, no scraping, no API.** The tool stores
  `contacts.linkedin_url` and generates a **suggested manual touch** (connection note / message text)
  as an export the founder copy-pastes by hand in the browser.
- The founder logs the outcome back via a CLI command (`log-linkedin <contact_id> <sent|replied|...>`)
  → `events`. Channel `linkedin_manual` never flows through the email send path or caps.
- Purpose: a compliant secondary channel for regions where cold email is `caution`/`no` (§11).

## 11. Compliance gates by region
`compliance_gate(contact)` reads `region_policy[contact.region_code]` and returns pass/hold+reason.
Seeded policy (B2B cold outreach, pilot-conservative — legal review is an open question, §15; **this is
not legal advice**):
- **US** — CAN-SPAM: cold email `yes`; require truthful headers, physical postal address, working
  unsubscribe.
- **Canada** — CASL: cold email `caution` (consent/implied-consent regime); prefer LinkedIn-manual or a
  documented existing-business-relationship; hard-require identification + unsubscribe; default HOLD
  unless founder marks a lawful basis.
- **UK/EU** — GDPR + PECR: cold B2B `caution` on legitimate-interest basis; require LIA note,
  identification, easy opt-out, honor erasure; corporate (role-based) addresses only, no individuals
  where avoidable.
- **Australia** — Spam Act: cold email `caution`; require consent/inferred consent + unsubscribe +
  identification.
- **APAC (India DPDP / Korea PIPA / Japan APPI)** — `caution`→`no` depending on country; consent-leaning
  regimes → default to **LinkedIn-manual** channel, HOLD email unless a lawful basis is recorded.
- Global invariants enforced for every send: suppression honored, unsubscribe present, sender identity +
  physical address present, per-contact frequency cap.

## 12. Deliverability gates
Preflight before a batch can send (each is a hard check; failure → hold):
- Domain has SPF + DKIM + DMARC configured and `status=active` (not `warming`).
- Mailbox `sent_today < daily_cap`; warmup stage sufficient for batch size; caps small
  (e.g. start ≤20/mailbox/day, ramp slowly).
- Rotation spreads sends across mailboxes/domains; randomized spacing; no burst.
- Content checks: no spam-trigger phrases, plain-text-friendly, single tracked link max, list-unsubscribe
  header present.
- Bounce/complaint monitor: if a mailbox's bounce or complaint rate crosses a threshold → auto-`paused`,
  batch halts, founder alerted.
- Email address `email_status=verified` preferred; `guessed` requires extra confirmation or HOLD.

## 13. Test strategy
- **Unit (pytest):** `compliance_gate()` per region (table-driven cases), state-machine transitions
  (illegal transitions raise), suppression precedence, cap accounting, dedupe/idempotent upsert,
  dashboard export contains **no** PII (assert no email/name keys).
- **Dry-run harness:** every send path defaults to dry-run; a golden test asserts dry-run emits zero
  network calls and produces an accurate preview.
- **Fixture Apollo:** record a small fixture of Apollo responses; ingest tested against fixtures, not
  live credits.
- **Manual acceptance:** one real end-to-end on a **seed/test account you own** (send to yourself)
  before any real recipient.

## 14. Rollout plan
1. Phase 0 scaffold merged; secret protection ON; schema + region policy seeded.
2. Ingest 25–50 accounts read-only; verify counts + dedupe + suppression on fixtures then live.
3. Draft + research; founder reviews all copy.
4. Run gates; founder approves batch; **send one test to self**; verify deliverability signals.
5. Send to a **first sub-slice (~5 accounts)**, watch bounce/complaint/reply for 48h.
6. If healthy, release the remainder under caps. Track meetings → LOIs toward 3–5.
7. Retention job scheduled; dashboard reflects the funnel.

Rollback: any mailbox anomaly auto-pauses; batches are inert without approval; DB backups allow restore.

## 15. Open questions
- Which exact Apollo saved list (name/id) is the seed?
- Sending provider for cold mailboxes (Google Workspace vs dedicated cold-email ESP) + how many
  domains/mailboxes exist today and their warmup status?
- Buyer-persona titles to target per account?
- **Legal sign-off** on the region policy defaults (esp. CASL / GDPR / APAC) — the seeded matrix is
  conservative-but-not-legal-advice; confirm before sending to CA/EU/APAC.
- Dashboard auth mechanism + where the sanitized export is stored (Vercel KV/Postgres? which?).
- Pilot length ("time-boxed" = how many weeks) and LOI template/source.
- Unsubscribe mechanism (hosted link vs reply-to-opt-out) for the physical/link requirements.

## 16. Non-goals (explicit)
- No high-volume / blast automation; no scaling past caps in the pilot.
- No Apollo write-back (no auto-created accounts/contacts/sequences/campaigns).
- No LinkedIn automation or scraping.
- No multi-user server, auth system, or hosted PII store.
- No auto-send without founder approval.
- No CRM rebuild — SQLite is the pilot store, not a product.
- No AI auto-reply / auto-negotiation of LOIs.
