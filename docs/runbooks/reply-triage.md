# Runbook — reply triage

## Sync activity
Ingest normalized Apollo activity (delivery/bounce/reply/meeting/sequence/stage). In dev
this runs on recorded fixtures; live sync is read-only.

## What the system does automatically (all reversible / no sends)
| Signal | Automatic behavior |
|--------|--------------------|
| Reply (any contact) | account **REPLIED lock** → new outreach blocked; PLANNED remove-from-sequence manifests prepared for the account's other contacts |
| Reply classified `referral` | `research_referral` task created — **never auto-sends** to the referred person |
| Meeting | `discovery_preparation` task + lock upgraded to MEETING_SET |
| Unsubscribe / objection | suppression record created **immediately**; contact marked unsubscribed |
| Bounce / bad data | contact `email_status=invalid`, `reverify_email` task — **no retries** until re-verified |
| Stage update | account stage synced |

## Operator actions
1. Positive reply → advance commercial stage (`progression.advance_stage`), start discovery prep.
2. Review and **apply** the prepared remove-from-sequence manifests via the outbound gateway
   (they are PLANNED, not auto-applied).
3. Referral → work the `research_referral` task (research first, never cold-send).
4. Objection → confirm suppression; add to `config/suppression_rules.yaml` if domain-wide.
5. Bounce → do not reuse the address until re-verified.

## Priority order for the operator queue
positive replies → referrals → meetings → objections → deliverability issues → due follow-ups.
