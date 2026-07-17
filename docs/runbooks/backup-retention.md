# Runbook — backup & retention

The local DB (`db/spindle.db`) and `generated/`, `exports/`, `logs/`, `outbox/` contain PII
and are **gitignored** — they never enter version control.

## Backup (local, encrypted)
```sh
# Snapshot the SQLite DB to an encrypted local location (not a synced/public folder).
cp db/spindle.db "$HOME/spindle-backups/spindle-$(date +%F).db"   # then encrypt at rest (FileVault / disk image)
```
Do NOT back up to any location that leaves the machine or is shared. Backups inherit the
same do-not-commit rules as the live DB.

## Retention (PII)
Policy: retain contact PII for **12 months**, then purge — but **keep** contacts who replied,
and keep suppression records permanently (do-not-contact ledger).

Sketch of the purge (run deliberately, not automated externally):
- select contacts with `fetched_at`/`last_synced_at` older than 12 months
- exclude any with a reply/meeting activity and any on the suppression ledger
- anonymize/delete PII fields; keep aggregate/audit rows

## Logs
`logs/external-attempts.log` may contain payloads with emails — it is gitignored. Rotate and
purge it on the same 12-month cadence; never commit or export it.

## Restore
```sh
cp "$HOME/spindle-backups/spindle-YYYY-MM-DD.db" db/spindle.db
make migrate   # ensure schema is at head
make doctor
```
