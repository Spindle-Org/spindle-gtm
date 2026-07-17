# Runbook — rollback

## Code / release rollback
```sh
git checkout main && git pull
git revert <bad-merge-sha> -m 1     # revert a merge commit; open a PR
# or, before a release is merged, just close the PR
```
Never force-push `main`. CI + branch protection must stay green.

## Database rollback
```sh
uv run alembic downgrade -1         # step back one revision
make migrate                        # return to head when ready
```
The DB is a research/audit cache, not the system of record — Apollo state is unaffected by a
local DB rollback. Restore from a backup if needed (backup-retention runbook).

## Outbound rollback
- Local: `outbound cancel --batch <id>` cancels not-yet-applied manifests.
- Applied enrollments: prepare + apply remove-from-sequence via the gateway (gated; no sends).
  Idempotency means re-running apply never double-enrolls.
- Engage the kill switch first if anything is uncertain (incident-kill-switch runbook).

## Config rollback
Config is versioned in git. Revert the offending `config/*.yaml` change and re-run
`make check` so the Pydantic schemas re-validate.

## After any rollback
`make verify` must pass before resuming.
