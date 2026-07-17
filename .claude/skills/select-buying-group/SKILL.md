---
name: select-buying-group
description: Select the buying group (roles/contacts) for each qualified account. Read-only; does not reveal emails unless explicitly requested.
---

Select the buying group for qualified accounts.

1. Delegate to the **contact-selector** subagent (read-only Apollo + config).
2. For each account, choose the decision-makers/champions by title and seniority from the
   buyer-persona config. Return contact **ids**, not revealed emails.
3. Only if this skill was invoked with an explicit `--enrich` request do you ask the selector to
   enrich/reveal emails — otherwise leave enrichment for a later, deliberate step.

Guardrails: read-only Apollo; no enrichment by default; no sends.
