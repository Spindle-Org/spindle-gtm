# Runbook — incident & kill switch

Use when something is wrong with outbound (wrong recipients, deliverability spike, a real
send that should not have happened, or any uncertainty).

## Engage the kill switch immediately
```sh
# in .env
OUTBOUND_ENABLED=false
```
With the kill switch engaged, `outbound apply` and `verify_outbound` refuse
(`KILL_SWITCH_ENGAGED`) regardless of approval or typed confirmation. The real Apollo
client also refuses until the rollout runbook is signed off, so in development outbound is
already off.

## Contain
1. `uv run spindle-gtm outbound cancel --batch <id>` for any in-flight batch.
2. If contacts were enrolled, prepare + apply remove-from-sequence via the gateway (this is
   itself a gated action; it never sends).
3. Add affected addresses/domains to suppression (see suppression-objection runbook).

## Diagnose
- `logs/external-attempts.log` — every attempted external write, including denials, with reason codes.
- Compliance decision log (`compliance_decisions` table) — per-contact reason codes.
- Audit log (`audit_log`) — reviews, approvals, revocations, apply confirmations.

## Recover
- Root-cause before re-enabling. Re-run `make verify` (release gate).
- Only re-set `OUTBOUND_ENABLED=true` after the founder explicitly authorizes, and only for
  the specific approved batch.

## Escalation
Anything touching real recipients, PII exposure, or a wrong send → notify the founder before
re-enabling. Document the incident and the fix.
