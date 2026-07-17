# Runbook — daily operator

A ~15-minute daily loop. Nothing here sends or writes to Apollo without an explicit,
separately-confirmed apply step.

## 1. Preflight
```sh
make doctor    # Apollo CLI/auth/MCP, DB, config, no tracked PII/secrets, kill switch engaged
```
If any check FAILs, stop and fix before touching a campaign.

## 2. Sync activity + triage replies
Run Operating Prompt H (reply triage) or drive it manually. Priorities in order:
1. positive replies → advance the commercial stage, prep discovery
2. referrals → a `research_referral` task is auto-created (never auto-send)
3. meetings → a `discovery_preparation` task is auto-created
4. objections / unsubscribes → suppression is auto-recorded; confirm
5. deliverability issues (bounces) → contact marked invalid; queue re-verification
6. due follow-ups

Any reply **locks the whole account** and prepares remove-from-sequence actions for the
other contacts — review and apply those via the outbound gateway.

## 3. Review the dashboard
```sh
make dashboard
```
- **Accounts / Buying groups / Research** — approve or reject evidence and selections.
- **Draft review** — edit (history is recorded), approve, or reject.
- **Batch manifest** — only advance DRAFTED → REVIEWED → APPROVED here; apply is separate.

## 4. Advance / prepare, do not send
- Prepare Apollo action manifests (Operating Prompt F) — no writes.
- Leave sending to the campaign-launch runbook with its typed confirmation.

## 5. End of day
- Confirm no batch is stuck mid-apply; check `logs/external-attempts.log`.
- Confirm the kill switch is still engaged unless a real send was explicitly authorized.
