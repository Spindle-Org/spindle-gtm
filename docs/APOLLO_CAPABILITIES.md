# Apollo capabilities & enforcement (sanitized)

> Read-only integration. This document is **sanitized** — no tokens, emails, team IDs, or
> credit balances. Generated from `apollo --help` (CLI v1.1.1) and the connected Apollo MCP
> tool list. Verified against **Claude Code 2.1.212**.

## Access surfaces
- **CLI:** official `apollo-io-cli` (Homebrew tap `apolloio/apollo-io-cli`), binary `apollo`.
  Install (macOS): `brew install apolloio/apollo-io-cli/apollo-io-cli`.
- **MCP:** remote HTTP server `apollo` at `https://mcp.apollo.io/mcp`, added at **project scope**
  (`.mcp.json`, URL-only, no secrets). OAuth is completed interactively per user; tokens are
  stored by Claude Code / the CLI outside the repo and are never committed.
- **Official Claude Code skill:** `.claude/skills/apollo-cli/SKILL.md` (vendored from the official
  repo; exempt from the PII scan as third-party docs).

## Classification legend
| Class | Meaning | Enforcement (this repo) |
|-------|---------|-------------------------|
| READ | No credits, no mutation | Allowed (defer to normal permissions) |
| CREDIT | Consumes Apollo credits (enrichment / reveal / match) | **ASK** (human approval) |
| WRITE | CRM mutation or purchase | **ASK** (human approval) |
| SEND/ENROLL | Sends real email or enrolls contacts | **DENY** (blocked during development) |

Enforcement is implemented in `src/spindle_gtm/policy.py` (verb-based, applies to both MCP tools
and the CLI) and surfaced via the `PreToolUse` hook. Every CREDIT/WRITE/SEND attempt — including
denials — is logged to `logs/external-attempts.log`.

## Actions that consume credits
`people enrich`, `people bulk-enrich`, `people email` (reveal), `companies enrich`,
`companies bulk-enrich`; MCP `apollo_organizations_enrich`, `apollo_organizations_bulk_enrich`,
`apollo_people_match`, `apollo_people_bulk_match`. → **ASK**.

## Actions that can send real messages
`sequences add-contacts` ("sends real emails"), `sequences approve` (activates sending); MCP
`apollo_emailer_messages_send_now`, `apollo_emailer_messages_create`,
`apollo_emailer_campaigns_add_contact_ids`, `apollo_emailer_campaigns_approve`. → **DENY**
(blocked; sequence enrollment and one-off sends stay blocked during development).

## CLI command map
| Group | READ | CREDIT | WRITE | SEND/ENROLL |
|-------|------|--------|-------|-------------|
| people | search, employees | enrich, bulk-enrich, email | — | — |
| companies | search, get, jobs | enrich, bulk-enrich | — | — |
| news | search | — | — | — |
| contacts | search | — | create, update, bulk-create | — |
| accounts | — | — | create, update, bulk-create | — |
| deals | search, show | — | create | — |
| sequences | search, schedules | — | create, update, remove-contacts | **add-contacts, approve** |
| calls | search | — | log, update | — |
| tasks | search | — | create, bulk-create | — |
| email-accounts | list | — | — | — |
| usage | credits | — | — | — |
| users | profile, search | — | — | — |
| analytics | report | — | — | — |
| auth | whoami, login, logout | — | — | — |

## MCP tool map
- **READ:** `apollo_contacts_search`, `apollo_mixed_companies_search`,
  `apollo_mixed_people_api_search`, `apollo_organizations_job_postings`,
  `apollo_emailer_campaigns_search`, `apollo_emailer_schedules_index`,
  `apollo_email_accounts_index`, `apollo_fields_index`, `apollo_labels_index`,
  `apollo_tasks_search`, `apollo_tasks_show`, `apollo_usage_stats_credit_usage_stats`,
  `apollo_users_api_profile`, `apollo_analytics_sync_report`, `apollo_webhook_result_show`,
  `apollo_emailer_messages_email_send_status`, `apollo_context_center_show*`.
- **CREDIT (ASK):** `apollo_organizations_enrich`, `apollo_organizations_bulk_enrich`,
  `apollo_people_match`, `apollo_people_bulk_match`.
- **WRITE (ASK):** `apollo_accounts_create|bulk_create|update`,
  `apollo_contacts_create|bulk_create|update`,
  `apollo_tasks_create|bulk_create|update|complete|skip`,
  `apollo_labels_create|update|add_entity_ids_to_label_names|remove_entity_ids_from_label_names`,
  `apollo_sequences_create|update`, `apollo_context_center_create_*|update_*`,
  `apollo_email_account_purchase_create|index`, `apollo_domain_purchase_index`,
  `apollo_feedback_log`, `apollo_emailer_campaigns_remove_or_stop_contact_ids`.
- **SEND/ENROLL (DENY):** `apollo_emailer_messages_send_now`, `apollo_emailer_messages_create`,
  `apollo_emailer_campaigns_add_contact_ids`, `apollo_emailer_campaigns_approve`.

> Unknown/unclassified Apollo verbs fail safe to **ASK** (never silently allowed). After any
> Apollo update, re-check `policy.py`'s verb regexes against the current tool list.

## Outbound kill switch
`OUTBOUND_ENABLED` (config, default **false** = outbound disabled). `spindle-gtm doctor` asserts
it stays engaged. Enabling it is a deliberate, reviewed step — separate from this foundation.
