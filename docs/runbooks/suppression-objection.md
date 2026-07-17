# Runbook — suppression & objection handling

Suppression wins over every other state. A suppressed contact can never be drafted, made
send-ready, or applied.

## When an objection / unsubscribe arrives
1. Activity sync creates a `SuppressionEntry` **immediately** and marks the contact
   `unsubscribed`. Confirm it landed:
   ```sh
   uv run python -c "from spindle_gtm.db import session_scope; from sqlmodel import select; from spindle_gtm.models import SuppressionEntry; \
   import itertools; s=session_scope().__enter__(); print([e.email or e.domain for e in s.exec(select(SuppressionEntry))][:20])"
   ```
2. If the objection is company-wide, add the domain to `config/suppression_rules.yaml`
   (`suppressed_domains`) and re-run `make check`.
3. Never contact that address/domain again, on any channel, without a fresh recorded basis.

## Where suppression is enforced
- **Gate #1** — `domain.draft_send_ready` holds a draft (status `HELD`) if the contact is suppressed.
- **Gate #2** — `preapply_recheck` re-checks suppression + account locks immediately before apply.
- **Compliance gate** — `contact_gate` returns BLOCK (`SUPPRESSED`) before any country logic.

## Role addresses
`config/suppression_rules.yaml` blocks role inboxes (info@, sales@, careers@, …). Keep that
list current; role addresses are never valid outreach targets.

## Retention
Suppression records are permanent (they are the do-not-contact ledger) and are excluded from
the 12-month PII purge — see the backup-and-retention runbook.
